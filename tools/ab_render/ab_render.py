"""Render each disputed phrase as competing audio clips for ear judgement.

Run where the speakers are:
    python tools/ab_render/ab_render.py
    python tools/ab_render/ab_render.py --only g08

Each clip is the original phrase with one reading of the chords laid over it.
The wrong reading clashes, the right one locks in. Put the winning letter into
variants.json under "verdict".
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from chord import ab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", default="build/audio/song.wav")
    ap.add_argument("--variants", default="Generate/Attempt-02/variants.json")
    ap.add_argument("--out", default="build/ab")
    ap.add_argument("--only", help="render just this group id, e.g. g08")
    args = ap.parse_args()

    rate, song = ab.read_song(args.wav)
    with open(args.variants, encoding="utf-8") as f:
        data = json.load(f)
    os.makedirs(args.out, exist_ok=True)

    made = 0
    for g in data["groups"]:
        if args.only and g["id"] != args.only:
            continue
        lo, hi = g["bars"][0], g["bars"][1]
        before, after = g["context"]["before"], g["context"]["after"]
        print("%s  bars %.1f-%.1f  %s -> ? -> %s" % (g["id"], lo, hi, before, after))
        for v in g["variants"]:
            name = "%s_%s.wav" % (g["id"], v["letter"])
            ab.render_phrase(rate, song, g["t0"], g["t1"], g["spans"], v["chords"],
                             os.path.join(args.out, name))
            print("    %s  %-22s %s" % (v["letter"], " ".join(v["chords"]), v["label"]))
            made += 1
    print("\n%d clips in %s/" % (made, args.out))


if __name__ == "__main__":
    main()
