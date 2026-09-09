"""Derive note durations from stems, beams and flags on a notation staff.

Guitar Pro draws a beam as a filled parallelogram, so each beam reaches the
content stream as a pair of near-parallel edges. The number of beams covering a
stem is what distinguishes an eighth from a sixteenth.

Usage: python rhythm.py <file.pdf> [--page N]
"""

import math
from collections import Counter, defaultdict
from fractions import Fraction

from src.converter.pdf.extractor import extract
from src.converter.pdf.staff import find_staves, pair_systems, find_barlines, attach_notes

BEAM_REACH = 24.0        # how far outside the staff a beam can sit
BEAM_MAX_WIDTH = 0.35    # as a fraction of the staff's own x extent
BEAM_MAX_ANGLE = 25.0    # beams slant, but not steeply
BEAM_MIN_EDGE = 2.5      # a beamlet is only ~3.7 long, so this floor must stay low
STEM_MIN = 6.0
NOTEHEAD_BLACK = ""
NOTEHEAD_HALF = ""
NOTEHEAD_WHOLE = ""
AUG_DOT = ""

# beams -> note value, for a stemmed black notehead
VALUE_BY_BEAMS = {0: "Quarter", 1: "Eighth", 2: "16th", 3: "32nd", 4: "64th"}
DENOM = {"Whole": 1, "Half": 2, "Quarter": 4, "Eighth": 8, "16th": 16, "32nd": 32, "64th": 64}


TIMESIG_LO, TIMESIG_HI = 0xE080, 0xE089


def read_time_signature(staves, glyphs, default=Fraction(4, 4), text=False):
    """timeSig digits are stacked at one x: numerator above, denominator below.

    Fraction reduces 4/4 to 1, so the printable form is returned separately.
    """
    def result(frac, label):
        return (frac, label) if text else frac

    digits = [g for g in glyphs if TIMESIG_LO <= ord(g.char) <= TIMESIG_HI]
    if not digits:
        return result(default, f"{default.numerator}/{default.denominator}")
    columns = defaultdict(list)
    for g in digits:
        columns[round(g.x, 0)].append(g)
    for x in sorted(columns):
        col = sorted(columns[x], key=lambda g: -g.y)
        if len(col) < 2:
            continue
        num = ord(col[0].char) - TIMESIG_LO
        den = ord(col[-1].char) - TIMESIG_LO
        if num and den:
            return result(Fraction(num, den), f"{num}/{den}")
    return result(default, f"{default.numerator}/{default.denominator}")


def stem_direction(stem, heads):
    """Up when the free end of the stem points above the noteheads."""
    if not heads:
        return 0
    hi, lo = max(h.y for h in heads), min(h.y for h in heads)
    return 1 if (stem.y1 - hi) >= (lo - stem.y0) else -1


def length_of(col):
    """Note value plus augmentation dots, as a fraction of a whole note."""
    base = Fraction(1, DENOM[col["value"]])
    if col["dots"]:
        base *= Fraction(2) - Fraction(1, 2 ** col["dots"])
    return base


def measure_closure(tab, cols, signature=Fraction(4, 4)):
    """Per-measure, per-voice sum of durations.

    Guitar Pro writes each voice with its own stem direction, so a measure with
    two voices carries the time signature twice over. Summing them together
    never closes; each voice has to close on its own.
    """
    out = []
    for i in range(len(tab.barlines) - 1):
        lo, hi = tab.barlines[i], tab.barlines[i + 1]
        inside = [c for c in cols if lo <= c["x"] < hi]
        voices = defaultdict(list)
        for c in inside:
            voices[c.get("voice", 1)].append(c)
        sums = {v: sum((length_of(c) for c in group), Fraction(0))
                for v, group in sorted(voices.items())}
        total = sum(sums.values(), Fraction(0))
        # single voice with mixed stem directions, or genuine polyphony
        closed = total == signature or (len(sums) > 1 and all(t == signature for t in sums.values()))
        out.append((i + 1, sums, total, closed, len(inside)))
    return out


class Beam:
    def __init__(self, x0, x1, y):
        self.x0, self.x1, self.y = min(x0, x1), max(x0, x1), y

    def covers(self, x):
        return self.x0 - 1.0 <= x <= self.x1 + 1.0

    def __repr__(self):
        return f"beam[{self.x0:.0f}..{self.x1:.0f}]@{self.y:.0f}"


class Stem:
    def __init__(self, x, y0, y1):
        self.x, self.y0, self.y1 = x, min(y0, y1), max(y0, y1)
        self.beams = 0

    @property
    def up(self):
        return None    # direction is resolved against the notehead

    def __repr__(self):
        return f"stem@{self.x:.0f}({self.y0:.0f}-{self.y1:.0f}) beams={self.beams}"


def count_beams(stem, beams, staff):
    """Beams hang off the free end of the stem, all on the same side of the staff.

    Counting every beam that merely shares the stem's x credits an up-stem with
    the beams of a down-stem group underneath it, which shortens the note by a
    whole level.
    """
    n = 0
    for b in beams:
        if not b.covers(stem.x):
            continue
        # a slanted beam's stored y is its midpoint, which can sit past the stem
        # end, so side of the staff is the only bound that holds
        if b.y > staff.top if stem.direction >= 0 else b.y < staff.bottom:
            n += 1
    return n


def angle(seg):
    a = abs(math.degrees(math.atan2(seg.y1 - seg.y0, seg.x1 - seg.x0))) % 180
    return min(a, 180 - a)


def on_any_staff_line(y, staves, tol=0.8):
    return any(abs(y - line) < tol for st in staves for line in st.lines)


def find_beams(staff, segments, staves):
    span = [min(s.x0, s.x1) for s in segments
            if s.horizontal and any(abs(s.y0 - line) < 0.6 for line in staff.lines)]
    span += [max(s.x0, s.x1) for s in segments
             if s.horizontal and any(abs(s.y0 - line) < 0.6 for line in staff.lines)]
    width_cap = (max(span) - min(span)) * BEAM_MAX_WIDTH if span else 1e9
    edges = []
    for s in segments:
        if s.length < BEAM_MIN_EDGE or angle(s) > BEAM_MAX_ANGLE:
            continue
        lo, hi = min(s.y0, s.y1), max(s.y0, s.y1)
        outside = hi < staff.bottom - 0.5 or lo > staff.top + 0.5
        within = lo > staff.bottom - BEAM_REACH and hi < staff.top + BEAM_REACH
        # a rule that runs the width of the system is not a beam
        if s.length > width_cap:
            continue
        if outside and within and not on_any_staff_line((lo + hi) / 2, staves):
            edges.append(s)
    # each beam is a filled shape, so its two long edges share an x span
    buckets = defaultdict(list)
    for s in edges:
        buckets[(round(min(s.x0, s.x1), 0), round(max(s.x0, s.x1), 0))].append(s)
    beams = []
    for (x0, x1), group in buckets.items():
        group.sort(key=lambda s: (s.y0 + s.y1) / 2)
        used = []
        for s in group:
            mid = (s.y0 + s.y1) / 2
            if any(abs(mid - u) < 1.6 for u in used):
                continue
            used.append(mid)
        # a pair of edges is one beam; an odd edge still counts as one
        for i in range(0, len(used), 2):
            beams.append(Beam(x0, x1, used[i]))
    return beams


def find_stems(staff, segments, barlines=()):
    """Verticals that touch the staff, minus the barlines.

    A long stem reaches past both staff edges, so "spans the staff" cannot be
    used to tell a stem from a barline. Excluding the already-detected barline
    x positions is what works.
    """
    stems = []
    for s in segments:
        if not s.vertical or s.length < STEM_MIN:
            continue
        lo, hi = min(s.y0, s.y1), max(s.y0, s.y1)
        if hi < staff.bottom - 1 or lo > staff.top + 1:
            continue
        if any(abs(s.x0 - b) <= 2.0 for b in barlines):
            continue
        stems.append(Stem(round(s.x0, 1), lo, hi))
    stems.sort(key=lambda s: s.x)
    merged = []
    for s in stems:
        if merged and abs(s.x - merged[-1].x) < 1.0:
            merged[-1].y0 = min(merged[-1].y0, s.y0)
            merged[-1].y1 = max(merged[-1].y1, s.y1)
            continue
        merged.append(s)
    return merged


def durations(staff, glyphs, segments, staves, barlines=()):
    """One rhythmic event per stem; noteheads attach to the nearest stem."""
    beams = find_beams(staff, segments, staves)
    stems = find_stems(staff, segments, barlines)

    heads = [g for g in glyphs
             if g.char in (NOTEHEAD_BLACK, NOTEHEAD_HALF, NOTEHEAD_WHOLE)
             and staff.bottom - 14 < g.y < staff.top + 14]
    dots = [g for g in glyphs if g.char == AUG_DOT and staff.bottom - 14 < g.y < staff.top + 14]

    # a stem sits on one side of its noteheads, offset by about a notehead width
    attached = defaultdict(list)
    orphan = []
    for h in heads:
        near = [s for s in stems if abs(s.x - h.x) <= 7.0 and s.y0 - 3 <= h.y <= s.y1 + 3]
        if not near:
            # a stem is drawn only as far as its beam, so it need not reach every
            # notehead of a wide chord; fall back to x proximity alone
            near = [s for s in stems if abs(s.x - h.x) <= 7.0]
        if near:
            attached[min(near, key=lambda s: abs(s.x - h.x)).x].append(h)
        else:
            orphan.append(h)

    # beams sit on the free end of the stem, so direction has to be known first
    for st in stems:
        group = attached.get(st.x) or []
        st.direction = stem_direction(st, group)
        st.beams = count_beams(st, beams, staff)

    out = []
    for st in sorted(stems, key=lambda s: s.x):
        group = attached.get(st.x)
        if not group:
            continue
        if any(g.char == NOTEHEAD_WHOLE for g in group):
            value = "Whole"
        elif any(g.char == NOTEHEAD_HALF for g in group):
            value = "Half"
        else:
            value = VALUE_BY_BEAMS.get(st.beams, "32nd")
        direction = st.direction
        right = max(g.x for g in group)
        hits = {round(d.x, 1) for d in dots
                if 0 < d.x - right < 7 and any(abs(d.y - g.y) < 3 for g in group)}
        ndots = min(len(hits), 2)
        out.append({"x": min(g.x for g in group), "value": value, "dots": ndots,
                    "heads": len(group), "beams": st.beams,
                    "voice": 1 if direction >= 0 else 2})
    for h in orphan:
        # only a hollow notehead is genuinely stemless; a black one with no stem
        # is an attachment failure and must not be billed as a whole note
        if h.char in (NOTEHEAD_WHOLE, NOTEHEAD_HALF):
            value = "Whole" if h.char == NOTEHEAD_WHOLE else "Half"
            out.append({"x": h.x, "value": value, "dots": 0, "heads": 1,
                        "beams": 0, "voice": 1})
    out.sort(key=lambda c: c["x"])
    return out, beams, stems


def analyse(path, page=0):
    glyphs, segments, box = extract(path, page)
    staves = find_staves(segments)
    pairs = pair_systems(staves)
    partner = {id(t): n for t, n in pairs}
    for st in staves:
        st.barlines = find_barlines(st, segments, partner.get(id(st)))
        if st.kind == "tab":
            attach_notes(st, glyphs)
    systems = []
    for tab, notation in pairs:
        if notation is None:
            systems.append((tab, None, [], [], []))
            continue
        notation.barlines = tab.barlines
        cols, beams, stems = durations(notation, glyphs, segments, staves, tab.barlines)
        systems.append((tab, notation, cols, beams, stems))
    return systems, staves, glyphs
