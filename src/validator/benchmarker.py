"""Regression benchmark against songs that have both a .gp and its exported PDF.

The .gp is ground truth. Decoding the PDF and diffing against it is the only
check that catches a wrong direction early: tuning against one file looked like
33% once while the library as a whole sat at 19%.

Run this after every change to the decoders.

    python src/validator/benchmarker.py --library <path/to/scores>
    python src/validator/benchmarker.py --library <path/to/scores> --detail "The Crow"
"""

import argparse
import collections
import os
import re
import sys

sys.path.insert(0, ".")

from src.gp_ops.reader import read                       # noqa: E402
from src.converter.pdf.read_rhythm_notation import read_time_signature   # noqa: E402
from src.converter.pdf.read_rhythm_tab import analyse, measure_sequence  # noqa: E402


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
    signature = None
    for page in range(pages_of(pdf)):
        try:
            systems, staves, glyphs = analyse(pdf, page)
        except Exception:
            continue
        if signature is None:
            try:
                signature = read_time_signature(staves, glyphs, text=True)[1]
            except Exception:
                signature = ""
        for staff, cols, beams, flags in systems:
            out += measure_sequence(staff, cols, signature)
    return out


def truth(gp):
    """Notes merge every voice, because the decoder does not separate voices.

    Values can only be scored where there is a single voice: with two voices the
    beats interleave on the page and no flat list can represent them.
    """
    out = []
    for m in read(gp):
        voices = [v for v in m.voices.values() if v]
        notes = sorted(n for v in voices for b in v for n in b.notes)
        values = [f"{b.value}{'.' * b.dots}" for b in m.voices.get(1, [])]
        out.append((notes, values, len(voices) > 1))
    return out


def compare(gp, pdf):
    want = truth(gp)
    got = decode(pdf)
    notes = values = both = n = mixed = 0
    rows = []
    for i, (wn, wv, many) in enumerate(want):
        if i >= len(got):
            break
        n += 1
        mixed += many
        gn = sorted(x for col in got[i] for x in col["notes"])
        gv = [f"{col['value']}{'.' * col['dots']}" for col in got[i]]
        ok_n = gn == wn
        ok_v = (gv == wv) and not many
        notes += ok_n
        values += ok_v
        both += ok_n and ok_v
        rows.append((i + 1, wn, gn, wv, gv, ok_n, ok_v))
    return n, notes, values, both, mixed, rows


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
    print(f"{'song':<34}{'measures':>9}{'notes':>8}{'values':>8}{'both':>7}{'2-voice':>8}")
    total = collections.Counter()
    for song, gp, pdfs in pairs:
        pdf = pick_pdf(gp, pdfs)
        if pdf is None:
            continue
        n, notes, values, both, mixed, rows = compare(gp, pdf)
        if n == 0:
            continue
        print(f"  {song[:32]:<34}{n:>9}{notes:>8}{values:>8}{both:>7}{mixed:>8}")
        total["n"] += n
        total["notes"] += notes
        total["values"] += values
        total["both"] += both
        total["mixed"] += mixed
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
    solo = max(1, total["n"] - total["mixed"])
    print(f"{total['mixed']} of them carry two voices, which values are not scored on; "
          f"values over single-voice measures {100 * total['values'] / solo:.1f}%")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
