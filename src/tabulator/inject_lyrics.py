# -*- coding: utf-8 -*-
"""Write lyric lines into a Guitar Pro 8 score, one token per beat.

    python src/tabulator/inject_lyrics.py in.gp out.gp lyrics.json [--track N] [--dry]

lyrics.json is a list of [bar, text]. bar is 0-based and says where the line
starts.

Guitar Pro's own dispatch (track level <Lyrics>, what the Lyrics window edits)
walks the beats and skips every rest, so a syllable can never land on a rest and
a line that should start before the first chord has nowhere to go. This writes
the tokens straight onto the beats instead, as beat level <Lyrics><Line>, which
is the form Guitar Pro itself saves after a manual nudge. One token per beat of
voice 0, rests included, and the track level block is blanked so the dispatch
cannot overwrite the placement.

Tokens: every CJK character is its own token, an ASCII word stays whole, PLUS
glues characters onto one beat, DOT leaves a beat blank, and a space only
separates. So "無+心 的+愛" puts "無心" on the rest and "的愛" on the chord after it.
"""

import argparse
import collections
import io
import json
import re
import sys

sys.path.insert(0, ".")

from src.gp_ops.patcher import load_gpif, save_gpif
from src.gp_ops.reader import _refs, _table

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

LINES = 5                 # Guitar Pro keeps five lyric lines on every beat, filled or not
BLANK_LINE = "<Line>\n<Text><![CDATA[]]></Text>\n<Offset>0</Offset>\n</Line>"


def tokens(text):
    out = []
    glue = False
    joinable = False
    for ch in text:
        if ch == "+":
            glue = bool(out)
        elif ch == " ":
            glue = False
            joinable = False
        elif ch == ".":
            out.append("")
            joinable = False
        elif glue:
            out[-1] += ch
            glue = False
            joinable = ord(ch) <= 0x2E7F
        elif ord(ch) > 0x2E7F:
            out.append(ch)
            joinable = False
        elif joinable:
            out[-1] += ch
        else:
            out.append(ch)
            joinable = True
    return out


def slots(xml, track):
    """Flat [(bar, voice, position in voice, beat, is rest)] over voice 0."""
    bars = _table(xml, "Bars", "Bar")
    voices = _table(xml, "Voices", "Voice")
    beats = _table(xml, "Beats", "Beat")
    out = []
    for bar, mb in enumerate(re.finditer(r"<MasterBar>(.*?)</MasterBar>", xml, re.S)):
        ids = _refs(mb.group(1), "Bars")
        if track >= len(ids):
            continue
        voice = _refs(bars.get(ids[track], ""), "Voices")
        if not voice or voice[0] == -1:
            continue
        for pos, bid in enumerate(_refs(voices.get(voice[0], ""), "Beats")):
            out.append((bar, voice[0], pos, bid, "<Notes>" not in beats.get(bid, "")))
    return out


def dispatch(lines, table):
    """slot index -> {line index: token}, plus one placement list per line."""
    per_slot = {}
    report = []
    for li, (bar, toks) in enumerate(lines):
        start = next((i for i, s in enumerate(table) if s[0] == bar), None)
        if start is None:
            sys.exit(f"line {li + 1}: bar {bar + 1} has no beats on this track")
        if start + len(toks) > len(table):
            sys.exit(f"line {li + 1}: {len(toks)} tokens run past the last beat")
        placed = []
        for k, tok in enumerate(toks):
            if tok:
                per_slot.setdefault(start + k, {})[li] = tok
            placed.append((tok, table[start + k][4]))
        report.append(placed)
    return per_slot, report


def unshare(xml, table, wanted):
    """Give every lyric carrying slot its own Beat node.

    Guitar Pro keeps one Beat per distinct content and points several voices at
    it, so writing lyrics by beat id alone would echo them onto every other spot
    that reuses the beat.
    """
    voices = _table(xml, "Voices", "Voice")
    beats = _table(xml, "Beats", "Beat")
    uses = collections.Counter()
    for body in voices.values():
        for bid in _refs(body, "Beats"):
            uses[bid] += 1

    ids = {}
    clones = []
    edits = collections.defaultdict(dict)
    next_id = max(beats) + 1
    for i in sorted(wanted):
        _, vid, pos, bid, _ = table[i]
        if uses[bid] == 1:
            ids[i] = bid
            continue
        uses[bid] -= 1
        ids[i] = next_id
        clones.append((next_id, beats[bid]))
        edits[vid][pos] = next_id
        next_id += 1

    if clones:
        block = "".join(f'<Beat id="{n}">{b}</Beat>\n' for n, b in clones)
        cut = xml.rindex("</Beats>")
        xml = xml[:cut] + block + xml[cut:]
    for vid, changes in edits.items():
        seq = _refs(voices[vid], "Beats")
        for pos, new in changes.items():
            seq[pos] = new
        joined = " ".join(str(s) for s in seq)
        xml = re.sub(r'(<Voice id="%d">\s*<Beats>)[^<]*(</Beats>)' % vid,
                     lambda m: m.group(1) + joined + m.group(2), xml, count=1)
    return xml, ids


def blank_track_lyrics(xml, track):
    block = '<Lyrics dispatched="true">\n' + "\n".join([BLANK_LINE] * LINES) + "\n</Lyrics>"
    spans = list(re.finditer(r'<Track id="\d+">(.*?)</Track>', xml, re.S))
    if track >= len(spans):
        sys.exit(f"no track {track} in score")
    body = spans[track].group(1)
    if "<Lyrics" in body:
        fixed = re.sub(r"<Lyrics\b.*?</Lyrics>", lambda _: block, body, count=1, flags=re.S)
    else:
        fixed = body + block + "\n"
    return xml[:spans[track].start(1)] + fixed + xml[spans[track].end(1):]


def inject(xml, per_beat):
    def repl(m):
        bid, body = int(m.group(1)), m.group(2)
        body = re.sub(r"<Lyrics>.*?</Lyrics>\s*", "", body, flags=re.S)
        line_map = per_beat.get(bid)
        if line_map:
            block = "".join(f"<Line><![CDATA[{line_map.get(i, '')}]]></Line>\n"
                            for i in range(LINES))
            body = f"{body}<Lyrics>\n{block}</Lyrics>\n"
        return f'<Beat id="{bid}">{body}</Beat>'
    return re.sub(r'<Beat id="(\d+)">(.*?)</Beat>', repl, xml, flags=re.S)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("lyrics")
    ap.add_argument("--track", type=int, default=0)
    ap.add_argument("--raw", action="store_true", help="text is already one token per beat, space separated, empty token for a blank beat")
    ap.add_argument("--dry", action="store_true", help="print the placement, write nothing")
    args = ap.parse_args()

    with open(args.lyrics, encoding="utf-8") as f:
        raw = json.load(f)
    lines = [(int(bar), text.split(" ") if args.raw else tokens(text)) for bar, text in raw]

    xml = load_gpif(args.src)
    table = slots(xml, args.track)
    if not table:
        sys.exit(f"track {args.track} has no beats")
    per_slot, report = dispatch(lines, table)

    for (bar, _), placed in zip(lines, report):
        shown = " ".join(f"[{t}]" if rest else (t or ".") for t, rest in placed)
        print(f"  bar {bar + 1:>3}  {shown}")
    print("[] sits on a rest, . leaves the beat blank")

    if args.dry:
        return
    xml, ids = unshare(xml, table, per_slot)
    xml = blank_track_lyrics(xml, args.track)
    xml = inject(xml, {ids[i]: v for i, v in per_slot.items()})
    save_gpif(args.src, args.out, xml)
    print(f"{len(lines)} lines on {len(per_slot)} beats -> {args.out}")


if __name__ == "__main__":
    main()
