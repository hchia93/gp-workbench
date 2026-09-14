# -*- coding: utf-8 -*-
"""Ways the library already breaks a chord up, packed by scan.py.

    from src import sampling
    sampling.call("D7M")         every form the library uses for D7M
    sampling.call("D7M@1")       the one it uses most widely
    sampling.figures(songs=3)    figures at least three scores share
    sampling.dialect()           chord name -> uses, in the library's spelling

An entry is one chord plus one figure. A figure is which slot is plucked when:
thumb T0..T2 from the lowest played bass string up, fingers F0..F2 from the
highest treble string down, frets thrown away. So a form called up for one
chord lays onto any other shape.

corpus.db is gzipped JSON, rebuilt by scan.py. Nothing reads it directly.
"""

import gzip
import json
import os

PACK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus.db")
_pack = None


def load():
    global _pack
    if _pack is None:
        with gzip.open(PACK, "rb") as src:
            _pack = json.loads(src.read().decode("utf-8"))
    return _pack


def call(name, scores=1, uses=1):
    """Entries for a chord, or the single entry an id like D7M@1 names.

    Widest first: the form the most scores agree on, not the one repeated most
    inside a single score. Raise scores to drop the one-off forms.
    """
    rows = load()["entries"]
    field = 0 if "@" in name else 1
    return [dict(zip(FIELDS, row)) for row in rows
            if row[field] == name and row[5] >= scores and row[4] >= uses]


FIELDS = ("id", "chord", "figure", "length", "uses", "scores")


def chords():
    """Chord names that have at least one form on record."""
    return sorted({row[1] for row in load()["entries"]})


def figures(songs=1):
    """[(figure, uses, scores), ...] with the chord dropped."""
    return [tuple(row) for row in load()["figures"] if row[2] >= songs]


def skeletons(songs=1):
    return [tuple(row) for row in load()["skeletons"] if row[2] >= songs]


def dialect():
    """Chord name -> uses, in the spelling Guitar Pro writes into the library."""
    return {name: uses for name, uses, _ in load()["chords"]}


def shapes(name):
    """Fret shapes the library draws for one chord name, most used first."""
    for entry, uses, forms in load()["chords"]:
        if entry == name:
            return [(shape, count) for shape, count in forms]
    return []


def conventions():
    """Aggregate write-back habits: marks per bar, chart filled, lyric carrier."""
    songs = load()["songs"]
    scored = [s for s in songs if s["d"]]
    return {
        "scores": len(songs),
        "with_diagrams": len(scored),
        "chart_filled": sum(1 for s in scored if s["w"]),
        "mark_density": sorted(round(s["m"] / s["b"], 2) for s in scored if s["b"]),
        "beat_lyrics": sum(1 for s in songs if s["y"]),
        "capo_used": sum(1 for s in songs if s["c"]),
    }
