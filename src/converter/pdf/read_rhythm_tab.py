"""Read durations off a TAB staff that has no notation staff above it.

Guitar Pro draws the rhythm under the TAB staff: a stem per note, a flag glyph
for an unbeamed note, and beams across a beamed group. Two thirds of the library
is TAB-only, so this is the path that covers most systems.

Usage: gp-workbench rhythm <file.pdf> [--page N]
"""

import bisect
from collections import defaultdict
from fractions import Fraction

from src.converter.pdf.extract_content import extract
from src.converter.pdf.read_rhythm_notation import angle, DENOM
from src.converter.pdf.find_staff import attach_notes, dedupe, find_barlines, find_staves, pair_systems

FLAG_LO, FLAG_HI = 0xE240, 0xE24F     # flag8thUp .. flag128thDown
AUG_DOT = ""
REACH = 34.0                          # how far under the staff rhythm marks sit
COLUMN_TOL = 5.0                      # note x to flag x
STEM_OFFSET = 1.9                     # the stem is drawn just right of the digit
BEAM_TOL = 1.5                        # a beamlet is only ~3.7 wide, so keep this tight
VALUE_BY_LEVEL = {0: "Quarter", 1: "Eighth", 2: "16th", 3: "32nd", 4: "64th"}


def flag_level(code):
    """U+E240 is the 8th flag, and every duration adds two codepoints."""
    return (code - FLAG_LO) // 2 + 1


def beams_under(staff, segments):
    """Beam polygons drawn below the staff, as (x0, x1, y)."""
    edges = []
    for s in segments:
        if s.length < 2.5 or angle(s) > 25.0:
            continue
        y = (s.y0 + s.y1) / 2
        if staff.bottom - REACH < y < staff.bottom - 0.6:
            edges.append(s)
    buckets = defaultdict(list)
    for s in edges:
        buckets[(round(min(s.x0, s.x1), 0), round(max(s.x0, s.x1), 0))].append(s)
    out = []
    for (x0, x1), group in buckets.items():
        mids = []
        for s in sorted(group, key=lambda s: (s.y0 + s.y1) / 2):
            m = (s.y0 + s.y1) / 2
            if not any(abs(m - u) < 1.6 for u in mids):
                mids.append(m)
        for i in range(0, len(mids), 2):        # two edges per beam
            out.append((x0, x1, mids[i]))
    return out


def stems_under(staff, segments):
    """x of every rhythm stem drawn below the staff.

    Guitar Pro prints a stem for every beat but prints no fret digit for the
    far end of a tie, so a stem with no digit above it is a tied beat. Reading
    stems is the only way to see those beats at all.
    """
    xs = []
    for s in segments:
        if not s.vertical or s.length < 2.0:
            continue
        top = max(s.y0, s.y1)
        if staff.bottom - REACH < top < staff.bottom + 1.5:
            xs.append((s.x0 + s.x1) / 2)
    return dedupe(sorted(xs), tol=1.5)


def tied_columns(staff, segments, columns):
    """Beats that carry a stem but no digit, as (x, notes copied from before)."""
    known = sorted(columns)
    out = []
    for stem_x in stems_under(staff, segments):
        x = stem_x - STEM_OFFSET
        if any(abs(x - k) <= COLUMN_TOL for k in known):
            continue
        earlier = [k for k in known if k < x]
        if not earlier:
            continue
        out.append((x, columns[earlier[-1]]))
    return out


def durations(staff, glyphs, segments):
    """One event per TAB note column, with its note value."""
    beams = beams_under(staff, segments)
    flags = [g for g in glyphs
             if FLAG_LO <= ord(g.char) <= FLAG_HI
             and staff.bottom - REACH < g.y < staff.bottom + 1]
    dots = [g for g in glyphs
            if g.char == AUG_DOT and staff.bottom - REACH < g.y < staff.top + 4]

    columns = defaultdict(list)
    for n in staff.notes:
        columns[round(n.x, 1)].append(n)
    tied = {round(x, 1): source for x, source in tied_columns(staff, segments, columns)}
    columns.update(tied)

    out = []
    for x in sorted(columns):
        level = 0
        near = [g for g in flags if abs(g.x - x) <= COLUMN_TOL + 2]
        if near:
            level = flag_level(ord(min(near, key=lambda g: abs(g.x - x)).char))
        else:
            stem_x = x + STEM_OFFSET
            level = sum(1 for x0, x1, _ in beams
                        if x0 - BEAM_TOL <= stem_x <= x1 + BEAM_TOL)
        ndots = len({round(d.x, 1) for d in dots if 0 < d.x - x < 9})
        out.append({"x": x, "value": VALUE_BY_LEVEL.get(level, "64th"),
                    "dots": min(ndots, 2), "level": level,
                    "notes": [(n.string, n.fret) for n in columns[x]],
                    "measure": (bisect.bisect_right(staff.barlines, x)
                                if x in tied else columns[x][0].measure)})
    return out, beams, flags


def length_of(col):
    base = Fraction(1, DENOM[col["value"]])
    if col["dots"]:
        base *= Fraction(2) - Fraction(1, 2 ** col["dots"])
    return base


def dotting(dots):
    return Fraction(2) - Fraction(1, 2 ** dots) if dots else Fraction(1)


def resolve(seq, target, x_end):
    """Decide the durations tablature leaves ambiguous.

    Level 0 means no flag and no beam, and that is how Quarter, Half and Whole
    all look in TAB. Two facts settle it: the measure has to add up to the time
    signature, and engraving spaces notes proportional to how long they last.
    So enumerate the assignments that close the measure and keep the one whose
    proportions best match the horizontal gaps.
    """
    free = [i for i, c in enumerate(seq) if c["level"] == 0]
    if not free or len(free) > 6:
        return seq
    fixed = sum(length_of(c) for i, c in enumerate(seq) if i not in set(free))
    budget = target - fixed
    if budget <= 0:
        return seq

    xs = [c["x"] for c in seq] + [x_end]
    span = {i: max(xs[i + 1] - xs[i], 0.1) for i in free}
    total = sum(span.values())
    ideal = {i: budget * Fraction(span[i] / total).limit_denominator(64) for i in free}

    best, cost = None, None
    def walk(k, used, pick):
        nonlocal best, cost
        if used > budget:
            return
        if k == len(free):
            if used != budget:
                return
            c = sum(abs(pick[i] - ideal[i]) for i in free)
            if cost is None or c < cost:
                best, cost = dict(pick), c
            return
        i = free[k]
        for base in ("Quarter", "Half", "Whole"):
            pick[i] = Fraction(1, DENOM[base]) * dotting(seq[i]["dots"])
            walk(k + 1, used + pick[i], pick)
        pick.pop(i, None)
    walk(0, Fraction(0), {})
    if best is None:
        return seq

    for i, value in ((i, v) for i in free
                     for v in ("Quarter", "Half", "Whole")
                     if Fraction(1, DENOM[v]) * dotting(seq[i]["dots"]) == best[i]):
        seq[i]["value"] = value
    return seq


def measure_sequence(staff, cols, signature=None):
    """Every measure the barlines define, empty ones included.

    A score can open with an empty or partial measure. Emitting only measures
    that carry notes shifts the whole sequence and nothing lines up after it.
    """
    by_measure = defaultdict(list)
    for c in cols:
        by_measure[c["measure"]].append(c)
    out = [by_measure.get(m, []) for m in range(1, staff.measures + 1)]
    if not signature:
        return out
    beats, unit = (int(n) for n in signature.split("/"))
    target = Fraction(beats, unit)
    for m, seq in enumerate(out, start=1):
        if seq and m < len(staff.barlines):
            resolve(seq, target, staff.barlines[m])
    return out


def analyse(path, page=0):
    glyphs, segments, box = extract(path, page)
    staves = find_staves(segments)
    partner = {id(t): n for t, n in pair_systems(staves)}
    out = []
    for st in staves:
        if st.kind != "tab":
            continue
        st.barlines = find_barlines(st, segments, partner.get(id(st)))
        attach_notes(st, glyphs)
        cols, beams, flags = durations(st, glyphs, segments)
        out.append((st, cols, beams, flags))
    return out, staves, glyphs
