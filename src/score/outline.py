"""Group the vector strokes inside a TAB staff into glyph outlines.

Files on the image route draw their fret numbers as outlines rather than text.
The same digit is emitted from the same path data every time, so identical
glyphs hash to the same signature and only need to be named once.

Usage: python outline.py <file.pdf> [--page N] [--survey]
"""

import csv
import hashlib
import os
import re
from collections import Counter, defaultdict

from ..pdf.content import extract
from .staff import find_barlines, find_staves, pair_systems

JOIN_TOL = 1.2          # endpoints closer than this belong to one outline
GRID_W, GRID_H = 7, 10  # normalised bitmap the shape signature is taken from
MIN_STROKES = 3         # a glyph outline is more than a stray tick


class Outline:
    def __init__(self, segments):
        self.segments = segments
        xs = [v for s in segments for v in (s.x0, s.x1)]
        ys = [v for s in segments for v in (s.y0, s.y1)]
        self.x0, self.x1 = min(xs), max(xs)
        self.y0, self.y1 = min(ys), max(ys)

    @property
    def width(self):
        return self.x1 - self.x0

    @property
    def height(self):
        return self.y1 - self.y0

    def grid(self, w=GRID_W, h=GRID_H):
        """Normalised occupancy grid: the outline drawn into a small bitmap.

        Hashing raw coordinates is too brittle. Flattened curves land on
        slightly different sub-pixel offsets each time a glyph is drawn, so the
        same digit hashes differently. A normalised grid is stable and can also
        be compared against a rendered reference digit.
        """
        cells = set()
        sx = (w - 1) / self.width if self.width else 0
        sy = (h - 1) / self.height if self.height else 0
        for s in self.segments:
            steps = max(2, int(s.length * 3))
            for i in range(steps + 1):
                t = i / steps
                x = s.x0 + (s.x1 - s.x0) * t
                y = s.y0 + (s.y1 - s.y0) * t
                cells.add((int(round((x - self.x0) * sx)), int(round((y - self.y0) * sy))))
        return cells

    def signature(self):
        cells = self.grid()
        bits = "".join("1" if (x, y) in cells else "0"
                       for y in range(GRID_H) for x in range(GRID_W))
        return hashlib.sha1(bits.encode()).hexdigest()[:10]

    def render(self):
        cells = self.grid()
        return ["".join("#" if (x, y) in cells else "." for x in range(GRID_W))
                for y in range(GRID_H - 1, -1, -1)]

    def __repr__(self):
        return f"glyph({self.width:.1f}x{self.height:.1f}, {len(self.segments)} strokes)"


def cluster(segments):
    """Connect strokes that share an endpoint into outlines."""
    remaining = list(segments)
    out = []
    while remaining:
        seed = remaining.pop()
        group = [seed]
        ends = [(seed.x0, seed.y0), (seed.x1, seed.y1)]
        changed = True
        while changed:
            changed = False
            for s in list(remaining):
                for a in ((s.x0, s.y0), (s.x1, s.y1)):
                    if any(abs(a[0] - b[0]) < JOIN_TOL and abs(a[1] - b[1]) < JOIN_TOL for b in ends):
                        group.append(s)
                        ends += [(s.x0, s.y0), (s.x1, s.y1)]
                        remaining.remove(s)
                        changed = True
                        break
        if len(group) >= MIN_STROKES:
            out.append(Outline(group))
    return sorted(out, key=lambda o: (o.x0, o.y0))


def glyph_outlines(path, page=0):
    glyphs, segments, box = extract(path, page)
    staves = find_staves(segments)
    partner = {id(t): n for t, n in pair_systems(staves)}
    found = []
    for st in [s for s in staves if s.kind == "tab"]:
        st.barlines = find_barlines(st, segments, partner.get(id(st)))
        on_line = [s for s in segments
                   if s.horizontal and any(abs(s.y0 - line) < 0.6 for line in st.lines)]
        inside = [s for s in segments
                  if st.bottom - 2 <= min(s.y0, s.y1) and max(s.y0, s.y1) <= st.top + 2
                  and s not in on_line and s.length < 8]
        for o in cluster(inside):
            if 1.0 < o.width < 8 and 1.0 < o.height < 9:
                found.append((st, o))
    return found


def survey(limit=None):
    rows = [r for r in csv.DictReader(open(os.path.join(HERE, "routes.tsv"), encoding="utf-8"),
                                      delimiter="\t") if r["route"] == "image"][:limit]
    per_file = {}
    everywhere = Counter()
    owners = defaultdict(set)
    for r in rows:
        path = os.path.join(ROOT, r["path"].replace(SEP, "/"))
        try:
            found = glyph_outlines(path, 0)
        except Exception:
            found = []
        sigs = Counter(o.signature() for _, o in found)
        per_file[r["song"]] = (len(found), len(sigs))
        for s, n in sigs.items():
            everywhere[s] += n
            owners[s].add(r["song"])
    print(f"{'song':<40}{'outlines':>9}{'distinct':>9}")
    for song, (n, d) in list(per_file.items())[:24]:
        print(f"  {song[:38]:<40}{n:>9}{d:>9}")
    shared = [s for s, files in owners.items() if len(files) > 1]
    print(f"\nfiles surveyed {len(per_file)}")
    print(f"distinct signatures overall {len(everywhere)}")
    print(f"signatures seen in more than one file {len(shared)}")
    if shared:
        top = sorted(shared, key=lambda s: -len(owners[s]))[:8]
        for s in top:
            print(f"   {s}  appears in {len(owners[s])} files, {everywhere[s]} times")
