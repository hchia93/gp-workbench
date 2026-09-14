# -*- coding: utf-8 -*-
"""Bars of a Guitar Pro 7/8 score, without rebuilding what is already there.

    python src/tabulator/bars.py add     in.gp out.gp section.json
    python src/tabulator/bars.py modify  in.gp out.gp section.json --from BAR
    python src/tabulator/bars.py replace in.gp out.gp section.json --from BAR

add puts the section after the last bar. modify and replace rewrite from BAR
(1-based) on: the bars keep their ids and their voices point at fresh beats,
and bars after the section stay as they are. The two differ in what happens to
the payload of a beat the new bar has no room for: modify refuses, replace
drops it.

section.json is {"bars": [[beat, ...], ...]}, a beat being
{"v": "Eighth", "dot": false, "n": [[string, fret], ...]} with string 1 = high E
and an empty list for a rest. A beat may also carry "chord": "<diagram id>" to
set its chord label or "chord": null to clear one. The writer rebuilds a whole
score from a template and drops anything Guitar Pro added on its own, so a score
that has been through the program grows by patching its id tables instead.

Rewritten beats are built fresh, so the payload Guitar Pro hangs on a beat and
the writer cannot regenerate is carried across position by position. Lyrics and
chord labels live on the beat, not on the bar, so rebuilding a bar without the
carry strips the words off the staff without saying so. The carry is
unconditional; only replace is allowed to lose one, and it says which.
"""

import argparse
import io
import json
import re
import sys

sys.path.insert(0, ".")

from src.gp_ops import writer
from src.gp_ops.patcher import load_gpif, save_gpif

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def last_id(xml, tag):
    return max(int(i) for i in re.findall(r'<%s id="(\d+)"' % tag, xml))


def rhythm_ref(xml, value, dotted):
    """Reuse the score's own rhythm entry, appending one when the value is new."""
    for rid, body in re.findall(r'<Rhythm id="(\d+)">(.*?)</Rhythm>', xml, re.S):
        nv = re.search(r"<NoteValue>(\w+)</NoteValue>", body)
        dots = re.search(r'<AugmentationDot count="(\d+)"', body)
        if nv and nv.group(1) == value and bool(dots and int(dots.group(1))) == dotted:
            return xml, int(rid)
    rid = last_id(xml, "Rhythm") + 1
    dot = '\n<AugmentationDot count="1" />' if dotted else ""
    entry = f'<Rhythm id="{rid}">\n<NoteValue>{value}</NoteValue>{dot}\n</Rhythm>'
    return xml.replace("</Rhythms>", entry + "\n</Rhythms>", 1), rid


def append_table(xml, plural, entries):
    # the id table closes last; the same tag names the reference lists sitting above it
    cut = xml.rfind(f"</{plural}>")
    return xml[:cut] + "\n".join(entries) + "\n" + xml[cut:]


# Beat children the writer does not emit. Guitar Pro hangs the words and the
# chord label on the beat, so a rebuilt beat loses both unless grafted back on.
CARRY = ("Chord", "Lyrics")


def beat_payload(xml):
    """beat id -> {tag: element} for everything the writer cannot regenerate."""
    out = {}
    for bid, body in re.findall(r'<Beat id="(\d+)">(.*?)</Beat>', xml, re.S):
        keep = {}
        for tag in CARRY:
            found = re.search(r"<%s>.*?</%s>" % (tag, tag), body, re.S)
            if found:
                keep[tag] = found.group(0)
        if keep:
            out[bid] = keep
    return out


def graft(beat_xml, payload):
    """Put carried elements back where Guitar Pro writes them."""
    chord = payload.get("Chord")
    if chord:
        beat_xml = beat_xml.replace("<Notes>", chord + "\n<Notes>", 1)
    lyrics = payload.get("Lyrics")
    if lyrics:
        beat_xml = beat_xml.replace("</Properties>\n</Beat>", "</Properties>\n" + lyrics + "\n</Beat>", 1)
    return beat_xml


def sweep(xml):
    """Drop beats and notes no voice points at any more after a rewrite."""
    live_beats = set()
    for body in re.findall(r"<Voice id=\"\d+\">(.*?)</Voice>", xml, re.S):
        live_beats.update(re.search(r"<Beats>(.*?)</Beats>", body).group(1).split())
    live_notes = set()
    for bid, body in re.findall(r'<Beat id="(\d+)">(.*?)</Beat>', xml, re.S):
        if bid in live_beats:
            ns = re.search(r"<Notes>(.*?)</Notes>", body)
            live_notes.update(ns.group(1).split() if ns else [])
    xml = re.sub(r'<Beat id="(\d+)">.*?</Beat>\n?', lambda m: "" if m.group(1) not in live_beats else m.group(0), xml, flags=re.S)
    xml = re.sub(r'<Note id="(\d+)">.*?</Note>\n?', lambda m: "" if m.group(1) not in live_notes else m.group(0), xml, flags=re.S)
    return xml


def run(args):
    with open(args.section, encoding="utf-8") as f:
        bars = json.load(f)["bars"]

    xml = load_gpif(args.src)
    capo = int(re.search(r'<Property name="CapoFret">\s*<Fret>(\d+)</Fret>', xml).group(1))
    key = re.search(r"<MasterBar>\s*(<Key>.*?</Key>)", xml, re.S).group(1)
    time = re.search(r"<MasterBar>.*?<Time>([\d/]+)</Time>", xml, re.S).group(1)

    nid, bid, vid, barid = (last_id(xml, t) for t in ("Note", "Beat", "Voice", "Bar"))
    masters = re.findall(r"<MasterBar>.*?</MasterBar>", xml, re.S)
    payloads = beat_payload(xml)
    reuse, reuse_beats = [], []
    if args.start:
        if args.start > len(masters):
            sys.exit(f"--from {args.start}: score has {len(masters)} bars")
        for mb in masters[args.start - 1:]:
            bar_id = re.search(r"<Bars>(\d+)", mb).group(1)
            voice_id = re.search(r'<Bar id="%s">.*?<Voices>(\d+)' % bar_id, xml, re.S).group(1)
            reuse.append(int(voice_id))
            reuse_beats.append(re.search(r'<Voice id="%s">\s*<Beats>(.*?)</Beats>' % voice_id,
                                         xml, re.S).group(1).split())

    # A rebuilt bar shorter than the one it replaces cannot hold every payload.
    # Name the bar and the beat before anything is written.
    for index, old in enumerate(reuse_beats[:len(bars)]):
        for old_bid in old[len(bars[index]):]:
            if old_bid in payloads and not args.drop:
                sys.exit("bar %d: beat %s carries %s and the new bar has only %d beats; "
                         "lengthen it or use replace"
                         % (args.start + index, old_bid,
                            "+".join(sorted(payloads[old_bid])), len(bars[index])))
    notes, beats, voices, bar_entries, masterbars = [], [], [], [], []
    carried = 0
    for index, bar in enumerate(bars):
        beat_ids = []
        for beat in bar:
            xml, ref = rhythm_ref(xml, beat.get("v", "Eighth"), bool(beat.get("dot")))
            note_ids = []
            for string, fret in beat.get("n", []):
                nid += 1
                note_ids.append(nid)
                notes.append(writer._note_xml(nid, writer.Note(string, fret), capo))
            bid += 1
            beat_ids.append(bid)
            body = writer._beat_xml(bid, writer.Beat(beat.get("v", "Eighth"), [], bool(beat.get("dot"))), note_ids)
            body = re.sub(r'<Rhythm ref="\d+" />', f'<Rhythm ref="{ref}" />', body)
            old = reuse_beats[index] if index < len(reuse_beats) else []
            slot = len(beat_ids) - 1
            keep = dict(payloads[old[slot]]) if slot < len(old) and old[slot] in payloads else {}
            if "chord" in beat:
                keep.pop("Chord", None)
                if beat["chord"] is not None:
                    keep["Chord"] = "<Chord><![CDATA[%s]]></Chord>" % beat["chord"]
            carried += len(keep)
            beats.append(graft(body, keep))
        ids = " ".join(str(i) for i in beat_ids)
        if index < len(reuse):
            xml = re.sub(r'(<Voice id="%d">\s*<Beats>)[^<]*(</Beats>)' % reuse[index],
                         lambda m: m.group(1) + ids + m.group(2), xml, count=1)
            continue
        vid += 1
        barid += 1
        voices.append(f'<Voice id="{vid}">\n<Beats>{ids}</Beats>\n</Voice>')
        bar_entries.append(f'<Bar id="{barid}">\n<Clef>G2</Clef>\n<Voices>{vid} -1 -1 -1</Voices>\n</Bar>')
        masterbars.append(f"<MasterBar>\n{key}\n<Time>{time}</Time>\n<Bars>{barid}</Bars>\n</MasterBar>")

    xml = append_table(xml, "Notes", notes)
    xml = append_table(xml, "Beats", beats)
    xml = append_table(xml, "Voices", voices)
    xml = append_table(xml, "Bars", bar_entries)
    xml = append_table(xml, "MasterBars", masterbars)
    if reuse:
        xml = sweep(xml)

    before = sum(len(v) for v in payloads.values())
    after = sum(len(v) for v in beat_payload(xml).values())
    if after < before and not args.drop:
        sys.exit(f"payload carry lost {before - after} element(s), refusing to write {args.out}")

    save_gpif(args.src, args.out, xml)
    print(f"{len(reuse)} bars rewritten, {len(bar_entries)} appended, {len(beats)} beats, "
          f"{len(notes)} notes, {carried} payload grafted, {after}/{before} kept -> {args.out}")


def main():
    ap = argparse.ArgumentParser()
    verb = ap.add_subparsers(dest="verb", required=True)
    for name, helptext in (("add", "put the section after the last bar"),
                           ("modify", "rewrite from --from on, every payload carried or it stops"),
                           ("replace", "rewrite from --from on, dropping a payload that no longer fits")):
        p = verb.add_parser(name, help=helptext)
        p.add_argument("src")
        p.add_argument("out")
        p.add_argument("section")
        if name != "add":
            p.add_argument("--from", dest="start", type=int, required=True, help="1-based bar to rewrite from")
        p.set_defaults(run=run, start=0, drop=(name == "replace"))
    args = ap.parse_args()
    return args.run(args)


if __name__ == "__main__":
    main()
