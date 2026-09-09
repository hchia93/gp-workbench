"""Reconstruct staff geometry and TAB content from a text-layer PDF.

Builds on pdftext.py. Everything here is deterministic: staff lines, barlines and
fret numbers all come from the PDF's own vector and text operators, so there is
no recognition step and no error to measure.

Usage: python score.py <file.pdf> [--page N] [--dump]
"""

from collections import defaultdict

from src.converter.pdf.extractor import extract

LINE_MIN_COVERAGE = 150.0   # points of horizontal ink needed to call a y a staff line
STAFF_GAP = 9.0             # y distance that still counts as the same staff
DIGITS = set("0123456789")
FRET_FONT = "Arial"          # measure numbers and lyrics use other faces


class Staff:
    def __init__(self, lines):
        self.lines = lines                      # y of each line, top of page first
        self.spacing = abs(lines[-1] - lines[0]) / (len(lines) - 1) if len(lines) > 1 else 0
        self.barlines = []
        self.notes = []                         # Note, TAB staves only

    @property
    def kind(self):
        return {5: "notation", 6: "tab"}.get(len(self.lines), f"{len(self.lines)}-line")

    @property
    def top(self):
        # PDF y grows upward, so the topmost staff line has the largest y
        return max(self.lines)

    @property
    def bottom(self):
        return min(self.lines)

    @property
    def span(self):
        return self.top - self.bottom

    @property
    def measures(self):
        return max(0, len(self.barlines) - 1)

    def string_of(self, y, tol=2.0):
        """PDF y of a glyph baseline -> guitar string number (1 = highest pitch).

        `lines` runs top of page first, and in tablature the top line is the
        highest-pitched string, so the index maps straight onto the number.
        """
        best, dist = None, 1e9
        for i, line in enumerate(self.lines):
            d = abs(line - y)
            if d < dist:
                best, dist = i, d
        return (best + 1) if dist <= tol else None

    def measure_of(self, x):
        for i in range(len(self.barlines) - 1):
            if self.barlines[i] <= x < self.barlines[i + 1]:
                return i + 1
        return None


class Note:
    def __init__(self, string, fret, x, measure, ghost=False):
        self.string = string
        self.fret = fret
        self.x = x
        self.measure = measure
        self.ghost = ghost

    def __repr__(self):
        g = "()" if self.ghost else ""
        return f"m{self.measure}:s{self.string}f{self.fret}{g}"


def find_staves(segments):
    coverage = defaultdict(float)
    for s in segments:
        if s.horizontal:
            coverage[round(s.y0, 1)] += s.length
    ys = sorted(y for y, c in coverage.items() if c >= LINE_MIN_COVERAGE)
    if not ys:
        return []
    groups, cur = [], [ys[0]]
    for y in ys[1:]:
        if y - cur[-1] <= STAFF_GAP:
            cur.append(y)
        else:
            groups.append(cur)
            cur = [y]
    groups.append(cur)
    # PDF y grows upward, so ascending y is bottom-of-page first. Reading order
    # is top to bottom, so the staff list has to be reversed.
    groups.reverse()
    return [Staff(sorted(g, reverse=True)) for g in groups if len(g) >= 5]


def crossing_verticals(staff, segments, max_len=None):
    """x of every vertical stroke that spans the whole staff.

    A barline is often stroked across the notation staff and the TAB staff as a
    single line, so the length is not bounded by one staff's span.
    """
    xs = []
    for s in segments:
        if not s.vertical:
            continue
        lo, hi = min(s.y0, s.y1), max(s.y0, s.y1)
        if lo <= staff.bottom + 1.5 and hi >= staff.top - 1.5:
            if max_len is None or s.length <= max_len:
                xs.append(round(s.x0, 1))
    return sorted(xs)


def dedupe(xs, tol=4.0):
    out = []
    for x in xs:
        if out and x - out[-1] <= tol:
            continue
        out.append(x)
    return out


def find_barlines(staff, segments, partner=None):
    """A barline crosses the TAB staff and its notation staff at the same x.

    Note stems also cross a notation staff and beams also cross a TAB staff, but
    neither does both, so intersecting the two candidate sets leaves barlines.
    """
    if partner is not None:
        xs = crossing_verticals(staff, segments)
        other = crossing_verticals(partner, segments)
        xs = [x for x in xs if any(abs(x - o) <= 2.0 for o in other)]
    else:
        # no notation staff to intersect with; bound the length so the system
        # bracket and any multi-staff rule are excluded
        xs = crossing_verticals(staff, segments, max_len=staff.span * 1.2)
    left, right = staff_extent(staff, segments)
    if left is not None:
        xs = [x for x in xs if left - 2 <= x <= right + 2]
    merged = dedupe(xs)
    if left is not None:
        if not merged or merged[0] - left > 4:
            merged.insert(0, left)
        if not merged or right - merged[-1] > 4:
            merged.append(right)
    return drop_slivers(merged)


def drop_slivers(barlines, ratio=0.35):
    """Clef and key signature strokes leave barlines a few points apart.

    They create measures far narrower than any real one, and every measure after
    them is numbered wrong, so they have to go before notes are assigned.

    The yardstick is the 75th percentile rather than the median: a system can
    hold more slivers than real measures, and then the median is itself a sliver
    and nothing gets dropped.
    """
    if len(barlines) < 3:
        return barlines
    widths = [barlines[i + 1] - barlines[i] for i in range(len(barlines) - 1)]
    typical = sorted(widths)[min(len(widths) - 1, int(len(widths) * 0.75))]
    if typical <= 0:
        return barlines
    out = [barlines[0]]
    for i, w in enumerate(widths):
        if w >= typical * ratio:
            out.append(barlines[i + 1])
        elif i == len(widths) - 1:          # keep the closing edge
            out[-1] = barlines[i + 1]
    return out


def staff_extent(staff, segments):
    """Leftmost and rightmost x actually covered by this staff's own lines."""
    xs = []
    for s in segments:
        if s.horizontal and any(abs(s.y0 - line) < 0.6 for line in staff.lines):
            xs += [min(s.x0, s.x1), max(s.x0, s.x1)]
    return (round(min(xs), 1), round(max(xs), 1)) if xs else (None, None)


def calibrate_offset(staff, glyphs):
    """Fret digits sit a constant distance below the line they belong to."""
    cands = [g.y for g in glyphs
             if g.char in DIGITS and FRET_FONT in g.font
             and staff.bottom - 8 <= g.y <= staff.top + 4]
    if not cands:
        return 0.0
    best, score = 0.0, -1
    for off in [i * 0.1 for i in range(-60, 61)]:
        hit = sum(1 for y in cands if min(abs(line - (y - off)) for line in staff.lines) <= 1.0)
        if hit > score:
            best, score = off, hit
    return best


def attach_notes(staff, glyphs):
    offset = calibrate_offset(staff, glyphs)
    window = [g for g in glyphs
              if staff.bottom - 8 <= g.y <= staff.top + 4 and FRET_FONT in g.font
              and (g.char in DIGITS or g.char in "()")]
    window.sort(key=lambda g: g.x)
    notes, i = [], 0
    while i < len(window):
        g = window[i]
        if g.char not in DIGITS:
            i += 1
            continue
        # digits sharing an x are one multi-digit fret number
        digits = [g]
        j = i + 1
        while j < len(window) and window[j].char in DIGITS and abs(window[j].y - g.y) < 1.0 \
                and window[j].x - digits[-1].x < 4.0:
            digits.append(window[j])
            j += 1
        string = staff.string_of(g.y - offset)
        if string is not None:
            fret = int("".join(d.char for d in digits))
            ghost = any(w.char == "(" and 0 < g.x - w.x < 5 for w in window)
            notes.append(Note(string, fret, g.x, staff.measure_of(g.x), ghost))
        i = j
    staff.notes = notes
    return offset


def pair_systems(staves):
    """Each TAB staff belongs with the notation staff drawn directly above it."""
    tabs = [s for s in staves if s.kind == "tab"]
    nots = [s for s in staves if s.kind == "notation"]
    pairs = []
    for t in tabs:
        above = [n for n in nots if n.bottom > t.top]
        pairs.append((t, min(above, key=lambda n: n.bottom - t.top) if above else None))
    return pairs


def analyse(path, page=0):
    glyphs, segments, box = extract(path, page)
    staves = find_staves(segments)
    pairs = dict((id(t), n) for t, n in pair_systems(staves))
    for st in staves:
        partner = pairs.get(id(st))
        st.barlines = find_barlines(st, segments, partner)
        if st.kind == "tab":
            attach_notes(st, glyphs)
    for tab, notation in pair_systems(staves):
        if notation is not None:
            notation.barlines = tab.barlines
    return staves, glyphs, box
