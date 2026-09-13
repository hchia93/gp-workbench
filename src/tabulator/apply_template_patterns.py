# -*- coding: utf-8 -*-
"""Spread one bar's picking pattern over a run of chords.

    python src/tabulator/apply_template_patterns.py in.gp out.gp --sample 2 --from 10
        --chords "xx0222:2 xx0222:2 xx0222:2 x20222:2 x20222:2 x20222 020033"
        [--dry-run]

--sample is the bar to copy the pattern from: which strings each eighth plucks,
thumb on 4-6 and fingers on 1-3, in the order they come. --chords lists the
shapes to lay it on, low string first (x = not played), each with how many
half bars it lasts (default 1). The pattern's thumb strings are mapped onto the
shape's played bass strings from the lowest up, the finger strings likewise from
the highest down, so a T-23 pattern sampled on x02220 comes out as thumb plus the
top two strings on any shape. Rhythm values are copied from the sample bar.
Bars from --from on are rewritten in place, as append_bars --from does.
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
    top = sorted((s for s in frets if s not in THUMB), reverse=True)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--sample", type=int, required=True, help="1-based bar to copy the pattern from")
    ap.add_argument("--from", dest="start", type=int, required=True, help="1-based bar to start writing at")
    ap.add_argument("--chords", required=True, help="shapes low string first, 'x20222:2' = two half bars")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    fig = pattern(args.src, args.sample)
    halves = len(fig) // 2
    if len(fig) % 2:
        sys.exit(f"bar {args.sample} has {len(fig)} beats, the pattern must split into two halves")

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
        subprocess.run([sys.executable, "src/tabulator/append_bars.py", args.src, args.out, f.name,
                        "--from", str(args.start)], check=True)
    finally:
        os.unlink(f.name)


if __name__ == "__main__":
    main()
