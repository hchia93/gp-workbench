# -*- coding: utf-8 -*-
"""Picking figures: read one off a bar, spread one over a run of chords.

    python src/tabulator/chord_pattern.py sample in.gp --bar 2
    python src/tabulator/chord_pattern.py apply in.gp out.gp --sample 2 --from 10
        --chords "xx0222:2 xx0222:2 xx0222:2 x20222:2 x20222:2 x20222 020033"
        [--dry-run]

sample prints the bar in the slot form src/sampling stores, so a figure can go
into the pack and come back out through --figure. --sample is the bar to copy
the pattern from: which strings each eighth plucks,
thumb on 4-6 and fingers on 1-3, in the order they come. --chords lists the
shapes to lay it on, low string first (x = not played), each with how many
half bars it lasts (default 1). The pattern's thumb strings are mapped onto the
shape's played bass strings from the lowest up, the finger strings likewise from
the highest down, so a T-23 pattern sampled on x02220 comes out as thumb plus the
top two strings on any shape. Rhythm values are copied from the sample bar.
Bars from --from on are rewritten in place, as bars.py modify does.
"""

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, ".")

from src.gp_ops import reader
from src.gp_ops.patcher import load_gpif

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

THUMB = (4, 5, 6)
# The slot spelling src/sampling packs: thumb from the lowest played bass string
# up, fingers from the highest treble string down, frets thrown away.
SLOT_STRING = {"T0": 6, "T1": 5, "T2": 4, "F0": 1, "F1": 2, "F2": 3}
SHORT = {("Whole", False): "w", ("Half", True): "h.", ("Half", False): "h",
         ("Quarter", True): "q.", ("Quarter", False): "q", ("Eighth", True): "e.",
         ("Eighth", False): "e", ("16th", True): "s.", ("16th", False): "s",
         ("32nd", False): "t"}
VALUE = {v: k for k, v in SHORT.items()}


def as_slots(fig):
    """One bar in the slot form, so it round trips through src/sampling."""
    bass = sorted({s for _, _, ss in fig for s in ss if s in THUMB}, reverse=True)
    top = sorted({s for _, _, ss in fig for s in ss if s not in THUMB})
    out = []
    for value, dotted, strings in fig:
        named = sorted(("T%d" % bass.index(s)) if s in THUMB else ("F%d" % top.index(s)) for s in strings)
        out.append("%s:%s" % (SHORT.get((value, dotted), value), "+".join(named) or "-"))
    return " ".join(out)


def from_slots(text):
    """The slot form back into the (value, dotted, strings) the layer wants."""
    fig = []
    for cell in text.split():
        head, _, slots = cell.partition(":")
        if head not in VALUE:
            sys.exit(f"figure {cell}: {head} is not a note value")
        value, dotted = VALUE[head]
        strings = [] if slots in ("", "-") else [SLOT_STRING[s] for s in slots.split("+")]
        fig.append((value, dotted, sorted(strings)))
    return fig


def pattern(gp, bar):
    """[(value, dotted, [string, ...]), ...] for one bar, strings as plucked."""
    m = reader.read(gp)[bar - 1]
    return [(b.value, bool(b.dots), sorted(s for s, _ in b.notes)) for b in m.voices[1]]


def shape_map(shape):
    """string -> fret for a shape written low string first."""
    if len(shape) != 6:
        sys.exit(f"shape {shape}: six characters, low string first")
    return {6 - i: int(ch) for i, ch in enumerate(shape) if ch != "x"}


def lay(fig, shape):
    """The pattern's strings replaced by the shape's, role by role."""
    frets = shape_map(shape)
    bass = sorted(s for s in frets if s in THUMB)
    # both lists run highest pitch first, as fig_top does, or the roles invert
    top = sorted(s for s in frets if s not in THUMB)
    if not bass or not top:
        sys.exit(f"shape {shape}: needs at least one bass string and one treble string")
    fig_bass = sorted({s for _, _, ss in fig for s in ss if s in THUMB}, reverse=True)
    fig_top = sorted({s for _, _, ss in fig for s in ss if s not in THUMB})
    # deepest thumb string of the pattern -> deepest played string of the shape,
    # next thumb string -> next one up; highest finger string -> highest, and so on
    role = {s: bass[max(0, len(bass) - 1 - n)] for n, s in enumerate(fig_bass)}
    role.update({s: top[min(n, len(top) - 1)] for n, s in enumerate(fig_top)})
    beats = []
    for value, dotted, strings in fig:
        seen, notes = set(), []
        for s in strings:
            t = role[s]
            if t not in seen:
                seen.add(t)
                notes.append([t, frets[t]])
        beats.append({"v": value, "dot": dotted, "n": sorted(notes, reverse=True)})
    return beats


def cmd_sample(args):
    fig = pattern(args.src, args.bar)
    print(as_slots(fig))


def cmd_apply(args):
    if args.figure:
        fig = from_slots(args.figure)
        where = "figure"
    else:
        fig = pattern(args.src, args.sample)
        where = f"bar {args.sample}"
    halves = len(fig) // 2
    if len(fig) % 2:
        sys.exit(f"{where} has {len(fig)} beats, the pattern must split into two halves")

    plan = []
    for item in args.chords.split():
        shape, _, n = item.partition(":")
        plan += [shape] * (int(n) if n else 1)
    if len(plan) % 2:
        plan.append(plan[-1])

    bars = []
    for k in range(0, len(plan), 2):
        beats = lay(fig[:halves], plan[k]) + lay(fig[halves:], plan[k + 1])
        bars.append(beats)

    for i, bar in enumerate(bars):
        print(f"  bar {args.start + i:>2}  " + " | ".join("+".join(f"s{s}f{f}" for s, f in b["n"]) or "rest" for b in bar))
    if args.dry_run:
        return
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({"bars": bars}, f, ensure_ascii=False)
    try:
        subprocess.run([sys.executable, "src/tabulator/bars.py", "modify", args.src, args.out, f.name,
                        "--from", str(args.start)], check=True)
    finally:
        os.unlink(f.name)


def main():
    ap = argparse.ArgumentParser()
    verb = ap.add_subparsers(dest="verb", required=True)
    take = verb.add_parser("sample", help="print one bar as a figure in slot form")
    take.add_argument("src")
    take.add_argument("--bar", type=int, required=True, help="1-based bar to read")
    take.set_defaults(run=cmd_sample)
    use = verb.add_parser("apply", help="lay a figure over a run of chords")
    use.add_argument("src")
    use.add_argument("out")
    use.add_argument("--sample", type=int, help="1-based bar to copy the pattern from")
    use.add_argument("--figure", help="a figure in slot form, as src/sampling stores it")
    use.add_argument("--from", dest="start", type=int, required=True, help="1-based bar to start writing at")
    use.add_argument("--chords", required=True, help="shapes low string first, 'x20222:2' = two half bars")
    use.add_argument("--dry-run", action="store_true")
    use.set_defaults(run=cmd_apply)
    args = ap.parse_args()
    if args.verb == "apply" and bool(args.sample) == bool(args.figure):
        sys.exit("apply needs either --sample or --figure, not both")
    return args.run(args)


if __name__ == "__main__":
    main()
