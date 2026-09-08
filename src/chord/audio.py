"""Chroma extraction and chord matching from a mono wav. numpy only.

Deliberately blind to any key or chord vocabulary coming from other sources:
this has to stay an independent witness or cross-checking it proves nothing.
"""

import wave

import numpy as np

A4 = 440.0
PITCH_LOW = 36
PITCH_HIGH = 96
MAJOR = [0, 4, 7]
MINOR = [0, 3, 7]
NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def read_wav(path):
    with wave.open(path, "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("expected mono 16-bit wav")
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    return rate, np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0


def _pitch_bands(rate, n_fft):
    freqs = np.fft.rfftfreq(n_fft, 1.0 / rate)
    bands = []
    for p in range(PITCH_LOW, PITCH_HIGH):
        center = A4 * 2.0 ** ((p - 69) / 12.0)
        lo, hi = center * 2.0 ** (-1 / 24.0), center * 2.0 ** (1 / 24.0)
        idx = np.nonzero((freqs >= lo) & (freqs < hi))[0]
        bands.append((p, idx))
    return bands


def chroma(rate, x, n_fft=8192, hop=2048):
    window = np.hanning(n_fft)
    bands = _pitch_bands(rate, n_fft)
    frames = 1 + (len(x) - n_fft) // hop
    out = np.zeros((frames, 12))
    for i in range(frames):
        seg = x[i * hop:i * hop + n_fft] * window
        mag = np.abs(np.fft.rfft(seg))
        for p, idx in bands:
            if idx.size:
                out[i, p % 12] += mag[idx].sum()
    return out, hop / rate


def smooth(c, frames):
    if frames < 2:
        return c
    kernel = np.ones(frames) / frames
    return np.stack([np.convolve(c[:, k], kernel, mode="same") for k in range(12)], axis=1)


def smooth_median(c, frames):
    """Median, not mean, over the window.

    A melody note is a brief spike on one pitch class while the chord tones hold
    for the whole span. Averaging keeps the spike and it lands on the third, the
    one degree that decides major against minor.
    """
    if frames < 2:
        return c
    pad = frames // 2
    padded = np.pad(c, ((pad, pad), (0, 0)), mode="edge")
    out = np.empty_like(c)
    for i in range(len(c)):
        out[i] = np.median(padded[i:i + frames], axis=0)
    return out


def templates():
    out = []
    for root in range(12):
        for quality, tones in (("", MAJOR), ("m", MINOR)):
            v = np.zeros(12)
            for t in tones:
                v[(root + t) % 12] = 1.0
            out.append((NAMES[root] + quality, v / np.linalg.norm(v)))
    return out


def match(c):
    temps = templates()
    mat = np.stack([v for _, v in temps])
    norms = np.linalg.norm(c, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    scores = (c / norms) @ mat.T
    best = scores.argmax(axis=1)
    return [temps[b][0] for b in best], scores.max(axis=1)


def runs(labels, dt, min_len=0.5):
    out = []
    start = 0
    for i in range(1, len(labels) + 1):
        if i < len(labels) and labels[i] == labels[start]:
            continue
        if (i - start) * dt >= min_len:
            out.append({"t": round(start * dt, 2), "dur": round((i - start) * dt, 2), "chord": labels[start]})
        start = i
    return out


def chroma_band(rate, x, lo_pitch, hi_pitch, n_fft=8192, hop=2048, compress=0.5):
    window = np.hanning(n_fft)
    freqs = np.fft.rfftfreq(n_fft, 1.0 / rate)
    bands = []
    for p in range(lo_pitch, hi_pitch):
        center = A4 * 2.0 ** ((p - 69) / 12.0)
        idx = np.nonzero((freqs >= center * 2.0 ** (-1 / 24.0)) & (freqs < center * 2.0 ** (1 / 24.0)))[0]
        bands.append((p, idx))
    frames = 1 + (len(x) - n_fft) // hop
    out = np.zeros((frames, 12))
    for i in range(frames):
        mag = np.abs(np.fft.rfft(x[i * hop:i * hop + n_fft] * window)) ** compress
        for p, idx in bands:
            if idx.size:
                out[i, p % 12] += mag[idx].sum()
    return out


def _unit(v):
    n = np.linalg.norm(v, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return v / n


def match_with_bass(treble, bass, bass_weight=0.6):
    temps = templates()
    mat = np.stack([v for _, v in temps])
    roots = np.array([NAMES.index(n[:-1] if n.endswith("m") else n) for n, _ in temps])
    harmony = _unit(treble) @ mat.T
    root_support = _unit(bass)[:, roots]
    scores = harmony + bass_weight * root_support
    best = scores.argmax(axis=1)
    return [temps[b][0] for b in best], scores.max(axis=1)


def full_templates():
    """Every quality on every root. Names must round-trip through roman.parse."""
    from . import roman
    out = []
    for root in range(12):
        for quality, tones in roman.QUALITIES:
            out.append((NAMES[root] + quality, root,
                        tuple(sorted({(root + t) % 12 for t in tones}))))
    return out


# How often each quality actually shows up in band, blues and fingerstyle
# writing. Without this the no-third chords win everywhere: sus templates skip
# the one tone that melody and overtones pollute most, so they are always easier
# to satisfy than a plain triad. Values are penalties in score units.
QUALITY_PRIOR = {
    "": 0.0, "m": 0.0,
    "7": 0.004, "m7": 0.005, "maj7": 0.007,
    "sus4": 0.012, "add9": 0.012, "6": 0.013, "sus2": 0.016,
    "m6": 0.016, "madd9": 0.016, "7sus4": 0.016,
    "9": 0.018, "m9": 0.018, "maj9": 0.020,
    "dim": 0.016, "m7b5": 0.018, "dim7": 0.020, "aug": 0.022, "7#9": 0.022,
}


def match_asymmetric(treble, bass, leak=0.30, bass_weight=0.40, complexity=0.010, prior=1.0):
    """Missing chord tones are punished, extra tones barely are.

    Chroma cannot separate a chord tone from a melody note sitting on top of it,
    so a symmetric cosine drags a correct chord toward whichever template happens
    to lack that extra note. Asymmetry is what lets an added 9th stay an added 9th.
    Mean over tones, not sum, or five-note chords would win by covering more.
    """
    from . import roman
    temps = full_templates()
    t = treble / np.maximum(treble.sum(axis=1, keepdims=True), 1e-12)
    b = bass / np.maximum(bass.sum(axis=1, keepdims=True), 1e-12)
    scores = np.empty((len(t), len(temps)))
    for j, (_, root, tones) in enumerate(temps):
        mask = np.zeros(12, dtype=bool)
        mask[list(tones)] = True
        inside = t[:, mask].mean(axis=1)
        outside = t[:, ~mask].mean(axis=1)
        quality = roman.parse(temps[j][0]).quality
        scores[:, j] = (inside - leak * outside + bass_weight * b[:, root]
                        - complexity * len(tones) - prior * QUALITY_PRIOR.get(quality, 0.02))
    best = scores.argmax(axis=1)
    return [temps[k][0] for k in best], scores.max(axis=1)
