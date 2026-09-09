"""Command line entry point.

    gp-workbench route   <file.pdf>              which decoder the file needs
    gp-workbench read    <file.pdf> [--page N]   staves, barlines, TAB notes
    gp-workbench rhythm  <file.pdf> [--page N]   note values per measure
    gp-workbench gp      <file.gp>  [--measures A-B]   read a .gp back
    gp-workbench verify  <file.gp>...            dangling refs and bar duration
    gp-workbench convert <file.pdf> --template <any.gp> -o <out.gp>
"""

import argparse
import sys
from collections import defaultdict
from fractions import Fraction

from src.converter.pdf.router import probe_route
from src.converter.converter import convert
from src.gp_ops.reader import read as read_gp
from src.validator.verifier import check as verify_gp
from src.converter.pdf.rhythm_tab import analyse as analyse_rhythm, length_of, measure_sequence
from src.converter.pdf.staff import analyse as analyse_staff


def cmd_route(args):
    route, staves, measures, notes, glyphs = probe_route(args.pdf)
    print(f"{args.pdf}")
    print(f"  route {route}")
    print(f"  tab staves {staves}   measures {measures}   notes {notes}   glyphs {glyphs}")


def cmd_read(args):
    staves, glyphs, box = analyse_staff(args.pdf, args.page)
    tabs = [s for s in staves if s.kind == "tab"]
    print(f"{args.pdf}  page {args.page}")
    print(f"  staves {len(staves)} (tab {len(tabs)})   glyphs {len(glyphs)}")
    for i, st in enumerate(staves, 1):
        extra = f"   notes {len(st.notes)}" if st.kind == "tab" else ""
        print(f"  staff{i:<2} {st.kind:<9} measures {st.measures}{extra}")
    if not args.dump:
        return
    for i, st in enumerate(tabs, 1):
        by_measure = defaultdict(list)
        for n in st.notes:
            by_measure[n.measure].append(n)
        print(f"\n  tab {i}")
        for m in range(1, st.measures + 1):
            seq = " ".join(f"s{n.string}f{n.fret}"
                           for n in sorted(by_measure.get(m, []), key=lambda n: n.x))
            print(f"    m{m}: {seq or '(empty)'}")


def cmd_rhythm(args):
    systems, staves, glyphs = analyse_rhythm(args.pdf, args.page)
    print(f"{args.pdf}  page {args.page}   tab staves {len(systems)}")
    for i, (st, cols, beams, flags) in enumerate(systems, 1):
        print(f"  system{i}: measures {st.measures}  columns {len(cols)}  "
              f"beams {len(beams)}  flags {len(flags)}")
        for m, seq in enumerate(measure_sequence(st, cols), 1):
            total = sum((length_of(c) for c in seq), Fraction(0))
            body = " | ".join(f"{c['value']}{'.' * c['dots']}" for c in seq) or "(empty)"
            print(f"    m{m}: {str(total):>6}  {body}")


def cmd_gp(args):
    measures = read_gp(args.gp)
    lo, hi = 1, len(measures)
    if args.measures:
        a, _, b = args.measures.partition("-")
        lo, hi = int(a), int(b or a)
    closed = sum(1 for m in measures if m.closed)
    print(f"{args.gp}")
    print(f"  measures {len(measures)}   closed {closed}/{len(measures)}")
    for m in measures[lo - 1:hi]:
        sig = f"{m.signature.numerator}/{m.signature.denominator}"
        print(f"  m{m.index} ({sig})  " + "  ".join(f"v{v}={t}" for v, t in m.total.items()))
        for v, seq in sorted(m.voices.items()):
            print(f"     v{v}: " + " | ".join(repr(b) for b in seq))


def cmd_convert(args):
    info = convert(args.pdf, args.template, args.out,
                   title=args.title, artist=args.artist,
                   tempo=args.tempo, capo=args.capo)
    print(f"{args.pdf}")
    print(f"  time {info['time']}   measures {info['measures']}   "
          f"beats {info['beats']}   notes {info['notes']}")
    print(f"  -> {info['out']}")
    print("  open it in Guitar Pro; a corrected save becomes ground truth for src/validator/benchmarker.py")


def cmd_verify(args):
    ok = all(verify_gp(p) for p in args.gp)
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gp-workbench", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("route", help="report which decoder a PDF needs")
    p.add_argument("pdf")
    p.set_defaults(run=cmd_route)

    p = sub.add_parser("read", help="staves, barlines and TAB notes")
    p.add_argument("pdf")
    p.add_argument("--page", type=int, default=0)
    p.add_argument("--dump", action="store_true", help="list notes per measure")
    p.set_defaults(run=cmd_read)

    p = sub.add_parser("rhythm", help="note values per measure")
    p.add_argument("pdf")
    p.add_argument("--page", type=int, default=0)
    p.set_defaults(run=cmd_rhythm)

    p = sub.add_parser("gp", help="read a .gp back as measures")
    p.add_argument("gp")
    p.add_argument("--measures", help="range like 1-8")
    p.set_defaults(run=cmd_gp)

    p = sub.add_parser("convert", help="decode a PDF and write a .gp")
    p.add_argument("pdf")
    p.add_argument("--template", required=True,
                   help="any .gp to copy the non-XML zip entries from")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--title")
    p.add_argument("--artist", default="")
    p.add_argument("--tempo", type=int, default=90)
    p.add_argument("--capo", type=int, default=0)
    p.set_defaults(run=cmd_convert)

    p = sub.add_parser("verify", help="check a .gp for dangling refs and short bars")
    p.add_argument("gp", nargs="+")
    p.set_defaults(run=cmd_verify)

    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    return args.run(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
