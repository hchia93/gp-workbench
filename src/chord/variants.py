"""Group disputed chords into phrases and enumerate whole-phrase alternatives.

Per-chord variants would be a cartesian product: 19 disputes at ~3 candidates
each is 3**19. Phrases keep it linear, and an arranger's intent is a phrase-level
decision anyway, so a phrase is also the right thing to listen to.
"""

import json

from . import roman

GAP = 3.0          # disputes closer than this belong to one phrase
CONTEXT = 1.0      # seconds of surrounding audio to keep for the ear


def group(disputes, gap=GAP):
    groups, cur = [], []
    for d in disputes:
        if cur and d["t"] - (cur[-1]["t"] + cur[-1]["dur"]) > gap:
            groups.append(cur)
            cur = []
        cur.append(d)
    if cur:
        groups.append(cur)
    return groups


def _nearest_diatonic(chord_name, key):
    """Shared-tone match first, root distance as the fallback.

    Chords like Ebm share no two tones with anything in D, so the tone test
    returns nothing and the label would lie about what the variant contains.
    """
    c = roman.parse(chord_name)
    ranked = roman.neighbors(c, key)
    if ranked:
        return ranked[0][1].name
    best = None
    for d in roman.diatonic_triads(key):
        dist = min((d.root - c.root) % 12, (c.root - d.root) % 12)
        if best is None or dist < best[0]:
            best = (dist, d.name)
    return best[1]


def strategies(members, key):
    """Three readings of the same phrase, deduplicated."""
    detected = [m["detected"] for m in members]
    diatonic = [_nearest_diatonic(m["detected"], key) or m["detected"] for m in members]
    held = [m["prev"] or m["detected"] for m in members]

    out, seen = [], set()
    for chords, label in ((detected, "as detected, non-diatonic kept"),
                          (diatonic, "pulled to nearest diatonic"),
                          (held, "previous chord held through")):
        k = tuple(chords)
        if k in seen:
            continue
        seen.add(k)
        out.append({"letter": chr(65 + len(out)), "label": label, "chords": list(chords)})
    return out


def build(disputes, key, grid):
    bar, phase = grid["bar_seconds"], grid["downbeat_offset"]
    groups = []
    for members in group(disputes):
        t0 = members[0]["t"] - CONTEXT
        t1 = members[-1]["t"] + members[-1]["dur"] + CONTEXT
        groups.append({
            "id": f"g{len(groups)+1:02}",
            "disputes": [m["id"] for m in members],
            "bars": [round((members[0]["t"] - phase) / bar + 1, 1),
                     round((members[-1]["t"] - phase) / bar + 1, 1)],
            "t0": round(max(0.0, t0), 2),
            "t1": round(t1, 2),
            "spans": [{"t": m["t"], "dur": m["dur"]} for m in members],
            "context": {"before": members[0]["prev"], "after": members[-1]["next"]},
            "variants": strategies(members, key),
            "verdict": None,
        })
    return {"key": roman.NAMES[key], "grid": grid, "groups": groups}
