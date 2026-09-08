"""Classify every PDF in a library by the decoder it needs.

The question that decides the route is not the producer string, it is whether
the fret numbers come back out of the text layer. So this runs the text-layer
reader and records what it got.

    python tools/survey/survey.py --library <path/to/scores> --csv work/routes.tsv
"""

import argparse
import collections
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.classify import EMPTY, IMAGE_ROUTE, TEXT_ROUTE, probe_route   # noqa: E402
from src.pdf.content import extract                                    # noqa: E402
from src.score.staff import find_barlines, find_staves, pair_systems   # noqa: E402


def producer(data):
    m = re.search(rb"/Producer\s*\(([^)]*)\)", data) or re.search(rb"/Creator\s*\(([^)]*)\)", data)
    if not m:
        return ""
    raw = m.group(1)
    if raw.startswith(b"\xfe\xff"):
        try:
            return raw[2:].decode("utf-16-be", "replace").strip()
        except Exception:
            pass
    return raw.decode("latin1", "replace").strip()


def shape(path):
    """Cheap facts straight out of the file, before any decoding."""
    data = open(path, "rb").read()
    return {
        "pages": len(re.findall(rb"/Type\s*/Page[^s]", data)) or 1,
        "images": len(re.findall(rb"/Subtype\s*/Image", data)),
        "fonts": len(re.findall(rb"/Type\s*/Font", data)),
        "kb": round(len(data) / 1024),
        "producer": producer(data)[:40],
    }


def staff_agreement(path, max_pages=3):
    """How often a TAB staff and its notation staff report the same bar count.

    Both are detected independently, so agreement is a correctness signal that
    needs no ground truth. Only systems that have both staves can be scored.
    """
    agree = disagree = 0
    for page in range(min(shape(path)["pages"], max_pages)):
        try:
            glyphs, segments, box = extract(path, page)
        except Exception:
            continue
        staves = find_staves(segments)
        for tab, notation in pair_systems(staves):
            if notation is None:
                continue
            tab.barlines = find_barlines(tab, segments, notation)
            notation.barlines = find_barlines(notation, segments, tab)
            if tab.measures == notation.measures:
                agree += 1
            else:
                disagree += 1
    return agree, disagree


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", required=True)
    ap.add_argument("--csv", help="write the full table here")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    pdfs = []
    for root, _, files in os.walk(args.library):
        pdfs += [os.path.join(root, f) for f in files if f.lower().endswith(".pdf")]
    pdfs.sort()
    if args.limit:
        pdfs = pdfs[:args.limit]

    rows = []
    tally = collections.Counter()
    for path in pdfs:
        try:
            facts = shape(path)
            route, staves, measures, notes, glyphs = probe_route(path)
            agree, disagree = staff_agreement(path) if route == TEXT_ROUTE else (0, 0)
        except Exception:
            facts, route = {"pages": 0, "images": 0, "fonts": 0, "kb": 0, "producer": ""}, EMPTY
            staves = measures = notes = glyphs = agree = disagree = 0
        tally[route] += 1
        rows.append({"song": os.path.basename(os.path.dirname(path)),
                     "file": os.path.basename(path),
                     "route": route, "tab_staves": staves, "measures": measures,
                     "notes": notes, "glyphs": glyphs,
                     "agree": agree, "disagree": disagree, **facts})

    total = max(1, len(rows))
    print(f"{'route':<12}{'files':>7}{'share':>8}")
    for route in (TEXT_ROUTE, IMAGE_ROUTE, EMPTY):
        print(f"{route:<12}{tally[route]:>7}{100 * tally[route] / total:>7.1f}%")
    print(f"{'total':<12}{len(rows):>7}")

    usable = [r for r in rows if r["notes"] > 0]
    ag = sum(r["agree"] for r in rows)
    dis = sum(r["disagree"] for r in rows)
    print(f"\nfiles yielding notes  {len(usable)}")
    print(f"measures {sum(r['measures'] for r in usable)}   notes {sum(r['notes'] for r in usable)}")
    if ag + dis:
        print(f"staff agreement {ag}/{ag + dis} ({100 * ag / (ag + dis):.1f}%)")

    if args.csv:
        dest = os.path.abspath(args.csv)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        keys = ["song", "file", "route", "tab_staves", "measures", "notes", "glyphs",
                "agree", "disagree", "pages", "images", "fonts", "kb", "producer"]
        with open(dest, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys, delimiter="\t", lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        print(f"\n-> {dest}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
