"""Beat and downbeat grid from audio. numpy only.

Chord changes are the strongest downbeat cue we have, so the bar phase is
picked by how well chord onsets land on bar lines, not by audio alone.
"""

import numpy as np


def onset_envelope(rate, x, n_fft=2048, hop=512):
    window = np.hanning(n_fft)
    frames = 1 + (len(x) - n_fft) // hop
    prev = None
    flux = np.zeros(frames)
    for i in range(frames):
        mag = np.abs(np.fft.rfft(x[i * hop:i * hop + n_fft] * window))
        if prev is not None:
            flux[i] = np.maximum(mag - prev, 0).sum()
        prev = mag
    flux -= flux.mean()
    return np.maximum(flux, 0), hop / rate


def tempo_candidates(env, dt, lo_bpm=50, hi_bpm=200, top=5):
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    lo = int(round(60.0 / hi_bpm / dt))
    hi = min(int(round(60.0 / lo_bpm / dt)), len(ac) - 1)
    band = ac[lo:hi + 1].copy()
    out = []
    for _ in range(top):
        k = int(band.argmax())
        lag = k + lo
        out.append((60.0 / (lag * dt), float(band[k])))
        band[max(0, k - 3):k + 4] = -np.inf
    return out


def beat_phase(env, dt, bpm):
    period = 60.0 / bpm / dt
    best, best_score = 0.0, -np.inf
    steps = max(int(round(period)), 1)
    for s in range(steps):
        idx = np.round(np.arange(s, len(env), period)).astype(int)
        idx = idx[idx < len(env)]
        score = env[idx].sum()
        if score > best_score:
            best_score, best = score, s * dt
    return best, best_score


def beat_times(phase, bpm, duration):
    period = 60.0 / bpm
    return np.arange(phase, duration, period)


def downbeat_offset(beats, chord_onsets, per_bar=4):
    """Pick which beat starts a bar by how many chord changes land on it."""
    scores = []
    for off in range(per_bar):
        bars = beats[off::per_bar]
        if len(bars) < 2:
            scores.append((0.0, off))
            continue
        hits = 0.0
        for t in chord_onsets:
            d = np.abs(bars - t).min()
            hits += max(0.0, 1.0 - d / (0.5 * (beats[1] - beats[0])))
        scores.append((hits / len(chord_onsets), off))
    scores.sort(reverse=True)
    return scores
