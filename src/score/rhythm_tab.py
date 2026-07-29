"""Read durations off a TAB staff that has no notation staff above it.

Guitar Pro draws the rhythm under the TAB staff: a stem per note, a flag glyph
for an unbeamed note, and beams across a beamed group. Two thirds of the library
is TAB-only, so this is the path that covers most systems.

Usage: python tabrhythm.py <file.pdf> [--page N] [--gp <file.gp>]
"""

from collections import defaultdict
from fractions import Fraction

from ..pdf.content import extract
from .rhythm_notation import angle, DENOM
from .staff import find_staves, find_barlines, attach_notes, pair_systems

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
                    "measure": columns[x][0].measure})
    return out, beams, flags


def length_of(col):
    base = Fraction(1, DENOM[col["value"]])
    if col["dots"]:
        base *= Fraction(2) - Fraction(1, 2 ** col["dots"])
    return base


def measure_sequence(staff, cols):
    """Every measure the barlines define, empty ones included.

    A score can open with an empty or partial measure. Emitting only measures
    that carry notes shifts the whole sequence and nothing lines up after it.
    """
    by_measure = defaultdict(list)
    for c in cols:
        by_measure[c["measure"]].append(c)
    return [by_measure.get(m, []) for m in range(1, staff.measures + 1)]


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
