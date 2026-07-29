"""Regression benchmark against songs that have both a .gp and its exported PDF.

The .gp is ground truth. Decoding the PDF and diffing against it is the only
check that catches a wrong direction early: tuning against one file looked like
33% once while the library as a whole sat at 19%.

Run this after every change to the decoders.

    python tools/bench.py --library <path/to/scores>
    python tools/bench.py --library <path/to/scores> --detail "The Crow"
"""

import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gp.read import read                       # noqa: E402
from src.score.rhythm_tab import analyse           # noqa: E402


def pages_of(path):
    return len(re.findall(rb"/Type\s*/Page[^s]", open(path, "rb").read())) or 1


def find_pairs(library):
    """A song folder holding both a .gp and a PDF is a candidate pair."""
    pairs = []
    for root, _, files in os.walk(library):
        gps = sorted(f for f in files if f.lower().endswith(".gp"))
        pdfs = sorted(f for f in files if f.lower().endswith(".pdf"))
        if gps and pdfs:
            pairs.append((os.path.basename(root), os.path.join(root, gps[0]),
                          [os.path.join(root, p) for p in pdfs]))
    return sorted(pairs)


def decode(pdf):
    """Measure sequence from the PDF, empty measures included."""
    out = []
    for page in range(pages_of(pdf)):
        try:
            systems, staves, glyphs = analyse(pdf, page)
        except Exception:
            continue
        for staff, cols, beams, flags in systems:
            by_measure = collections.defaultdict(list)
            for c in cols:
                by_measure[c["measure"]].append(c)
            for m in range(1, staff.measures + 1):
                out.append(by_measure.get(m, []))
    return out


def truth(gp):
    measures = read(gp)
    return [(sorted(n for b in m.voices.get(1, []) for n in b.notes),
             [f"{b.value}{'.' * b.dots}" for b in m.voices.get(1, [])])
            for m in measures]


def compare(gp, pdf):
    want = truth(gp)
    got = decode(pdf)
    notes = values = both = n = 0
    rows = []
    for i, (wn, wv) in enumerate(want):
        if i >= len(got):
            break
        n += 1
        gn = sorted(x for col in got[i] for x in col["notes"])
        gv = [f"{col['value']}{'.' * col['dots']}" for col in got[i]]
        ok_n, ok_v = gn == wn, gv == wv
        notes += ok_n
        values += ok_v
        both += ok_n and ok_v
        rows.append((i + 1, wn, gn, wv, gv, ok_n, ok_v))
    return n, notes, values, both, rows


def pick_pdf(gp, pdfs):
    """The PDF that decodes to a measure count closest to the .gp is the pair."""
    target = len(read(gp))
    best, score = None, None
    for p in pdfs:
        try:
            count = len(decode(p))
        except Exception:
            continue
        if count == 0:
            continue
        gap = abs(count - target)
        if score is None or gap < score:
            best, score = p, gap
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", required=True, help="folder holding the song folders")
    ap.add_argument("--detail", help="print a measure-by-measure diff for songs matching this text")
    args = ap.parse_args()

    pairs = find_pairs(args.library)
    print(f"{'song':<34}{'measures':>9}{'notes':>8}{'values':>8}{'both':>7}")
    total = collections.Counter()
    for song, gp, pdfs in pairs:
        pdf = pick_pdf(gp, pdfs)
        if pdf is None:
            continue
        n, notes, values, both, rows = compare(gp, pdf)
        if n == 0:
            continue
        print(f"  {song[:32]:<34}{n:>9}{notes:>8}{values:>8}{both:>7}")
        total["n"] += n
        total["notes"] += notes
        total["values"] += values
        total["both"] += both
        if args.detail and args.detail.lower() in song.lower():
            for m, wn, gn, wv, gv, ok_n, ok_v in rows:
                if ok_n and ok_v:
                    continue
                print(f"      m{m}")
                if not ok_n:
                    print(f"        notes  want {wn}")
                    print(f"               got  {gn}")
                if not ok_v:
                    print(f"        values want {wv}")
                    print(f"               got  {gv}")

    n = max(1, total["n"])
    print(f"\n{total['n']} measures   "
          f"notes {total['notes']} ({100 * total['notes'] / n:.1f}%)   "
          f"values {total['values']} ({100 * total['values'] / n:.1f}%)   "
          f"both {total['both']} ({100 * total['both'] / n:.1f}%)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
