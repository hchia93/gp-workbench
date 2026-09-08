"""Cross-check independent chord sources against each other.

Reports disagreements, never resolves them. Anything the checks cannot decide
comes out as UNKNOWN with its position, per the project rule that scripts do
not guess.
"""

import json

from . import roman


class Finding:
    def __init__(self, kind, where, detail):
        self.kind = kind
        self.where = where
        self.detail = detail


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def source_by_id(data, sid):
    for s in data["sources"]:
        if s["id"] == sid:
            return s
    return None


def flatten_chart(section):
    out = []
    for i, line in enumerate(section["lines"]):
        for label in line["degrees"]:
            out.append((label, i))
    return out


def longest_common_run(a, b):
    best = (0, 0, 0)
    table = {}
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            if x != y:
                continue
            run = table.get((i - 1, j - 1), 0) + 1
            table[(i, j)] = run
            if run > best[0]:
                best = (run, i - run + 1, j - run + 1)
    return best


def infer_key(chords, chart_degrees):
    ranked = roman.rank_keys(chords)
    top, runner = ranked[0], ranked[1]
    findings = []
    if top[0] == runner[0]:
        findings.append(Finding("UNKNOWN", "key", f"tie between {roman.NAMES[top[1]]} and {roman.NAMES[runner[1]]}"))
        return None, ranked, findings
    return top[1], ranked, findings


def check_vocabulary(events, key, chart_labels):
    findings = []
    for e in events:
        c = roman.parse(e["chord"])
        if c is None:
            findings.append(Finding("UNPARSED", f"t={e['t']}", e["chord"]))
            continue
        label = roman.degree(c, key)
        head = roman.triad_degree(c, key)
        if not roman.is_diatonic(c, key):
            cand = ", ".join(f"{n.name}({s} shared)" for s, n in roman.neighbors(c, key))
            detail = f"{e['chord']} = {label}   candidates: {cand or 'none'}"
            findings.append(Finding("OUTSIDE_KEY", f"t={e['t']}", detail))
        elif "/" in label:
            findings.append(Finding("SLASH_REFINEMENT", f"t={e['t']}", f"{e['chord']} = {label}"))
        elif head not in chart_labels:
            findings.append(Finding("NOT_IN_CHART", f"t={e['t']}", f"{e['chord']} = {label}"))
    return findings


def degrees_of(events, key):
    out = []
    for e in events:
        c = roman.parse(e["chord"])
        out.append(roman.degree(c, key) if c else "?")
    return out


def report(path):
    data = load(path)
    timeline = source_by_id(data, "chord-tell")
    chart = source_by_id(data, "numeric-chart")
    events = timeline["events"]
    chords = [roman.parse(e["chord"]) for e in events]
    chords = [c for c in chords if c]

    lines = []
    lines.append(f"{data['song']} - {data['artist']}")
    lines.append("")
    lines.append(f"source A  {timeline['id']:16} {len(events)} events   [{timeline['kind']}]")
    total_chart = sum(len(s['lines']) for s in chart["sections"])
    lines.append(f"source B  {chart['id']:16} {total_chart} lines    [{chart['kind']}]")
    lines.append("")

    chart_labels = set()
    for section in chart["sections"]:
        for line in section["lines"]:
            chart_labels.update(line["degrees"])

    key, ranked, findings = infer_key(chords, chart_labels)
    lines.append("KEY")
    for hits, k in ranked[:3]:
        mark = "<--" if key is not None and k == key else ""
        lines.append(f"  {roman.NAMES[k]:3} {hits}/{len(chords)} diatonic {mark}")
    if key is None:
        lines.append("  UNKNOWN, tie")
        return "\n".join(lines), findings
    lines.append("")

    lines.append(f"TIMELINE AS DEGREES IN {roman.NAMES[key]}")
    seq = degrees_of(events, key)
    lines.append("  " + " ".join(seq))
    lines.append("")

    lines.append("CHART VOCABULARY")
    lines.append("  " + " ".join(sorted(chart_labels, key=lambda s: (s[0], s))))
    lines.append("  as chords: " + " ".join(roman.chord_name(x, key) or "?" for x in sorted(chart_labels, key=lambda s: (s[0], s))))
    lines.append("")

    findings += check_vocabulary(events, key, chart_labels)

    lines.append("SECTION MATCH")
    bare = [s.split("/")[0] for s in seq]
    for section in chart["sections"]:
        flat = flatten_chart(section)
        run, i, j = longest_common_run(bare, [x for x, _ in flat])
        pct = 100.0 * run / len(bare)
        lines.append(f"  {section['name']:10} longest common run {run}/{len(bare)} ({pct:.0f}%)")
        if run:
            lines.append(f"             timeline[{i}:{i+run}] = {' '.join(bare[i:i+run])}")
            lines.append(f"             chart line {flat[j][1] + 1}")
        if pct < 50:
            findings.append(Finding("UNMATCHED_SECTION", section["name"], f"only {run} of {len(bare)} contiguous"))
    lines.append("")

    lines.append("FINDINGS")
    if not findings:
        lines.append("  none")
    for f in findings:
        lines.append(f"  [{f.kind:18}] {f.where:12} {f.detail}")

    return "\n".join(lines), findings


if __name__ == "__main__":
    import sys
    text, _ = report(sys.argv[1])
    print(text)
