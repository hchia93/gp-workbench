"""Check a .gp for the two failure modes Guitar Pro will not report: dangling id
references and bars whose beats do not add up to the time signature."""

import re
import sys
import zipfile
from fractions import Fraction

VALUES = {"Whole": 1, "Half": 2, "Quarter": 4, "Eighth": 8, "16th": 16, "32nd": 32, "64th": 64}


def _table(xml, plural, single):
    m = re.search(r"<%s>\s*(<%s id=.*?)</%s>" % (plural, single, plural), xml, re.S)
    if not m:
        return {}
    out = {}
    for item in re.finditer(r'<%s id="(\d+)"\s*(?:/>|>(.*?)</%s>)' % (single, single), m.group(1), re.S):
        out[int(item.group(1))] = item.group(2) or ""
    return out


def _refs(body, tag):
    m = re.search(r"<%s>([\d\s-]*)</%s>" % (tag, tag), body)
    return [int(v) for v in m.group(1).split()] if m and m.group(1).strip() else []


def check(path):
    xml = zipfile.ZipFile(path).read("Content/score.gpif").decode("utf-8")
    bars = _table(xml, "Bars", "Bar")
    voices = _table(xml, "Voices", "Voice")
    beats = _table(xml, "Beats", "Beat")
    notes = _table(xml, "Notes", "Note")
    rhythms = _table(xml, "Rhythms", "Rhythm")

    # each MasterBar carries its own time signature, so map bar id -> expected duration
    sigs = {}
    current = None
    for mb in re.finditer(r"<MasterBar>(.*?)</MasterBar>", xml, re.S):
        t = re.search(r"<Time>(\d+)/(\d+)</Time>", mb.group(1))
        if t:
            current = Fraction(int(t.group(1)), int(t.group(2)))
        for bid in _refs(mb.group(1), "Bars"):
            sigs[bid] = current

    errors, warnings = [], []
    for bid, body in bars.items():
        expected = sigs.get(bid)
        for vid in _refs(body, "Voices"):
            if vid == -1:
                continue
            if vid not in voices:
                errors.append(f"bar {bid} -> missing voice {vid}")
                continue
            total = Fraction(0)
            for beat_id in _refs(voices[vid], "Beats"):
                if beat_id not in beats:
                    errors.append(f"voice {vid} -> missing beat {beat_id}")
                    continue
                body_b = beats[beat_id]
                for nid in _refs(body_b, "Notes"):
                    if nid not in notes:
                        errors.append(f"beat {beat_id} -> missing note {nid}")
                rm = re.search(r'<Rhythm ref="(\d+)"', body_b)
                if not rm or int(rm.group(1)) not in rhythms:
                    errors.append(f"beat {beat_id} -> missing rhythm")
                    continue
                r = rhythms[int(rm.group(1))]
                value = VALUES[re.search(r"<NoteValue>(\w+)</NoteValue>", r).group(1)]
                dur = Fraction(1, value)
                dots = re.search(r'<AugmentationDot count="(\d+)"', r)
                if dots:
                    dur *= Fraction(2) - Fraction(1, 2 ** int(dots.group(1)))
                total += dur
            if expected and total != expected:
                # Guitar Pro tolerates short bars, so this is a smell not a hard error
                warnings.append(f"bar {bid} duration {total} != {expected}")

    used = {n for b in beats.values() for n in _refs(b, "Notes")}
    orphan = set(notes) - used
    if orphan:
        errors.append(f"{len(orphan)} orphan notes")

    print(f"{path}")
    print(f"  bars={len(bars)} voices={len(voices)} beats={len(beats)} notes={len(notes)} time={sorted({str(v) for v in sigs.values()})}")
    for w in warnings[:5]:
        print("  WARN", w)
    if warnings[5:]:
        print(f"  WARN +{len(warnings) - 5} more short bars")
    for e in errors[:20]:
        print("  FAIL", e)
    if not errors and not warnings:
        print("  OK")
    return not errors


if __name__ == "__main__":
    sys.exit(0 if all(check(p) for p in sys.argv[1:]) else 1)
