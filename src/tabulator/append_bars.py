# -*- coding: utf-8 -*-
"""Append bars to a Guitar Pro 7/8 score without rebuilding what is already there.

    python src/tabulator/append_bars.py in.gp out.gp section.json

section.json is {"bars": [[beat, ...], ...]}, a beat being
{"v": "Eighth", "dot": false, "n": [[string, fret], ...]} with string 1 = high E
and an empty list for a rest. The writer rebuilds a whole score from a template
and drops anything Guitar Pro added on its own, so a score that has been through
the program grows by patching its id tables instead.
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("section")
    args = ap.parse_args()

    with open(args.section, encoding="utf-8") as f:
        bars = json.load(f)["bars"]

    xml = load_gpif(args.src)
    capo = int(re.search(r'<Property name="CapoFret">\s*<Fret>(\d+)</Fret>', xml).group(1))
    key = re.search(r"<MasterBar>\s*(<Key>.*?</Key>)", xml, re.S).group(1)
    time = re.search(r"<MasterBar>.*?<Time>([\d/]+)</Time>", xml, re.S).group(1)

    nid, bid, vid, barid = (last_id(xml, t) for t in ("Note", "Beat", "Voice", "Bar"))
    notes, beats, voices, bar_entries, masterbars = [], [], [], [], []
    for bar in bars:
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
            beats.append(re.sub(r'<Rhythm ref="\d+" />', f'<Rhythm ref="{ref}" />', body))
        vid += 1
        barid += 1
        voices.append(f'<Voice id="{vid}">\n<Beats>{" ".join(str(i) for i in beat_ids)}</Beats>\n</Voice>')
        bar_entries.append(f'<Bar id="{barid}">\n<Clef>G2</Clef>\n<Voices>{vid} -1 -1 -1</Voices>\n</Bar>')
        masterbars.append(f"<MasterBar>\n{key}\n<Time>{time}</Time>\n<Bars>{barid}</Bars>\n</MasterBar>")

    xml = append_table(xml, "Notes", notes)
    xml = append_table(xml, "Beats", beats)
    xml = append_table(xml, "Voices", voices)
    xml = append_table(xml, "Bars", bar_entries)
    xml = append_table(xml, "MasterBars", masterbars)

    save_gpif(args.src, args.out, xml)
    print(f"+{len(bars)} bars, {len(beats)} beats, {len(notes)} notes -> {args.out}")


if __name__ == "__main__":
    main()
