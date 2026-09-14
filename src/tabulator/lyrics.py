# -*- coding: utf-8 -*-
"""Lyrics of a Guitar Pro 8 score, one token per beat.

    python src/tabulator/lyrics.py add     in.gp out.gp lyrics.json [--raw] [--dry]
    python src/tabulator/lyrics.py modify  in.gp out.gp --shift N [--from BAR]
    python src/tabulator/lyrics.py refresh in.gp [out.gp] [--write]

add takes lyrics the score does not have yet and decides the spacing from where
each line starts: lyrics.json is a list of [bar, text], bar 0-based. Once the
words are in the score the work is nudging, not rewriting, so modify moves what
is already placed, by hand or to undo the displacement a bar edit caused, and
leaves the spacing alone. refresh answers whether the words are still on the
staff and respells the track block from the beats that hold them.

Guitar Pro's own dispatch (track level <Lyrics>, what the Lyrics window edits)
walks the beats and skips every rest, so a syllable can never land on a rest and
a line that should start before the first chord has nowhere to go. This writes
the tokens straight onto the beats instead, as beat level <Lyrics><Line>, which
is the form Guitar Pro itself saves after a manual nudge. One token per beat of
voice 0, rests included. The track level block is written too, spelled the way
dispatch would need it, so an edit that moves bars rebuilds the same words
instead of clearing every beat.

Tokens: every CJK character is its own token, an ASCII word stays whole, PLUS
glues characters onto one beat, DOT leaves a beat blank, and a space only
separates. So "無+心 的+愛" puts "無心" on the rest and "的愛" on the chord after it.
Contract on line breaks: the text is laid out one lyric phrase per line, the
phrases being the song's own short lines, not the bars. A newline separates
tokens exactly like one space and is carried into the Lyrics panel as a line
break, so the panel reads phrase by phrase. The tool never breaks or joins
lines on its own.
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
        elif ch in " \n":
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


def parse(text):
    """Tokens plus the token counts at which the text broke a line."""
    toks, breaks = [], []
    for piece in text.split("\n"):
        toks += tokens(piece)
        breaks.append(len(toks))
    return toks, breaks[:-1]


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


def track_text(placed, breaks=()):
    """The same line as Guitar Pro's own dispatch would need to spell it.

    Dispatch walks note beats only, so a token sitting on a rest has no slot of
    its own and rides along on the next note beat. Line breaks land after the
    same words they followed in the source.
    """
    out, pending, cut = [], "", set()
    for i, (tok, rest) in enumerate(placed):
        if i in breaks:
            cut.add(len(out))
        if rest:
            pending += tok
            continue
        out.append(pending + tok)
        pending = ""
    if pending:
        out.append(pending)
    while out and not out[-1]:
        out.pop()
    text = ""
    for i, tok in enumerate(out):
        if i:
            text += "\n" if i in cut else " "
        text += tok
    return text


def track_lyrics(xml, track, rows):
    """Fill the track block too, so an edit that re-dispatches finds the words.

    Beat level <Lyrics> is only the cached dispatch. Guitar Pro rebuilds it from
    this block whenever bars move, so leaving it empty drops every syllable in
    the score at once.
    """
    entries = [f"<Line>\n<Text><![CDATA[{text}]]></Text>\n<Offset>{bar}</Offset>\n</Line>"
               for bar, text in rows[:LINES]]
    entries += [BLANK_LINE] * (LINES - len(entries))
    block = '<Lyrics dispatched="true">\n' + "\n".join(entries) + "\n</Lyrics>"
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


def current(xml, track):
    """The table plus {slot: {line: token}} for the beats holding words now."""
    table = slots(xml, track)
    bodies = _table(xml, "Beats", "Beat")
    held = {}
    for i, (bar, vid, pos, bid, rest) in enumerate(table):
        block = re.search(r"<Lyrics>(.*?)</Lyrics>", bodies.get(bid, ""), re.S)
        if not block:
            continue
        tokens = re.findall(r"<Line><!\[CDATA\[(.*?)\]\]></Line>", block.group(1))
        got = {n: t for n, t in enumerate(tokens) if t}
        if got:
            held[i] = got
    return table, held


def regroup(table, per_slot):
    """Track block rows spelled from what the beats actually hold."""
    rows = []
    for line in range(LINES):
        used = sorted(i for i, m in per_slot.items() if line in m)
        if not used:
            rows.append((0, ""))
            continue
        first, last = used[0], used[-1]
        placed = [(per_slot.get(i, {}).get(line, ""), table[i][4]) for i in range(first, last + 1)]
        rows.append((table[first][0], track_text(placed)))
    return rows


def track_block(xml, track):
    """The lines the Lyrics window shows, as [(bar, text), ...]."""
    spans = list(re.finditer(r'<Track id="\d+">(.*?)</Track>', xml, re.S))
    if track >= len(spans):
        sys.exit(f"no track {track} in score")
    found = re.search(r"<Lyrics\b.*?</Lyrics>", spans[track].group(1), re.S)
    if not found:
        return []
    return [(int(off), text) for text, off in
            re.findall(r"<Text><!\[CDATA\[(.*?)\]\]></Text>\s*<Offset>(-?\d+)</Offset>",
                       found.group(0), re.S)]


def cmd_add(args):
    with open(args.lyrics, encoding="utf-8") as f:
        raw = json.load(f)
    parsed = [(int(bar), *((text.split(" "), []) if args.raw else parse(text))) for bar, text in raw]
    lines = [(bar, toks) for bar, toks, _ in parsed]

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
    xml = track_lyrics(xml, args.track, [(bar, track_text(p, set(br))) for (bar, _, br), p in zip(parsed, report)])
    xml = inject(xml, {ids[i]: v for i, v in per_slot.items()})
    save_gpif(args.src, args.out, xml)
    print(f"{len(lines)} lines on {len(per_slot)} beats -> {args.out}")


def cmd_modify(args):
    xml = load_gpif(args.src)
    table, held = current(xml, args.track)
    if not held:
        sys.exit("no beat carries a lyric; use add, or refresh to see what is there")
    first = next((i for i, s in enumerate(table) if s[0] == args.start), 0) if args.start else 0
    moved = {}
    for slot, tokens in sorted(held.items(), reverse=args.shift > 0):
        target = slot + args.shift if slot >= first else slot
        if not 0 <= target < len(table):
            sys.exit(f"shift {args.shift:+d} puts a token off the end of the track")
        if target in moved:
            sys.exit(f"shift {args.shift:+d} lands two tokens on beat {target}")
        moved[target] = tokens
    print(f"  {sum(1 for s in held if s >= first)} of {len(held)} lyric beats shifted {args.shift:+d}")
    if args.dry:
        return
    xml, ids = unshare(xml, table, moved)
    xml = track_lyrics(xml, args.track, regroup(table, moved))
    xml = inject(xml, {ids[i]: v for i, v in moved.items()})
    save_gpif(args.src, args.out, xml)
    print(f"{len(moved)} lyric beats -> {args.out}")


def cmd_refresh(args):
    xml = load_gpif(args.src)
    table, held = current(xml, args.track)
    block = [(bar, text) for bar, text in track_block(xml, args.track) if text.strip()]
    beats = sum(len(v) for v in held.values())
    print(f"  track block {len(block)} line(s), beats holding words {beats}")
    if block and not beats:
        sys.exit("the Lyrics window has text and no beat carries it: the words are off the staff")
    if not args.write:
        return
    if not args.out:
        sys.exit("refresh --write needs an out.gp")
    xml = track_lyrics(xml, args.track, regroup(table, held))
    save_gpif(args.src, args.out, xml)
    print(f"track block respelled from {beats} beats -> {args.out}")


def main():
    ap = argparse.ArgumentParser()
    verb = ap.add_subparsers(dest="verb", required=True)

    new = verb.add_parser("add", help="place lyrics the score does not have yet")
    new.add_argument("src")
    new.add_argument("out")
    new.add_argument("lyrics")
    new.add_argument("--raw", action="store_true", help="text is already one token per beat, space separated, empty token for a blank beat")
    new.add_argument("--dry", action="store_true", help="print the placement, write nothing")
    new.set_defaults(run=cmd_add)

    nudge = verb.add_parser("modify", help="move words already placed, spacing untouched")
    nudge.add_argument("src")
    nudge.add_argument("out")
    nudge.add_argument("--shift", type=int, required=True, help="beats to move by, negative moves earlier")
    nudge.add_argument("--from", dest="start", type=int, default=0, help="0-based bar to start moving at")
    nudge.add_argument("--dry", action="store_true")
    nudge.set_defaults(run=cmd_modify)

    check = verb.add_parser("refresh", help="are the words still on the staff, and respell the track block")
    check.add_argument("src")
    check.add_argument("out", nargs="?")
    check.add_argument("--write", action="store_true", help="respell the track block from the beats")
    check.set_defaults(run=cmd_refresh)

    for parser in (new, nudge, check):
        parser.add_argument("--track", type=int, default=0)
    args = ap.parse_args()
    return args.run(args)


if __name__ == "__main__":
    main()
