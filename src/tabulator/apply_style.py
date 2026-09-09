"""Give a Guitar Pro score the house look.

    python src/tabulator/apply_style.py in.gp out.gp [--from reference.gp] [--format gp7|gp8]

Notation or tablature visibility, page layout and chord-diagram drawing live in
three binary entries next to score.gpif. Guitar Pro 8 only honours a stylesheet
it compiled itself: a GP7-era sheet dropped into a GP8 file loads without
complaint and then draws no chord diagrams in the score. So there is one entry
set per file format under resource/style/, each captured from a file the
matching Guitar Pro saved after loading style.gps. The target's own format
picks the set; --from takes the entries from any other .gp instead.
"""

import argparse
import io
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, ".")

from src.gp_ops.patcher import load_gpif, save_gpif

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ENTRIES = ("BinaryStylesheet", "LayoutConfiguration", "PartConfiguration")
RESOURCE = Path(__file__).resolve().parents[2] / "resource" / "style"


def detect_format(xml):
    version = re.search(r"<GPVersion>(.*?)</GPVersion>", xml)
    major = version.group(1).split(".")[0] if version else "8"
    return "gp7" if major == "7" else "gp8"


def entries_from_gp(path):
    z = zipfile.ZipFile(path)
    return {f"Content/{e}": z.read(f"Content/{e}") for e in ENTRIES if f"Content/{e}" in z.namelist()}


def entries_from_resource(fmt):
    folder = RESOURCE / fmt
    if not folder.is_dir():
        sys.exit(f"no style set for {fmt} under {RESOURCE}")
    return {f"Content/{e}": (folder / e).read_bytes() for e in ENTRIES if (folder / e).exists()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--from", dest="ref", help=".gp whose style entries to copy instead of the bundled set")
    ap.add_argument("--format", choices=("gp7", "gp8"), help="override the format detected from the target")
    args = ap.parse_args()

    xml = load_gpif(args.src)
    fmt = args.format or detect_format(xml)
    replace = entries_from_gp(args.ref) if args.ref else entries_from_resource(fmt)
    save_gpif(args.src, args.out, xml, replace)
    source = args.ref if args.ref else f"resource/style/{fmt}"
    print(f"{fmt}: copied {', '.join(k.split('/')[1] for k in replace)} from {source} -> {args.out}")


if __name__ == "__main__":
    main()
