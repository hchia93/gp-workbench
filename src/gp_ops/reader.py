"""Read a .gp file into a plain per-measure structure.

Used as ground truth: when a song has both a .gp and the PDF exported from it,
the .gp says exactly what the PDF's ink is supposed to mean.

Usage: gp-workbench gp <file.gp> [--measures A-B]
"""

import re
import zipfile
from fractions import Fraction

VALUES = {"Whole": 1, "Half": 2, "Quarter": 4, "Eighth": 8,
          "16th": 16, "32nd": 32, "64th": 64, "128th": 128}
TECHNIQUES = ("Muted", "PalmMuted", "Brush", "HopoOrigin", "HopoDestination",
              "Slide", "Harmonic", "PickStroke")


class Beat:
    def __init__(self, value, dots, tuplet, notes, techniques):
        self.value = value
        self.dots = dots
        self.tuplet = tuplet              # (num, den) or None
        self.notes = notes                # list of (string, fret)
        self.techniques = techniques

    @property
    def length(self):
        base = Fraction(1, VALUES[self.value])
        if self.dots:
            base *= Fraction(2) - Fraction(1, 2 ** self.dots)
        if self.tuplet:
            base *= Fraction(self.tuplet[1], self.tuplet[0])
        return base

    def __repr__(self):
        pitch = "+".join(f"s{s}f{f}" for s, f in self.notes) or "rest"
        dot = "." * self.dots
        tup = f"[{self.tuplet[0]}:{self.tuplet[1]}]" if self.tuplet else ""
        return f"{self.value}{dot}{tup} {pitch}"


class Measure:
    def __init__(self, index, signature):
        self.index = index
        self.signature = signature
        self.voices = {}                  # voice number -> [Beat]

    @property
    def total(self):
        return {v: sum((b.length for b in beats), Fraction(0))
                for v, beats in sorted(self.voices.items())}

    @property
    def closed(self):
        return all(t == self.signature for t in self.total.values()) if self.voices else False


def _table(xml, plural, single):
    m = re.search(r"<%s>\s*(<%s id=.*?)</%s>" % (plural, single, plural), xml, re.S)
    if not m:
        return {}
    out = {}
    for item in re.finditer(r'<%s id="(\d+)"\s*(?:/>|>(.*?)</%s>)' % (single, single),
                            m.group(1), re.S):
        out[int(item.group(1))] = item.group(2) or ""
    return out


def _refs(body, tag):
    m = re.search(r"<%s>([\d\s-]*)</%s>" % (tag, tag), body)
    return [int(v) for v in m.group(1).split()] if m and m.group(1).strip() else []


def read(path, track=0):
    xml = zipfile.ZipFile(path).read("Content/score.gpif").decode("utf-8")
    bars = _table(xml, "Bars", "Bar")
    voices = _table(xml, "Voices", "Voice")
    beats = _table(xml, "Beats", "Beat")
    notes = _table(xml, "Notes", "Note")
    rhythms = _table(xml, "Rhythms", "Rhythm")

    def note_of(nid):
        body = notes.get(nid, "")
        s = re.search(r'name="String">\s*<String>(\d+)', body)
        f = re.search(r'name="Fret">\s*<Fret>(\d+)', body)
        if not (s and f):
            return None
        return (6 - int(s.group(1)), int(f.group(1)))

    def rhythm_of(rid):
        body = rhythms.get(rid, "")
        value = re.search(r"<NoteValue>(\w+)</NoteValue>", body)
        dots = re.search(r'<AugmentationDot count="(\d+)"', body)
        tup = re.search(r'<PrimaryTuplet num="(\d+)" den="(\d+)"', body)
        return (value.group(1) if value else "Quarter",
                int(dots.group(1)) if dots else 0,
                (int(tup.group(1)), int(tup.group(2))) if tup else None)

    out = []
    index = 0
    signature = Fraction(4, 4)
    for mb in re.finditer(r"<MasterBar>(.*?)</MasterBar>", xml, re.S):
        body = mb.group(1)
        t = re.search(r"<Time>(\d+)/(\d+)</Time>", body)
        if t:
            signature = Fraction(int(t.group(1)), int(t.group(2)))
        bar_ids = _refs(body, "Bars")
        if track >= len(bar_ids):
            continue
        index += 1
        measure = Measure(index, signature)
        for slot, vid in enumerate(_refs(bars.get(bar_ids[track], ""), "Voices"), 1):
            if vid == -1:
                continue
            seq = []
            for bid in _refs(voices.get(vid, ""), "Beats"):
                bbody = beats.get(bid, "")
                rm = re.search(r'<Rhythm ref="(\d+)"', bbody)
                value, dots, tup = rhythm_of(int(rm.group(1))) if rm else ("Quarter", 0, None)
                ns = [note_of(n) for n in _refs(bbody, "Notes")]
                tech = [t for t in TECHNIQUES
                        if any(f'name="{t}"' in notes.get(n, "") for n in _refs(bbody, "Notes"))
                        or f'name="{t}"' in bbody]
                seq.append(Beat(value, dots, tup, [n for n in ns if n], tech))
            if seq:
                measure.voices[slot] = seq
        out.append(measure)
    return out
