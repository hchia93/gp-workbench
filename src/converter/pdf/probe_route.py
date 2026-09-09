"""Split the library by the only question that decides the pipeline:

can the fret numbers be read out of the PDF's text layer?

Producer strings and image counts only correlate with the answer. The test that
actually decides it is running the text-layer reader and seeing whether TAB
digits come back, so that is what this does.

Usage: gp-workbench route <file.pdf>
"""

import re
from collections import Counter, defaultdict

from src.converter.pdf.extract_content import extract
from src.converter.pdf.find_staff import attach_notes, find_barlines, find_staves, pair_systems


TEXT_ROUTE = "text-layer"      # fret digits recoverable, deterministic
IMAGE_ROUTE = "image"          # needs recognition
EMPTY = "no-staff"             # nothing that looks like a TAB staff


def pages_of(path):
    data = open(path, "rb").read()
    return len(re.findall(rb"/Type\s*/Page[^s]", data)) or 1


def probe_route(path, max_pages=3):
    """Read the first few pages and report what the text layer yields."""
    staves = notes = measures = glyphs = 0
    for page in range(min(pages_of(path), max_pages)):
        try:
            gs, segs, box = extract(path, page)
        except Exception:
            continue
        glyphs += len(gs)
        found = find_staves(segs)
        partner = {id(t): n for t, n in pair_systems(found)}
        for st in [s for s in found if s.kind == "tab"]:
            st.barlines = find_barlines(st, segs, partner.get(id(st)))
            attach_notes(st, gs)
            staves += 1
            measures += st.measures
            notes += len(st.notes)
    if staves == 0:
        return EMPTY, staves, measures, notes, glyphs
    return (TEXT_ROUTE if notes else IMAGE_ROUTE), staves, measures, notes, glyphs
