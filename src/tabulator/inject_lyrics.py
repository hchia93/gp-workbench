# -*- coding: utf-8 -*-
"""Write lyric lines into a Guitar Pro 8 score.

    python src/tabulator/inject_lyrics.py in.gp out.gp lyrics.json

lyrics.json is a list of [bar, text]. bar is 0-based and only positions the
line; inside a bar Guitar Pro hands one whitespace-separated token to each beat
that carries a note. Every CJK character becomes its own token, a space in the
text becomes an empty token that skips a beat. Use spaces to hold a syllable
over a beat or to start a line off the downbeat.
"""

import argparse
import io
import json
import re
import sys

sys.path.insert(0, ".")

from src.gp_ops.patcher import load_gpif, save_gpif

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def tokens(text):
    out = []
    for ch in text:
        if ch == " ":
            out.append("")
        elif ord(ch) > 0x2E7F:
            out.append(ch)
        elif out and out[-1] and ord(out[-1][-1]) <= 0x2E7F:
            out[-1] += ch
        else:
            out.append(ch)
    return " ".join(out)


def lyrics_xml(lines):
    body = "\n".join(f"<Line>\n<Text><![CDATA[{t}]]></Text>\n<Offset>{o}</Offset>\n</Line>"
                     for o, t in lines)
    return f'<Lyrics dispatched="true">\n{body}\n</Lyrics>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("lyrics")
    ap.add_argument("--raw", action="store_true", help="text is already one token per beat, space separated")
    args = ap.parse_args()

    with open(args.lyrics, encoding="utf-8") as f:
        raw = json.load(f)
    lines = [(int(bar), text if args.raw else tokens(text)) for bar, text in raw]

    xml = load_gpif(args.src)
    xml, n = re.subn(r"<Lyrics\b.*?</Lyrics>", lambda _: lyrics_xml(lines), xml, count=1, flags=re.S)
    if not n:
        sys.exit("no <Lyrics> block in track")
    save_gpif(args.src, args.out, xml)
    for bar, t in lines:
        print(f"  bar {bar + 1:>2}  {sum(1 for x in t.split(' ') if x)} syllables, {t.count('  ') + t.startswith(' ')} rests")
    print(f"{len(lines)} lines -> {args.out}")


if __name__ == "__main__":
    main()
