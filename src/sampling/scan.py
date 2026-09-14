# -*- coding: utf-8 -*-
"""Batch analysis: read a tree of .gp files and pack the figures they use.

    python src/sampling/scan.py "D:/scores/**/*.gp"

An entry is one chord plus one way the library breaks it up. The figure keeps
only which slot is plucked when, the frets thrown away, so an entry called up
for D7M lays onto any other shape just as well. The pack carries no notes and no
lyric text. Regenerate it whenever the library grows.

A figure can also come in from outside this scan, read off a screenshot or
checked against a recording; the pack takes an entry either way.
"""

import collections
import glob
import gzip
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(HERE, "corpus.db")
VALUE = {"Whole": 16, "Half": 8, "Quarter": 4, "Eighth": 2, "16th": 1, "32nd": 0.5, "64th": 0.25}
SHORT = {16: "w", 12: "h.", 8: "h", 6: "q.", 4: "q", 3: "e.", 2: "e", 1.5: "s.", 1: "s", 0.5: "t"}


def gpif(path):
    archive = zipfile.ZipFile(path)
    for name in archive.namelist():
        if name.endswith("score.gpif"):
            return archive.read(name).decode("utf-8", "replace")
    return None


def diagrams(xml):
    """Diagram id -> chord name, the spelling Guitar Pro drew into the file."""
    found = {}
    for item in re.finditer(r'<Item id="(\d+)" name="([^"]*)">(.*?)</Item>', xml, re.S):
        cid, name, body = item.groups()
        if "<Diagram" in body:
            found[cid] = name
    return found


def read(xml):
    """Bars as [[{d, n, c, l}, ...], ...] plus the time signature of each."""
    rhythm = {}
    for rid, body in re.findall(r'<Rhythm id="(\d+)">(.*?)</Rhythm>', xml, re.S):
        value = re.search(r"<NoteValue>(\w+)</NoteValue>", body)
        dot = re.search(r'<AugmentationDot count="(\d+)"', body)
        if value and value.group(1) in VALUE:
            rhythm[rid] = VALUE[value.group(1)] * (1.5 if dot and int(dot.group(1)) else 1)
    note = {}
    for nid, body in re.findall(r'<Note id="(\d+)">(.*?)</Note>', xml, re.S):
        string = re.search(r'name="String">\s*<String>(-?\d+)</String>', body)
        fret = re.search(r'name="Fret">\s*<Fret>(-?\d+)</Fret>', body)
        if string and fret:
            note[nid] = 6 - int(string.group(1))          # 1 = high E
    beat = {}
    for bid, body in re.findall(r'<Beat id="(\d+)">(.*?)</Beat>', xml, re.S):
        ref = re.search(r'<Rhythm ref="(\d+)"', body)
        notes = re.search(r"<Notes>(.*?)</Notes>", body)
        chord = re.search(r"<Chord><!\[CDATA\[(.*?)\]\]></Chord>", body)
        lyric = re.findall(r"<Line><!\[CDATA\[(.*?)\]\]></Line>", body)
        beat[bid] = {"d": rhythm.get(ref.group(1) if ref else None, 0),
                     "n": sorted({note[i] for i in (notes.group(1).split() if notes else []) if i in note}),
                     "c": chord.group(1) if chord else None,
                     "l": sum(1 for token in lyric if token.strip())}
    voice = {v: b.split() for v, b in re.findall(r'<Voice id="(\d+)">\s*<Beats>(.*?)</Beats>', xml, re.S)}
    owner = {b: re.search(r"<Voices>(-?\d+)", body).group(1)
             for b, body in re.findall(r'<Bar id="(\d+)">(.*?)</Bar>', xml, re.S)}
    bars, times = [], []
    for master in re.findall(r"<MasterBar>.*?</MasterBar>", xml, re.S):
        time = re.search(r"<Time>([\d/]+)</Time>", master)
        times.append(time.group(1) if time else "?")
        ids = re.search(r"<Bars>([\d\s]+)</Bars>", master)
        vid = owner.get(ids.group(1).split()[0]) if ids else None
        bars.append([beat[b] for b in voice.get(vid, []) if b in beat])
    return bars, times


def figure(run):
    """Beats as (value, slots), strings replaced by thumb and finger slots.

    Slot order is the one apply expects: thumb from the lowest played bass
    string up, fingers from the highest treble string down. A figure sampled on
    one shape then lays onto any other.
    """
    bass = sorted({s for bt in run for s in bt["n"] if s >= 4}, reverse=True)
    treble = sorted({s for bt in run for s in bt["n"] if s <= 3})
    out = []
    for bt in run:
        if not bt["d"]:
            return None
        slots = {("T%d" % bass.index(s)) if s >= 4 else ("F%d" % treble.index(s)) for s in bt["n"]}
        out.append((bt["d"], tuple(sorted(slots))))
    return tuple(out)


def render(fig):
    return " ".join("%s:%s" % (SHORT.get(d, str(d)), "+".join(s) or "-") for d, s in fig)


def spans(bar, carried):
    """Split a bar where its chord mark changes: [(chord, [beat, ...]), ...]."""
    out, current, run = [], carried, []
    for bt in bar:
        if bt["c"] is not None and bt["c"] != current:
            if run:
                out.append((current, run))
            current, run = bt["c"], []
        run.append(bt)
    if run:
        out.append((current, run))
    return out, current


def scan(paths):
    entries = collections.Counter()
    entry_song = collections.defaultdict(set)
    figures = collections.Counter()
    figure_song = collections.defaultdict(set)
    skeletons = collections.Counter()
    skeleton_song = collections.defaultdict(set)
    names = collections.Counter()
    shapes = collections.defaultdict(collections.Counter)
    songs, broken = [], []
    for path in paths:
        tag = os.path.basename(path)[:-3]
        try:
            xml = gpif(path)
            if xml is None:
                broken.append(tag)
                continue
            bars, times = read(xml)
        except Exception as exc:
            broken.append("%s (%s)" % (tag, type(exc).__name__))
            continue
        named = diagrams(xml)
        for item in re.finditer(r'<Item id="\d+" name="([^"]*)">(.*?)</Item>', xml, re.S):
            name, body = item.groups()
            if "<Diagram" not in body:
                continue
            names[name] += 1
            frets = re.findall(r'<Fret string="(\d+)" fret="(\d+)"/>', body)
            shapes[name]["".join("%s.%s" % (s, f) for s, f in sorted(frets))] += 1
        carried = None
        for bar in bars:
            if not bar or len(bar) > 32:
                carried = None
                continue
            runs, carried = spans(bar, carried)
            for chord, run in runs:
                fig = figure(run)
                if not fig:
                    continue
                drawn = render(fig)
                figures[drawn] += 1
                figure_song[drawn].add(tag)
                skeleton = " ".join(SHORT.get(d, str(d)) for d, s in fig)
                skeletons[skeleton] += 1
                skeleton_song[skeleton].add(tag)
                label = named.get(chord)
                if label:
                    entries[(label, drawn, sum(d for d, s in fig))] += 1
                    entry_song[(label, drawn)].add(tag)
        working = re.search(r'name="DiagramWorkingSet">\s*<Items\s*(/?)>', xml)
        dispatched = re.search(r'<Lyrics\s+dispatched="(\w+)"', xml)
        capo = re.search(r'name="CapoFret">\s*<Fret>(\d+)</Fret>', xml)
        songs.append({
            "s": tag,
            "b": len(bars),
            "t": sorted(set(times)),
            "m": sum(1 for b in bars if any(bt["c"] for bt in b)),
            "d": len(named),
            "w": bool(working and not working.group(1)),
            "y": sum(1 for b in bars for bt in b if bt["l"]),
            "p": dispatched.group(1) if dispatched else None,
            "c": int(capo.group(1)) if capo else 0,
        })
    return {
        "version": 2,
        "songs": songs,
        "unreadable": broken,
        "entries": numbered(entries, entry_song),
        "figures": rank(figures, figure_song),
        "skeletons": rank(skeletons, skeleton_song),
        "chords": sorted(([name, uses, shapes[name].most_common(4)] for name, uses in names.items()),
                         key=lambda row: -row[1]),
    }


def numbered(counter, owners):
    """[id, chord, figure, length, uses, scores], the id callable by hand.

    Forms of one chord rank by how many scores use them, so D7M@1 is the way
    the library breaks up D7M most widely, not merely most often. The separator
    is @ because a chord name already owns # and /.
    """
    rows = [[chord, drawn, length, uses, len(owners[(chord, drawn)])]
            for (chord, drawn, length), uses in counter.items()]
    rows.sort(key=lambda row: (row[0], -row[4], -row[3]))
    out, seen = [], collections.Counter()
    for chord, drawn, length, uses, scores in rows:
        seen[chord] += 1
        out.append(["%s@%d" % (chord, seen[chord]), chord, drawn, length, uses, scores])
    out.sort(key=lambda row: (-row[5], -row[4]))
    return out


def rank(counter, owners):
    return sorted(([key, uses, len(owners[key])] for key, uses in counter.items()),
                  key=lambda row: (-row[2], -row[1]))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    paths = []
    for arg in sys.argv[1:]:
        paths += glob.glob(arg, recursive=True)
    paths = sorted(set(paths))
    if not paths:
        sys.exit("no .gp matched")
    pack = scan(paths)
    raw = json.dumps(pack, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with gzip.GzipFile(PACK, "wb", compresslevel=9, mtime=0) as out:
        out.write(raw)
    print("%d scores, %d unreadable, %d entries over %d chords, %d figures, %d skeletons"
          % (len(pack["songs"]), len(pack["unreadable"]), len(pack["entries"]),
             len(pack["chords"]), len(pack["figures"]), len(pack["skeletons"])))
    print("%s  %d bytes packed from %d" % (PACK, os.path.getsize(PACK), len(raw)))


if __name__ == "__main__":
    main()
