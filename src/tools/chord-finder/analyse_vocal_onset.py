# -*- coding: utf-8 -*-
"""Where each sung syllable starts, on the bar grid, from the vocal stem.

    python src/tools/chord-finder/analyse_vocal_onset.py vocals.wav --bpm 72.1 --phase 0.045
        [--grid0 22] [--end 32] [--json out.json]

Guitar Pro hands lyric tokens to note beats in order, so lyrics land right only
when the syllable positions are known. Onsets come from spectral flux with a
short smoothing so a vowel wobble is not counted twice; phrases split on gaps.
"""

import argparse
import io
import json
import sys

import numpy as np
from scipy.io import wavfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

LABEL = ["", "e", "&", "a"]


def onsets(wav, end, min_gap=0.26):
    rate, d = wavfile.read(wav)
    x = d.astype(np.float64)
    x = x.mean(axis=1) if x.ndim > 1 else x
    x /= 32768.0
    n_fft, hop = 2048, 256
    w = np.hanning(n_fft)
    nf = 1 + (len(x) - n_fft) // hop
    mag = np.empty((nf, n_fft // 2 + 1), dtype=np.float32)
    for i in range(nf):
        mag[i] = np.abs(np.fft.rfft(x[i * hop:i * hop + n_fft] * w))
    dt = hop / rate
    flux = np.concatenate([[0], np.maximum(np.diff(mag, axis=0), 0).sum(axis=1)])
    sm = np.convolve(flux, np.ones(5) / 5, mode="same")
    win = int(0.25 / dt)
    loc = np.convolve(sm, np.ones(win) / win, mode="same")
    rms = np.array([np.sqrt((x[i * hop:i * hop + n_fft] ** 2).mean()) for i in range(nf)])
    gate = rms > rms.max() * 0.08
    out = []
    for i in range(1, len(sm) - 1):
        t = i * dt
        if end and t >= end:
            break
        if gate[i] and sm[i] > sm[i - 1] and sm[i] >= sm[i + 1] and sm[i] > loc[i] * 1.6:
            if not out or t - out[-1] > min_gap:
                out.append(t)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--phase", type=float, required=True, help="sixteenth-grid phase in seconds")
    ap.add_argument("--grid0", type=int, default=0, help="sixteenth index of bar 1's downbeat")
    ap.add_argument("--end", type=float, default=0.0)
    ap.add_argument("--gap", type=float, default=0.75, help="seconds of silence that end a phrase")
    ap.add_argument("--json")
    args = ap.parse_args()

    six = 60.0 / args.bpm / 4
    times = onsets(args.wav, args.end)
    rows = []
    for t in times:
        k = int(round((t - args.phase) / six)) - args.grid0
        bar, sub = divmod(k, 16)
        rows.append({"t": round(t, 3), "bar": bar, "sixteenth": sub})

    phrases, cur = [], []
    for r in rows:
        if cur and r["t"] - cur[-1]["t"] > args.gap:
            phrases.append(cur)
            cur = []
        cur.append(r)
    if cur:
        phrases.append(cur)

    print(f"{len(rows)} syllables, {len(phrases)} phrases, sizes {[len(p) for p in phrases]}")
    for i, p in enumerate(phrases):
        cells = " ".join(f"{r['bar'] + 1}.{r['sixteenth'] // 4 + 1}{LABEL[r['sixteenth'] % 4]}" for r in p)
        print(f"  phrase {i + 1:>2}  {len(p):>2} syl  {p[0]['t']:6.2f}-{p[-1]['t']:6.2f}s   {cells}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"bpm": args.bpm, "phase": args.phase, "grid0": args.grid0, "phrases": phrases}, f, indent=1)
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
