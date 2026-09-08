"""Chord names to scale degrees and back. Pure symbolic, touches no audio."""

import re

PITCH = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

DEGREE_OF_INTERVAL = {
    0: (1, ""), 1: (2, "b"), 2: (2, ""), 3: (3, "b"), 4: (3, ""), 5: (4, ""),
    6: (4, "#"), 7: (5, ""), 8: (6, "b"), 9: (6, ""), 10: (7, "b"), 11: (7, ""),
}

INTERVAL_OF_DEGREE = {v: k for k, v in DEGREE_OF_INTERVAL.items()}

NATURAL_QUALITY = {1: "", 2: "m", 3: "m", 4: "", 5: "", 6: "m", 7: "dim"}

# Band, blues and fingerstyle vocabulary. Order matters: longest suffix wins.
QUALITIES = [
    ("maj9",  (0, 2, 4, 7, 11)),
    ("maj7",  (0, 4, 7, 11)),
    ("m7b5",  (0, 3, 6, 10)),
    ("madd9", (0, 2, 3, 7)),
    ("7sus4", (0, 5, 7, 10)),
    ("dim7",  (0, 3, 6, 9)),
    ("add9",  (0, 2, 4, 7)),
    ("sus2",  (0, 2, 7)),
    ("sus4",  (0, 5, 7)),
    ("7#9",   (0, 3, 4, 7, 10)),
    ("dim",   (0, 3, 6)),
    ("aug",   (0, 4, 8)),
    ("m9",    (0, 2, 3, 7, 10)),
    ("m7",    (0, 3, 7, 10)),
    ("m6",    (0, 3, 7, 9)),
    ("m",     (0, 3, 7)),
    ("9",     (0, 2, 4, 7, 10)),
    ("7",     (0, 4, 7, 10)),
    ("6",     (0, 4, 7, 9)),
    ("",      (0, 4, 7)),
]
QUALITY_TONES = dict(QUALITIES)
# the plain triad each quality reduces to, for degree labels and key ranking
TRIAD_OF = {q: ("dim" if "dim" in q or q == "m7b5" else
                "aug" if q == "aug" else
                "m" if q.startswith("m") and not q.startswith("maj") else "")
            for q, _ in QUALITIES}

_CHORD_RE = re.compile(r"^([A-G][#b]?)([^/]*)(?:/([A-G][#b]?))?$")
_DEGREE_RE = re.compile(r"^([#b]?)([1-7])(.*)$")


class Chord:
    def __init__(self, name, root, quality, bass=None):
        self.name = name
        self.root = root
        self.quality = quality
        self.bass = bass

    def __repr__(self):
        return f"Chord({self.name})"


def _quality_of(suffix):
    s = suffix.strip()
    for q, _ in QUALITIES:
        if q and s == q:
            return q
    for q, _ in QUALITIES:
        if q and s.startswith(q):
            return q
    low = s.lower()
    if "dim" in low or low.startswith("o"):
        return "dim"
    if "aug" in low or low.startswith("+"):
        return "aug"
    if low.startswith("m") and not low.startswith("maj"):
        return "m"
    return ""


def parse(name):
    m = _CHORD_RE.match(name.strip())
    if not m:
        return None
    root, suffix, bass = m.group(1), m.group(2), m.group(3)
    return Chord(name, PITCH[root], _quality_of(suffix), PITCH[bass] if bass else None)


def degree(chord, key):
    number, accidental = DEGREE_OF_INTERVAL[(chord.root - key) % 12]
    label = f"{accidental}{number}{chord.quality}"
    if chord.bass is None:
        return label
    bass_number, bass_accidental = DEGREE_OF_INTERVAL[(chord.bass - key) % 12]
    return f"{label}/{bass_accidental}{bass_number}"


def triad_degree(chord, key):
    """Degree of the underlying triad, extensions dropped.

    A7 and A both read as 5. A degree chart written in triads must not treat
    an extension as a different chord.
    """
    number, accidental = DEGREE_OF_INTERVAL[(chord.root - key) % 12]
    return f"{accidental}{number}{TRIAD_OF.get(chord.quality, '')}"


def chord_name(label, key):
    head = label.split("/")[0]
    m = _DEGREE_RE.match(head)
    if not m:
        return None
    accidental, number, quality = m.group(1), int(m.group(2)), m.group(3)
    root = (key + INTERVAL_OF_DEGREE[(number, accidental)]) % 12
    return NAMES[root] + quality


def scale_tones(key):
    return {(key + i) % 12 for i in (0, 2, 4, 5, 7, 9, 11)}


def is_diatonic(chord, key):
    """Every tone of the chord sits in the key. A D7 is not diatonic in D."""
    return tones(chord) <= scale_tones(key)


def rank_keys(chords):
    scored = [(sum(1 for c in chords if is_diatonic(c, k)), k) for k in range(12)]
    scored.sort(key=lambda p: -p[0])
    return scored


TRIAD = {"": (0, 4, 7), "m": (0, 3, 7), "dim": (0, 3, 6), "aug": (0, 4, 8)}


def tones(chord):
    return {(chord.root + i) % 12 for i in QUALITY_TONES.get(chord.quality, (0, 4, 7))}


def triad_tones(chord):
    return {(chord.root + i) % 12 for i in TRIAD[TRIAD_OF.get(chord.quality, "")]}


def diatonic_triads(key):
    out = []
    for number in range(1, 8):
        root = (key + INTERVAL_OF_DEGREE[(number, "")]) % 12
        quality = NATURAL_QUALITY[number]
        out.append(Chord(NAMES[root] + quality, root, quality))
    return out


def neighbors(chord, key):
    mine = tones(chord)
    scored = [(len(mine & tones(c)), c) for c in diatonic_triads(key)]
    scored = [p for p in scored if p[0] >= 2]
    scored.sort(key=lambda p: -p[0])
    return scored
