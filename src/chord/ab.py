"""Render A/B candidates for disputed chords: synth the candidate over the
original audio so the ear can judge. Wrong chord clashes, right chord locks in.
"""

import json
import wave

import numpy as np

from . import roman

PARTIALS = ((1.0, 1.0), (2.0, 0.35), (3.0, 0.18), (4.0, 0.09))


def synth(chord_name, seconds, rate, root_midi=52, gain=0.22):
    c = roman.parse(chord_name)
    t = np.arange(int(seconds * rate)) / rate
    out = np.zeros_like(t)
    root = root_midi + ((c.root - root_midi) % 12)
    for k, semi in enumerate(sorted(roman.QUALITY_TONES.get(c.quality, (0, 4, 7)))):
        midi = root + semi
        f = 440.0 * 2.0 ** ((midi - 69) / 12.0)
        env = np.exp(-1.6 * (t % 1.0)) * (1 - np.exp(-60 * (t % 1.0)))
        for mult, amp in PARTIALS:
            out += amp * env * np.sin(2 * np.pi * f * mult * t + k)
    peak = np.abs(out).max()
    return gain * out / peak if peak else out


def write_wav(path, rate, x):
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def render(rate, song, t0, dur, chord_name, out_path, pad=1.0):
    lo = max(0, int((t0 - pad) * rate))
    hi = min(len(song), int((t0 + dur + pad) * rate))
    clip = song[lo:hi].astype(np.float64).copy()
    peak = np.abs(clip).max()
    if peak:
        clip /= peak
    lead = int(pad * rate)
    body = synth(chord_name, (hi - lo - lead) / rate, rate)
    mix = clip * 0.75
    mix[lead:lead + len(body)] += body
    write_wav(out_path, rate, mix)


def candidates(chord_name, key, neighbours=()):
    """Detected chord, then whatever it could plausibly be instead.

    Neighbouring chords go in even when they share no tones: a lone odd chord
    between two identical ones is usually that one held, not a new chord.
    """
    c = roman.parse(chord_name)
    mine = roman.tones(c)
    out = [chord_name]
    scored = []
    for d in roman.diatonic_triads(key):
        shared = len(mine & roman.tones(d))
        if shared >= 2 and d.name != chord_name:
            scored.append((shared, d.name))
    scored.sort(reverse=True)
    for _, n in scored[:2]:
        if n not in out:
            out.append(n)
    for n in neighbours:
        if n and n not in out:
            out.append(n)
    return out


def read_song(path):
    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    return rate, np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0


def render_phrase(rate, song, t0, t1, spans, chords, out_path):
    """Original audio for a whole phrase, with one candidate laid over each span."""
    lo, hi = max(0, int(t0 * rate)), min(len(song), int(t1 * rate))
    clip = song[lo:hi].astype(np.float64).copy()
    peak = np.abs(clip).max()
    if peak:
        clip /= peak
    mix = clip * 0.75
    for span, name in zip(spans, chords):
        at = int((span["t"] - t0) * rate)
        body = synth(name, span["dur"], rate)
        end = min(at + len(body), len(mix))
        if at < len(mix):
            mix[at:end] += body[:end - at]
    write_wav(out_path, rate, mix)
