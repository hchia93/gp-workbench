"""Fetch a track and normalise it to the mono wav the analysis layer expects.

    python src/tools/chord-finder/fetch_audio.py --url <video url>

Needs yt-dlp and a decoder, both installable without admin rights:
    pip install --user yt-dlp imageio-ffmpeg
"""

import argparse
import glob
import os
import subprocess
import sys


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", default="build/audio/song.wav")
    ap.add_argument("--rate", type=int, default=11025)
    args = ap.parse_args()

    work = os.path.dirname(args.out) or "."
    os.makedirs(work, exist_ok=True)
    for stale in glob.glob(os.path.join(work, "raw.*")):
        os.remove(stale)

    subprocess.run([sys.executable, "-m", "yt_dlp", "--no-playlist", "-f", "bestaudio",
                    "-o", os.path.join(work, "raw.%(ext)s"), args.url], check=True)

    found = glob.glob(os.path.join(work, "raw.*"))
    if not found:
        sys.exit("download produced no file")

    subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", found[0],
                    "-ac", "1", "-ar", str(args.rate), "-y", args.out], check=True)
    print(f"wrote {args.out}  mono {args.rate} Hz")


if __name__ == "__main__":
    main()
