"""Turn a decoded PDF into a .gp file.

This is the step that makes the project produce something rather than report a
percentage. Even a partly wrong .gp is more useful than an accuracy number: it
opens in Guitar Pro, the errors are visible at a glance, and a corrected save
becomes new ground truth.

The writer works by template, rewriting only Content/score.gpif and copying every
other zip entry through, so the undocumented binary blobs stay valid. That means
a .gp has to be supplied to copy from.
"""

import os
import re

from .gp.write import Beat, Note, build
from .score.rhythm_tab import analyse, measure_sequence

# gpwrite spells note values the same way the decoders do
DOTTED = {0: False, 1: True}


def pages_of(path):
    return len(re.findall(rb"/Type\s*/Page[^s]", open(path, "rb").read())) or 1


def decode(pdf):
    """Every measure of the score, in reading order, empty ones included."""
    measures = []
    signature = None
    for page in range(pages_of(pdf)):
        try:
            systems, staves, glyphs = analyse(pdf, page)
        except Exception:
            continue
        if signature is None:
            from .score.rhythm_notation import read_time_signature
            signature = read_time_signature(staves, glyphs, text=True)[1]
        for staff, cols, beams, flags in systems:
            measures += measure_sequence(staff, cols, signature)
    return measures, signature or "4/4"


def to_song(measures, signature, title, artist, tempo=90, capo=0):
    """Shape the decoded measures the way gpwrite.build expects."""
    bars = []
    for seq in measures:
        beats = []
        for col in seq:
            notes = [Note(string, fret) for string, fret in col["notes"]]
            if not notes:
                continue
            beats.append(Beat(col["value"], notes, dotted=col["dots"] > 0))
        if not beats:
            # gpwrite has no rest yet, so an empty measure is written as silence
            beats.append(Beat("Whole", [Note(6, 0, muted=True)]))
        bars.append({"beats": beats})
    return {"title": title, "artist": artist, "tabber": "score-pdf-to-gp",
            "tempo": tempo, "time": signature, "capo": capo, "bars": bars}


def convert(pdf, template, out, title=None, artist="", tempo=90, capo=0):
    measures, signature = decode(pdf)
    stem = os.path.splitext(os.path.basename(pdf))[0]
    song = to_song(measures, signature,
                   title or stem.split(" - ")[0].strip(),
                   artist or (stem.split(" - ")[1].strip() if " - " in stem else ""),
                   tempo, capo)
    notes, beats, bars = build(template, song, out)
    return {"measures": bars, "beats": beats, "notes": notes,
            "time": signature, "out": out}
