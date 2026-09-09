"""Split a track into stems and keep the guitar one.

    python src/tools/chord-finder/split_stem.py --in build/audio/raw.webm --start 58 --seconds 66

Needs demucs on a CPU-only torch, both installable without admin rights:
    pip install --user torch torchaudio --index-url https://download.pytorch.org/whl/cpu
    pip install --user demucs

htdemucs_6s is the only pretrained model that emits a guitar stem. The plain
htdemucs folds guitar into "other" and spleeter has no guitar stem at all.
Demucs was trained on 44.1 kHz stereo, so the 11 kHz mono the analysis layer
eats is not a valid input here. Decode fresh from the original download.
"""

import argparse
import os
import subprocess
import sys

MODEL = "htdemucs_6s"


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default="build/audio/raw.webm")
    ap.add_argument("--out", default="build/stems")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--seconds", type=float, default=0.0, help="0 for the whole track")
    ap.add_argument("--name", default="input")
    ap.add_argument("--stem", default="guitar")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    slice_wav = os.path.join(args.out, args.name + ".wav")

    seek = ["-ss", str(args.start)] if args.start > 0 else []
    cut = ["-t", str(args.seconds)] if args.seconds > 0 else []
    subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", *seek, "-i", args.src,
                    *cut, "-ac", "2", "-ar", "44100", "-y", slice_wav], check=True)

    subprocess.run([sys.executable, "-m", "demucs", "-n", MODEL, "-d", "cpu",
                    "--jobs", "1", "-o", args.out, slice_wav], check=True)

    stem = os.path.join(args.out, MODEL, args.name, args.stem + ".wav")
    if not os.path.exists(stem):
        sys.exit(f"no {args.stem} stem at {stem}")
    print(f"wrote {stem}")


if __name__ == "__main__":
    main()
