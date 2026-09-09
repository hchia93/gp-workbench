# -*- coding: utf-8 -*-
"""Fill in the header of a Guitar Pro 8 score: song, artist, key, tempo, tuning.

    python src/tabulator/init_tabulate.py in.gp out.gp --title T --artist A
        [--album X] [--tabber X] [--tempo 72] [--key D|Bm] [--capo 0]
        [--tuning "E2 A2 D3 G3 B3 E4"]

Only the options given are written; everything else in the file is untouched.
"""

import argparse
import io
import re
import sys

sys.path.insert(0, ".")

from src.gp_ops.patcher import load_gpif, save_gpif, set_cdata

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# accidental count on the circle of fifths, sharps positive
MAJOR = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
         "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7}
MINOR = {"A": 0, "E": 1, "B": 2, "F#": 3, "C#": 4, "G#": 5, "D#": 6, "A#": 7,
         "D": -1, "G": -2, "C": -3, "F": -4, "Bb": -5, "Eb": -6, "Ab": -7}
PITCH = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6,
         "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def key_xml(name):
    mode = "Minor" if name.endswith("m") else "Major"
    root = name[:-1] if mode == "Minor" else name
    table = MINOR if mode == "Minor" else MAJOR
    if root not in table:
        sys.exit(f"unknown key {name}")
    count = table[root]
    return (f"<Key>\n<AccidentalCount>{count}</AccidentalCount>\n<Mode>{mode}</Mode>\n"
            f"<TransposeAs>{'Flats' if count < 0 else 'Sharps'}</TransposeAs>\n</Key>")


def midi_of(token):
    m = re.fullmatch(r"([A-G][#b]?)(\d)", token)
    if m:
        return 12 * (int(m.group(2)) + 1) + PITCH[m.group(1)]
    return int(token)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--title")
    ap.add_argument("--artist")
    ap.add_argument("--album")
    ap.add_argument("--tabber")
    ap.add_argument("--tempo", type=int)
    ap.add_argument("--key", help="D, Bm, F#, Ebm ...")
    ap.add_argument("--capo", type=int)
    ap.add_argument("--tuning", help="six notes low to high, names like E2 or MIDI numbers")
    args = ap.parse_args()

    xml = load_gpif(args.src)
    done = []
    for tag, value in (("Title", args.title), ("Artist", args.artist),
                       ("Album", args.album), ("Tabber", args.tabber)):
        if value is not None:
            xml = set_cdata(xml, tag, value)
            done.append(tag.lower())
    if args.tempo is not None:
        xml = re.sub(r"(<Type>Tempo</Type>.*?<Value>)[\d.]+( \d+</Value>)",
                     lambda m: f"{m.group(1)}{args.tempo}{m.group(2)}", xml, count=1, flags=re.S)
        done.append("tempo")
    if args.key is not None:
        xml = re.sub(r"<Key>.*?</Key>", key_xml(args.key), xml, flags=re.S)
        done.append("key")
    if args.capo is not None:
        xml = re.sub(r'(<Property name="CapoFret">\s*<Fret>)\d+(</Fret>)',
                     rf"\g<1>{args.capo}\g<2>", xml, count=1)
        done.append("capo")
    if args.tuning is not None:
        pitches = " ".join(str(midi_of(t)) for t in args.tuning.split())
        xml = re.sub(r"(<Pitches>)[\d ]+(</Pitches>)", rf"\g<1>{pitches}\g<2>", xml, count=1)
        done.append("tuning")

    save_gpif(args.src, args.out, xml)
    print(f"set {', '.join(done) or 'nothing'} -> {args.out}")


if __name__ == "__main__":
    main()
