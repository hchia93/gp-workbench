# -*- coding: utf-8 -*-
"""Guitar stem -> draft fingerstyle .gp, via basic-pitch.

    python src/tools/chord-finder/transcribe_stem.py stem.wav template.gp out.gp
        [--bpm 72.1 --phase 0.045] [--start 5.5 --end 32] [--max-fret 5]

Two transcription passes: the strict one sets the skeleton, the permissive one
is trusted only where the strict one left a pulse empty. Everything else is the
hand: eighth pulse, thumb plus two fingers, low position. The output is a draft
to be corrected in Guitar Pro, not a transcription to trust.
"""

import argparse
import io
import itertools
import sys
import warnings

import numpy as np

sys.path.insert(0, ".")

from src.gp_ops import writer

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
warnings.filterwarnings("ignore")

TUNING = {1: 64, 2: 59, 3: 55, 4: 50, 5: 45, 6: 40}
BASS_STRINGS = (6, 5, 4)
STRICT, LOOSE = 0.5, 0.28
VALUE = {1: ("16th", False), 2: ("Eighth", False), 3: ("Eighth", True), 4: ("Quarter", False),
         6: ("Quarter", True), 8: ("Half", False)}


def transcribe(wav, onset, frame, lo_hz=75.0, hi_hz=1400.0):
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict
    _, _, notes = predict(wav, ICASSP_2022_MODEL_PATH, onset_threshold=onset, frame_threshold=frame,
                          minimum_note_length=58, minimum_frequency=lo_hz, maximum_frequency=hi_hz)
    return [(s, e, int(p), float(a)) for s, e, p, a, _ in notes if 40 <= p <= 86]


def fit_grid(strikes, lo=60.0, hi=90.0):
    """Tempo and sixteenth phase that put the most strikes on the grid."""
    st = np.array(sorted(strikes))
    best = None
    for bpm in np.arange(lo, hi + 0.01, 0.05):
        six = 60.0 / bpm / 4
        for phase in np.arange(0, six, six / 50):
            pos = (st - phase) / six
            err = np.median(np.abs(pos - np.round(pos))) * six
            if best is None or err < best[0]:
                best = (err, bpm, phase)
    return best


def attack_fn(wav):
    from scipy.io import wavfile
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

    def attack(t):
        i = int(t / dt)
        a, b = max(0, i - 3), min(len(flux), i + 6)
        if a >= b:
            return 0.0
        lo, hi = max(0, i - int(0.30 / dt)), min(len(flux), i + int(0.30 / dt))
        return float(flux[a:b].max() / (np.median(flux[lo:hi]) + 1e-9))
    return attack


def to_slots(notes, phase, six, attack):
    out = {}
    for s, e, p, a in sorted(notes):
        k = int(round((s - phase) / six))
        cur = out.setdefault(k, {})
        if p not in cur:
            cur[p] = (s, e, attack(s))
        else:
            s0, e0, a0 = cur[p]
            cur[p] = (min(s0, s), max(e0, e), a0 if s0 <= s else attack(s))
    return out


def fold_to_eighths(src, ref):
    out = {}
    for k in sorted(src):
        dst = k - 1 if (k - ref) % 4 in (1, 3) else k
        tgt = out.setdefault(dst, {})
        for p, v in src[k].items():
            if p in tgt:
                s0, e0, a0 = tgt[p]
                tgt[p] = (min(s0, v[0]), max(e0, v[1]), a0)
            else:
                tgt[p] = v
    return out


def place(ps, cap):
    per = [[(st, p - TUNING[st]) for st in range(1, 7) if 0 <= p - TUNING[st] <= cap] for p in sorted(ps)]
    keep = [(p, o) for p, o in zip(sorted(ps), per) if o]
    if len(keep) != len(ps):
        return None
    best = key = None
    for combo in itertools.product(*[o for _, o in keep]):
        st = [s for s, _ in combo]
        if len(set(st)) != len(st):
            continue
        fr = [f for _, f in combo]
        lit = [f for f in fr if f > 0]
        kk = (max(fr), (max(lit) - min(lit)) if lit else 0, sum(fr))
        if key is None or kk < key:
            key, best = kk, combo
    return {p: sc for sc, (p, _) in zip(best, keep)} if best else None


def resolve(ps, soft, hard):
    """Octave pairs are the thumb-and-fingers sound, keep them; only a stack
    that cannot be fretted loses its highest partial."""
    ps = set(ps)
    got = place(ps, soft)
    while got is None and len(ps) > 1:
        ghosts = [p for p in sorted(ps, reverse=True) if any(p - h in ps for h in (12, 24, 36))]
        if not ghosts:
            break
        ps.discard(ghosts[0])
        got = place(ps, soft)
    return got or place(ps, hard) or {}


def value_for(n):
    for sp in (8, 6, 4, 3, 2, 1):
        if n >= sp:
            return VALUE[sp], sp
    return VALUE[1], 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("template")
    ap.add_argument("out")
    ap.add_argument("--bpm", type=float)
    ap.add_argument("--phase", type=float, help="seconds, sixteenth-grid phase")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=0.0)
    ap.add_argument("--max-fret", type=int, default=5)
    ap.add_argument("--title", default="")
    ap.add_argument("--artist", default="")
    args = ap.parse_args()

    strict = transcribe(args.wav, STRICT, 0.3)
    loose = transcribe(args.wav, LOOSE, LOOSE)
    inside = lambda n: n[0] >= args.start and (not args.end or n[0] < args.end)
    strict = [n for n in strict if inside(n) and n[3] >= 0.33]
    loose = [n for n in loose if inside(n)]

    if args.bpm and args.phase is not None:
        bpm, phase = args.bpm, args.phase
    else:
        starts = []
        for s, *_ in sorted(strict):
            if not starts or s - starts[-1] > 0.055:
                starts.append(s)
        err, bpm, phase = fit_grid(starts)
        print(f"grid fit: {bpm:.2f} BPM, phase {phase:.4f}s, median error {1000 * err:.0f} ms")
    six = 60.0 / bpm / 4
    attack = attack_fn(args.wav)

    slots = to_slots(strict, phase, six, attack)
    weight = np.zeros(16)
    for k, v in slots.items():
        weight[k % 16] += sum(1 for p in v if p <= 55)
    ref = int(max(range(16), key=lambda s: weight[s % 16] + weight[(8 + s) % 16]))
    slots = fold_to_eighths(slots, ref)
    lo_slots = fold_to_eighths(to_slots(loose, phase, six, attack), ref)

    # weak beats the strict pass could not see start inside the previous ring
    for k in range(min(slots), max(slots) + 1):
        if (k - ref) % 2 == 0 and k not in slots and k in lo_slots:
            slots[k] = dict(lo_slots[k])

    # an identical shape on the next eighth, fading, is one stroke still ringing
    atk = sorted(max(v[2] for v in sl.values()) for sl in slots.values())
    faint = atk[int(len(atk) * 0.20)]
    for a in sorted(slots):
        b = a + 2
        if a in slots and b in slots and set(slots[a]) == set(slots[b]):
            aa = max(v[2] for v in slots[a].values())
            ab = max(v[2] for v in slots[b].values())
            if ab < aa * 0.6 or (aa < faint and ab < faint):
                for p, v in slots.pop(b).items():
                    s0, e0, a0 = slots[a][p]
                    slots[a][p] = (s0, max(e0, v[1]), a0)

    keys = sorted(slots)
    shaped = {k: resolve(slots[k].keys(), args.max_fret, args.max_fret + 2) for k in keys}

    # thumb and two fingers: never more than two notes at once
    for k in keys:
        sh = shaped[k]
        if len(sh) <= 2:
            continue
        if (k - ref) % 4 == 0:
            bass = [p for p, (st, _) in sh.items() if st in BASS_STRINGS]
            keep = {min(bass) if bass else min(sh), max(sh)}
        else:
            keep = set(sorted(sh)[-2:])
        shaped[k] = {p: v for p, v in sh.items() if p in keep}

    # an offbeat with one treble note is half a finger pair, the other half is
    # usually in the permissive pass
    for k in keys:
        if (k - ref) % 4 == 0 or len(shaped[k]) != 1:
            continue
        p0 = next(iter(shaped[k]))
        if p0 < 52:
            continue
        for p in sorted((p for p in lo_slots.get(k, {}) if p != p0 and p >= 52 and abs(p - p0) not in (12, 24)),
                        key=lambda q: -lo_slots[k][q][2]):
            trial = place({p0, p}, args.max_fret)
            if trial:
                shaped[k] = trial
                break

    keys = [k for k in keys if shaped[k]]
    grid0 = ((keys[0] - ref) // 16) * 16 + ref
    bars = {}
    for k in keys:
        if k >= grid0:
            bars.setdefault((k - grid0) // 16, {})[(k - grid0) % 16] = k

    song_bars = []
    for b in range(max(bars) + 1):
        items = sorted(bars.get(b, {}).items())
        beats, pos = [], 0
        for sub, k in items:
            while pos < sub:
                (v, dot), sp = value_for(min(sub - pos, 8))
                beats.append(writer.Beat(v, [], dot))
                pos += sp
            nx = next((s for s, _ in items if s > sub), 16)
            (v, dot), sp = value_for(min(nx - sub, 8))
            ns = [writer.Note(st, fr) for _, (st, fr) in sorted(shaped[k].items(), reverse=True)]
            beats.append(writer.Beat(v, ns, dot))
            pos += sp
        while pos < 16:
            (v, dot), sp = value_for(min(16 - pos, 8))
            beats.append(writer.Beat(v, [], dot))
            pos += sp
        song_bars.append({"beats": beats})

    song = {"title": args.title, "artist": args.artist, "tabber": "transcribe_stem draft",
            "tempo": int(round(bpm)), "capo": 0, "time": "4/4", "bars": song_bars, "lyrics": None}
    n, bt, nb = writer.build(args.template, song, args.out)
    print(f"{nb} bars, {bt} beats, {n} notes, downbeat phase {ref} sixteenths -> {args.out}")


if __name__ == "__main__":
    main()
