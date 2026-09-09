"""Edit a Guitar Pro 8 .gp in place: score.gpif as text, everything else copied.

The template writer in write.py rebuilds a score from scratch and knows only the
elements it emits. Once a score has been touched in Guitar Pro (ties, grace
notes, arpeggios, ...) that path throws work away, so late-stage tools patch the
XML the program wrote instead.
"""

import re
import zipfile

GPIF = "Content/score.gpif"


def load_gpif(path):
    return zipfile.ZipFile(path).read(GPIF).decode("utf-8")


def save_gpif(src, out, xml, replace=None):
    """Write out with the patched gpif; replace maps entry name -> bytes."""
    replace = replace or {}
    zin = zipfile.ZipFile(src)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.namelist():
            if item == GPIF:
                data = xml.encode("utf-8")
            elif item in replace:
                data = replace[item]
            else:
                data = zin.read(item)
            zout.writestr(item, data)


def set_cdata(xml, tag, value):
    return re.sub(r"<%s><!\[CDATA\[.*?\]\]></%s>" % (tag, tag),
                  f"<{tag}><![CDATA[{value}]]></{tag}>", xml, count=1, flags=re.S)
