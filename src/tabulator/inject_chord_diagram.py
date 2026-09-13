# -*- coding: utf-8 -*-
"""Read chords off a Guitar Pro 8 score and inject diagrams and chord marks.

    python src/tabulator/inject_chord_diagram.py in.gp out.gp
        [--key D] [--dry-run]

Names are chosen the way the program's chord tool lists them: every spelling
that fits the fretted notes is a candidate, and the pick prefers a chord tone
in the bass over an odd root, a root inside the key, and a root that the next
chord confirms. --dry-run prints the aliases it passed over. The key defaults
to the score's key signature.

Chords are inferred per bar from what is actually fretted, so one bar may carry
one chord or four, and a chord that runs on into the next bar is not marked
twice. A strike whose bass is another tone of the chord before it, with the
fingers held or moved by a step, is that chord walking and gets no mark. The
file is patched in place as text; nothing drawn in Guitar Pro is regenerated.
"""

import argparse
import io
import re
import sys

sys.path.insert(0, ".")

from src.gp_ops.patcher import load_gpif, save_gpif

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
STEP = {0: ("C", "Natural"), 1: ("C", "Sharp"), 2: ("D", "Natural"), 3: ("D", "Sharp"),
        4: ("E", "Natural"), 5: ("F", "Natural"), 6: ("F", "Sharp"), 7: ("G", "Natural"),
        8: ("G", "Sharp"), 9: ("A", "Natural"), 10: ("A", "Sharp"), 11: ("B", "Natural")}
TUNING = {1: 64, 2: 59, 3: 55, 4: 50, 5: 45, 6: 40}
BASS_STRINGS = (4, 5, 6)

# Suffixes follow the library's own naming (D7M, Bm7, Asus4, ...). Order is the
# tiebreak: earlier wins when two templates fit equally.
QUALITIES = [
    ("",     (0, 4, 7)), ("m",    (0, 3, 7)), ("7",   (0, 4, 7, 10)), ("7M",   (0, 4, 7, 11)),
    ("m7",   (0, 3, 7, 10)), ("sus4", (0, 5, 7)), ("sus2", (0, 2, 7)), ("m7b5", (0, 3, 6, 10)),
    ("dim",  (0, 3, 6)), ("add9", (0, 2, 4, 7)), ("6",  (0, 4, 7, 9)), ("m6",   (0, 3, 7, 9)),
    ("9",    (0, 2, 4, 7, 10)), ("m9", (0, 2, 3, 7, 10)),
    ("7sus4", (0, 5, 7, 10)), ("7sus2", (0, 2, 7, 10)),
]
RARE = {"m7b5", "dim", "add9", "6", "m6", "9", "7sus4", "7sus2"}
# a seventh chord with no third is the last resort: it counts as missing one note
SUS = {"7sus4", "7sus2"}
MAJOR = (0, 2, 4, 5, 7, 9, 11)
# how welcome each scale degree is as a chord root, I IV V first, vii last
DEGREE_RANK = {0: 0, 3: 0, 4: 0, 1: 1, 5: 1, 2: 2, 6: 3}
DEGREE = {2: ("Second", "Major"), 3: ("Third", "Minor"), 4: ("Third", "Major"),
          5: ("Fourth", "Perfect"), 6: ("Fifth", "Diminished"), 7: ("Fifth", "Perfect"),
          9: ("Sixth", "Major"), 10: ("Seventh", "Minor"), 11: ("Seventh", "Major")}


# ---- gpif reading --------------------------------------------------------------

def read_score(xml):
    """Bars as lists of (beat_id, [(string, fret, midi)]) plus each bar's voice id."""
    notes = {}
    for nid, body in re.findall(r'<Note id="(\d+)">(.*?)</Note>', xml, re.S):
        st = re.search(r"<String>(\d+)</String>", body)
        fr = re.search(r"<Fret>(\d+)</Fret>", body)
        if st and fr:
            string = 6 - int(st.group(1))
            notes[nid] = (string, int(fr.group(1)), TUNING[string] + int(fr.group(1)))
    beats = {}
    for bid, body in re.findall(r'<Beat id="(\d+)">(.*?)</Beat>', xml, re.S):
        ns = re.search(r"<Notes>(.*?)</Notes>", body)
        ids = ns.group(1).split() if ns else []
        beats[bid] = [notes[i] for i in ids if i in notes]
    voices = {vid: re.search(r"<Beats>(.*?)</Beats>", body).group(1).split()
              for vid, body in re.findall(r'<Voice id="(\d+)">(.*?)</Voice>', xml, re.S)}
    bars = {bid: re.search(r"<Voices>(.*?)</Voices>", body).group(1).split()
            for bid, body in re.findall(r'<Bar id="(\d+)">(.*?)</Bar>', xml, re.S)}
    out = []
    for mb in re.findall(r"<MasterBar>.*?<Bars>(.*?)</Bars>.*?</MasterBar>", xml, re.S):
        v0 = bars[mb.split()[0]][0]
        seq = [(b, beats[b]) for b in voices[v0]] if v0 != "-1" else []
        out.append((seq, v0))
    return out


# ---- chord inference -----------------------------------------------------------

def is_start(beat_notes, at_bar_start):
    if len(beat_notes) < 2:
        return False
    return at_bar_start or any(s in BASS_STRINGS for s, _, _ in beat_notes)


def segments(bars):
    """Yield (bar, beat index, voicing) for every chord start in the score.

    A chord is what the thumb lays down with the fingers, so a start is a beat
    with two notes and a bass. Its tones are the start beat, every two-note beat
    after it, and the first lone bass after it. Later lone notes are the inner
    bass walking or a passing tone and would only add wrong extensions.
    """
    last = set()
    for b, (seq, _) in enumerate(bars):
        starts = [i for i, (_, ns) in enumerate(seq) if is_start(ns, i == 0 or not any(len(x[1]) > 1 for x in seq[:i]))]
        # fingers still on the previous chord with no thumb under them are that
        # chord going on, not a new one
        kept = [i for i in starts if any(s in BASS_STRINGS for s, _, _ in seq[i][1])
                or not {m % 12 for _, _, m in seq[i][1]} <= last]
        # what those fingers were sounding is still ringing when the thumb lands,
        # provided the thumb lands under the same fingers
        carry = {}
        if kept and kept[0] > (starts[0] if starts else 0):
            for _, ns in seq[starts[0]:kept[0]]:
                if len(ns) > 1:
                    for s, f, m in ns:
                        carry.setdefault(s, (f, m))
            fingers = {m % 12 for s, _, m in seq[kept[0]][1] if s not in BASS_STRINGS}
            if not fingers <= {m % 12 for _, (_, m) in carry.items()}:
                carry = {}
        starts = kept
        # fingers that open the bar before the thumb arrives are the same chord
        # as the thumb's strike, as long as no lone bass note sits in between
        has_bass = lambda ns: any(s in BASS_STRINGS for s, _, _ in ns)
        merged = []
        for n, i in enumerate(starts):
            prev = merged[-1] if merged else None
            if prev is not None and not has_bass(seq[prev][1]) and has_bass(seq[i][1]) \
                    and not any(len(ns) == 1 and has_bass(ns) for _, ns in seq[prev + 1:i]):
                continue
            merged.append(i)
        starts = merged
        for n, i in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(seq)
            voicing = dict(carry) if n == 0 else {}
            # a start without a bass gets its root from the first lone bass after
            # it; a start that has one already treats later lone basses as the
            # inner bass walking, which is what turns a G into a G7M
            need_bass = not any(s in BASS_STRINGS for s, _, _ in seq[i][1])
            # a thumb that struck on 5 or 6 and then alternates on 4 is playing
            # the same chord; a lone note anywhere else is a walk or a passing tone
            deep = any(s in (5, 6) for s, _, _ in seq[i][1])
            for j in range(i, end):
                ns = seq[j][1]
                if j == i or len(ns) > 1:
                    for s, f, m in ns:
                        voicing.setdefault(s, (f, m))
                elif need_bass and len(ns) == 1 and ns[0][0] in BASS_STRINGS:
                    s, f, m = ns[0]
                    voicing.setdefault(s, (f, m))
                    need_bass = False
                elif deep and len(ns) == 1 and ns[0][0] == 4:
                    s, f, m = ns[0]
                    voicing.setdefault(s, (f, m))
            last = {m % 12 for _, (_, m) in voicing.items()}
            yield b, i, voicing


def walks_on(voicing, prev_voicing, prev_named):
    """True when this strike is the previous chord going on, not a new one.

    The thumb has moved to another tone of the chord it was already under and
    the fingers have stayed or stepped to a neighbour, so the bass note it left
    is still ringing under the new one. Bm7 with the thumb on D is still Bm7.
    """
    if not prev_named:
        return False
    _, root, _, tones, _ = prev_named[:5]
    chord = {(root + t) % 12 for t in tones}
    bass = min(m for _, (_, m) in voicing.items())
    if bass % 12 == root or bass % 12 not in chord:
        return False
    held = {m % 12 for _, (_, m) in prev_voicing.items()}
    for _, (_, m) in voicing.items():
        if m == bass:
            continue
        pc = m % 12
        if pc not in chord and not any(min((pc - h) % 12, (h - pc) % 12) <= 2 for h in held):
            return False
    return True


def key_of(xml, override=None):
    """Tonic pitch class of the key, from --key or the first bar's signature."""
    if override:
        m = re.match(r"([A-G])([#b]?)(m?)$", override)
        if not m:
            sys.exit(f"unknown key {override}")
        pc = NAMES.index(m.group(1)) + {"#": 1, "b": -1, "": 0}[m.group(2)]
        return (pc + (3 if m.group(3) else 0)) % 12
    acc = int(re.search(r"<AccidentalCount>(-?\d+)</AccidentalCount>", xml).group(1))
    minor = re.search(r"<Mode>Minor</Mode>", xml) is not None
    return ((acc * 7) % 12 + (3 if minor else 0)) % 12


def candidates(voicing, tonic, next_root=None):
    """Every spelling that fits, best first.

    The order is the program's habit: complete chords before incomplete ones,
    then a bass that is a chord tone (a slash chord) before a bass that forces
    an odd root, then a root that the next chord repeats (the bass got there
    early), then plain qualities before rare ones, then roots high in the key.
    """
    pcs = {m % 12 for _, (_, m) in voicing.items()}
    bass = min(m for _, (_, m) in voicing.items()) % 12
    scale = {(tonic + d) % 12: i for i, d in enumerate(MAJOR)}
    out = []
    for root in range(12):
        rel = {(p - root) % 12 for p in pcs}
        for rank, (suffix, tones) in enumerate(QUALITIES):
            tset = set(tones)
            if rel - tset:
                continue
            bass_rel = (bass - root) % 12
            if root != bass and bass_rel not in tset:
                continue
            missing = tset - rel
            root_missing = 0 in missing
            if root_missing and root != next_root:
                continue
            # a bass that has already moved to the next chord's tone is that
            # chord in inversion, not a new root
            early = root != bass and root == next_root
            name = NAMES[root] + suffix + ("/" + NAMES[bass] if root != bass else "")
            # a spelling that implies notes outside the key loses to one that stays in it
            foreign = sum(1 for i in tset if (root + i) % 12 not in scale)
            score = (len(missing - {0}) + (suffix in SUS), root != bass and not early, root_missing and not early,
                     foreign, suffix in RARE, DEGREE_RANK.get(scale.get(root, -1), 4), rank)
            out.append((score, name, root, bass, tones, pcs))
    out.sort(key=lambda c: c[0])
    return [c[1:] for c in out]


def name_chord(voicing, tonic=0, next_root=None):
    got = candidates(voicing, tonic, next_root)
    return got[0] if got else None


# ---- xml emit ------------------------------------------------------------------

def item_xml(cid, name, root, bass, tones, pcs, voicing):
    frets = sorted((6 - s, f) for s, (f, _) in voicing.items())
    fr = "\n".join(f'<Fret string="{s}" fret="{f}"/>' for s, f in frets)
    played = {s for s, _ in frets}
    pos = "\n".join(f'<Position finger="None" fret="{f}" string="{s}"/>' for s, f in frets)
    pos += "".join(f'\n<Position finger="None" fret="4294967295" string="{s}"/>' for s in range(6) if s not in played)
    deg = "\n".join(f'<Degree interval="{DEGREE[i][0]}" alteration="{DEGREE[i][1]}" '
                    f'omitted="{str((root + i) % 12 not in pcs).lower()}"/>' for i in tones if i)
    ks, ka = STEP[root]
    bs, ba = STEP[bass]
    idattr = f' id="{cid}"' if cid is not None else ""
    return (f'<Item{idattr} name="{name}">\n'
            f'<Diagram stringCount="6" fretCount="5" baseFret="0" barsStates="1 1 1 1 1">\n{fr}\n'
            f"<Fingering>\n{pos}\n</Fingering>\n"
            '<Property name="ShowName" type="bool" value="true" />\n'
            '<Property name="ShowDiagram" type="bool" value="true" />\n'
            '<Property name="ShowFingering" type="bool" value="false" />\n'
            f'</Diagram>\n<Chord>\n<KeyNote step="{ks}" accidental="{ka}"/>\n'
            f'<BassNote step="{bs}" accidental="{ba}"/>\n{deg}\n</Chord>\n</Item>')


def existing_items(xml):
    """Diagrams already in the track's collection, name -> (id, item xml).

    Kept as they are on a rerun: hand made diagrams live here too, and the chord
    reader only names what it can infer from the fretted notes.
    """
    m = re.search(r'<Property name="DiagramCollection">\s*<Items>(.*?)</Items>', xml, re.S)
    if not m:
        return {}
    out = {}
    for item in re.findall(r'<Item id="\d+" name="[^"]*">.*?</Item>', m.group(1), re.S):
        cid = int(re.search(r'id="(\d+)"', item).group(1))
        out[re.search(r'name="([^"]*)"', item).group(1)] = (cid, item)
    return out


def clone_beat(xml, bid):
    new_id = max(int(i) for i in re.findall(r'<Beat id="(\d+)">', xml)) + 1
    m = re.search(r'<Beat id="%s">.*?</Beat>' % bid, xml, re.S)
    copy = m.group(0).replace(f'<Beat id="{bid}">', f'<Beat id="{new_id}">', 1)
    return xml[:m.end()] + "\n" + copy + xml[m.end():], new_id


def voice_slots(xml, vid):
    m = re.search(r'(<Voice id="%s">.*?<Beats>)(.*?)(</Beats>)' % vid, xml, re.S)
    return m, m.group(2).split()


def mark_beat(xml, vid, k, cid):
    """Put the chord reference on a private copy of the beat.

    Guitar Pro shares one <Beat> between every position with identical content,
    so writing into it in place would label every bar that reuses it.
    """
    m, ids = voice_slots(xml, vid)
    bid = ids[k]
    body = re.search(r'<Beat id="%s">(.*?)</Beat>' % bid, xml, re.S).group(1)
    if "<Chord>" in body:
        return xml, False
    xml, nb = clone_beat(xml, bid)
    m, ids = voice_slots(xml, vid)
    ids[k] = str(nb)
    xml = xml[:m.start(2)] + " ".join(ids) + xml[m.end(2):]
    pat = re.compile(r'(<Beat id="%s">.*?)(<Notes>)' % nb, re.S)
    return pat.sub(lambda mm: mm.group(1) + f"<Chord><![CDATA[{cid}]]></Chord>\n" + mm.group(2), xml, count=1), True


def lyrics_xml(lines):
    lines = lines or [(0, "")]
    body = "\n".join(f"<Line>\n<Text><![CDATA[{t}]]></Text>\n<Offset>{o}</Offset>\n</Line>" for o, t in lines)
    return f'<Lyrics dispatched="true">\n{body}\n</Lyrics>'


# ---- main ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--key", help="D, Bm, F#, Ebm ... (default: the score's key signature)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    xml = load_gpif(args.src)
    bars = read_score(xml)
    tonic = key_of(xml, args.key)

    kept = existing_items(xml)
    marks, fresh = [], []
    ids = {n: cid for n, (cid, _) in kept.items()}
    next_id = max(ids.values(), default=-1) + 1
    segs = list(segments(bars))
    # a first pass names every chord on its own, the second lets each one see
    # the root of the chord after it
    first = [name_chord(v, tonic) or (None, None) for _, _, v in segs]
    prev = None
    prev_named, prev_voicing = None, {}
    aliases = {}
    for n, (b, i, voicing) in enumerate(segs):
        if walks_on(voicing, prev_voicing, prev_named):
            continue
        # the chord after this one, skipping restrikes of the same shape
        following = next((f[1] for f in first[n + 1:] if f[0] is not None and f[0] != first[n][0]), None)
        found = candidates(voicing, tonic, following)
        if not found:
            continue
        named = found[0]
        name = named[0]
        prev_named, prev_voicing = named, voicing
        aliases[(b, i)] = [c[0] for c in found[1:5]]
        if name not in ids:
            ids[name] = next_id
            next_id += 1
            fresh.append((name, item_xml(next_id - 1, name, *named[1:], voicing)))
        if name != prev:
            marks.append((b, i, name))
        prev = name

    for b, i, name in marks:
        others = aliases.get((b, i), [])
        print(f"  bar {b + 1:>2} beat {i + 1}  {name:<8}" + (f"  also {', '.join(others)}" if others and args.dry_run else ""))
    names = list(kept) + [n for n, _ in fresh]
    print(f"{len(marks)} chord marks, {len(names)} diagrams: {', '.join(names)}"
          + (f" (kept {len(kept)})" if kept else ""))
    if args.dry_run:
        return

    # Collection holds the definitions the marks point at by id, the working set
    # is what the Chords panel lists as the track's diagram library.
    every = [body for _, body in kept.values()] + [body for _, body in fresh]
    coll = "<Items>\n" + "\n".join(every) + "\n</Items>"
    work = "<Items>\n" + "\n".join(re.sub(r'<Item id="\d+" ', "<Item ", b, count=1) for b in every) + "\n</Items>"
    xml = re.sub(r'(<Property name="DiagramCollection">\s*)<Items(?:/>|>.*?</Items>)',
                 lambda m: m.group(1) + coll, xml, count=1, flags=re.S)
    xml = re.sub(r'(<Property name="DiagramWorkingSet">\s*)<Items(?:/>|>.*?</Items>)',
                 lambda m: m.group(1) + work, xml, count=1, flags=re.S)

    placed = 0
    for b, i, name in marks:
        xml, done = mark_beat(xml, bars[b][1], i, ids[name])
        placed += done

    save_gpif(args.src, args.out, xml)
    print(f"placed {placed} marks -> {args.out}")


if __name__ == "__main__":
    main()
