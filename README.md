# gp-workbench

**English** | [中文](README-cn.md)

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Platform: Cross-platform](https://img.shields.io/badge/Platform-Cross--platform-blue.svg)
![Status: Research](https://img.shields.io/badge/Status-Research-orange.svg)

Guitar Pro 8 workbench. Two sources, **A audio** and **B image/PDF**, each produce a draft `.gp`. The draft is finished in `src/tabulator/` (`init_tabulate → apply_style → inject_chord_diagram → inject_lyrics`), which reads and writes through `src/gp_ops/` (reader / writer / patcher).

<div align="center">

| Source | Input | Draft comes from | Recognition |
|---|---|---|---|
| A · Audio | A track URL | demucs guitar stem, basic-pitch transcription, fret mapping | Model based, draft is hand-edited afterwards |
| B · Image/PDF | Score PDF exported by notation software | Text layer and vector operators of the PDF itself | None, no OCR, no LLM |

</div>

## Why

Entering one song into Guitar Pro by hand takes two to three hours. Existing tools all hit at least one of: upload required, paywalled, standard notation only with no tablature, or OCR-based and therefore lossy.

<div align="center">

| Tool | Offline | Free | TAB | No OCR | Notes |
|---|---|---|---|---|---|
| Audiveris | ✓ | ✓ | ✗ | ✗ | Standard notation OMR, no tablature |
| oemer | ✓ | ✓ | ✗ | ✗ | Standard notation OMR, needs ML weights |
| SmartScore | ✓ | ✗ | Partial | ✗ | Commercial software, recognition driven |
| Online PDF to MusicXML services | ✗ | Limited | Partial | ✗ | Upload required |
| **gp-workbench** | **✓** | **✓** | **✓** | **✓** | Decodes PDF operators directly |

</div>

Inside a PDF exported by notation software the fret numbers, staff geometry and rhythm marks already exist exactly. Source B reads them instead of recognizing them.

## Generation Route

### A. Audio → .gp

```bash
python src/tools/chord-finder/fetch_audio.py --url <url>
python src/tools/chord-finder/stem_split.py --in build/audio/raw.webm --seconds 40
python src/tools/chord-finder/transcribe_stem.py build/stems/htdemucs_6s/input/guitar.wav <template.gp> build/gp/draft.gp --start 5.5 --end 32
```

<div align="center">

| Step | Script | Output |
|---|---|---|
| Fetch | `fetch_audio.py` | Raw download under `build/audio/` plus a mono wav |
| Split | `stem_split.py` | demucs `htdemucs_6s` stems, `guitar.wav` and `vocals.wav` under `build/stems/` |
| Transcribe | `transcribe_stem.py` | basic-pitch dual-threshold transcription, sixteenth-grid fit, fret mapping, T-23 fingering, draft `.gp` |

</div>

### B. Image/PDF → .gp

Run from the repository root:

```bash
python gp-workbench.py route   <file.pdf>
python gp-workbench.py read    <file.pdf> [--page N] [--dump]
python gp-workbench.py rhythm  <file.pdf> [--page N]
python gp-workbench.py convert <file.pdf> --template <any.gp> -o out.gp [--title T] [--artist A] [--tempo N] [--capo N]
python gp-workbench.py gp      <file.gp>  [--measures A-B]
python gp-workbench.py verify  <file.gp>...
```

<div align="center">

| Command | Purpose |
|---|---|
| `route` | Report which decode route this PDF needs |
| `read` | Staves, barlines, TAB notes |
| `rhythm` | Duration sequence per measure |
| `convert` | Decode a PDF and write a `.gp`, non-XML zip entries copied from `--template` |
| `gp` | Read a `.gp` back as measures |
| `verify` | Check dangling references and measure duration closure |

</div>

Library tools:

```bash
python src/tools/survey/surveyor.py --library <path> --csv work/routes.tsv
python src/validator/benchmarker.py --library <path>
python src/validator/benchmarker.py --library <path> --detail "song name"
```

Either draft then goes through `src/tabulator/`. Open the draft in Guitar Pro, fix it by hand, save, then run the scripts in order. Every script takes `in.gp out.gp`, edits `Content/score.gpif` as text through `src/gp_ops/patcher.py` and copies every other zip entry verbatim.

```bash
python src/tabulator/init_tabulate.py in.gp out.gp --title ... --artist ... --tempo 72 --key D
python src/tabulator/apply_style.py in.gp out.gp [--from reference.gp] [--format gp7|gp8]
python src/tabulator/inject_chord_diagram.py in.gp out.gp [--chart]
python src/tools/chord-finder/vocal_syllables.py vocals.wav --bpm 72.1 --phase 0.045 --grid0 22 --json build/vox.json
python src/tabulator/inject_lyrics.py in.gp out.gp lyrics.json [--raw]
```

<div align="center">

| Script | Writes |
|---|---|
| `init_tabulate.py` | Header: title, artist, album, tabber, tempo, key, capo, tuning |
| `apply_style.py` | Style triplet `BinaryStylesheet`, `LayoutConfiguration`, `PartConfiguration` from `resource/style/<gp7\|gp8>/`, format read from the target's `<GPVersion>`. `--from` copies the three entries from any `.gp` instead, `--format` forces one |
| `inject_chord_diagram.py` | Chords inferred per measure from the notes, `DiagramCollection` entries, `<Chord>` marks where the chord changes, `--chart` fills the chord palette at the top of the page |
| `vocal_syllables.py` | Syllable onsets from the vocal stem as `measure.beat`, the placement basis for lyrics, source A only |
| `inject_lyrics.py` | Lyric line, one token per CJK character, a space skips one beat |

</div>

Templates: the repository ships no `.gp`. `--template` takes any `.gp` of your own. `apply_style.py` needs none, the bundled sets under `resource/style/` cover gp7 and gp8.

## Dependencies

<div align="center">

| Source | Install |
|---|---|
| B Image/PDF | Python 3.10 or newer, standard library only |
| A Audio, fetch and analysis | `pip install --user numpy scipy yt-dlp imageio-ffmpeg` |
| A Audio, stem split | `pip install --user torch torchaudio --index-url https://download.pytorch.org/whl/cpu` then `pip install --user demucs` |
| A Audio, transcription | `pip install --user onnxruntime` then `pip install --user --no-deps basic-pitch` then `pip install --user pretty_midi mir_eval librosa resampy` |

</div>

Constraints: on Python 3.13 basic-pitch must be installed with `--no-deps` and its dependencies added separately, the plain install hits a dependency conflict. torch and demucs go in separate pip commands.

## Accuracy

Measured over a 169-PDF library:

<div align="center">

| Metric | Value |
|---|---|
| Files with readable notes | 38 |
| Measures | 1730 |
| Notes | 19225 |
| TAB staff and standard notation measure counts agree | 198 / 198 |

</div>

Accuracy is measured on songs that have a `.gp` ground truth, where the `.gp` and its exported PDF form a pair. 12 songs, 669 measures:

<div align="center">

| Metric | Correct | Rate |
|---|---|---|
| Note set matches | 368 | 55.0% |
| Duration sequence matches | 265 | 39.6% |
| Both match | 253 | 37.8% |

</div>

Best single-song results: `南山南` notes 58 / 63, `雪落下的声音` notes 49 / 54. The text-layer route has no structural obstacle, everything left is engineering.

## Source layout

```
gp-workbench.py                        CLI entry: route / read / rhythm / gp / convert / verify
src/
├── cli.py
├── converter/
│   ├── converter.py                   PDF decode result -> .gp
│   └── pdf/
│       ├── router.py                  which decode route a PDF needs
│       ├── extractor.py               positioned glyphs from the text layer
│       ├── staff.py                   staff geometry and TAB content
│       ├── outline.py                 vector strokes inside a TAB staff clustered into glyphs
│       ├── rhythm_notation.py         durations from stems and beams of the standard staff
│       └── rhythm_tab.py              durations from the TAB staff when no standard staff exists
├── gp_ops/
│   ├── reader.py                      .gp -> per-measure structure
│   ├── writer.py                      template writer, rebuilds only the id tables of score.gpif
│   └── patcher.py                     in-place edit, gpif as text, other zip entries copied
├── validator/
│   ├── verifier.py                    dangling references, measure durations
│   ├── benchmarker.py                 regression against songs that have both .gp and exported PDF
│   └── test/                          test cases
├── tabulator/
│   ├── init_tabulate.py               header fields
│   ├── apply_style.py                 style triplet from resource/style/ or a reference .gp
│   ├── inject_chord_diagram.py        chord diagrams and <Chord> marks
│   └── inject_lyrics.py               lyric tokens
└── tools/
    ├── chord-finder/
    │   ├── fetch_audio.py             yt-dlp -> mono wav
    │   ├── stem_split.py              demucs htdemucs_6s, guitar stem
    │   ├── transcribe_stem.py         basic-pitch -> grid -> frets -> draft .gp
    │   └── vocal_syllables.py         syllable onsets -> measure.beat
    └── survey/
        └── surveyor.py                classify a whole PDF library by decode route

resource/
└── style/
    ├── gp7/                           BinaryStylesheet, LayoutConfiguration, PartConfiguration saved by Guitar Pro 7
    └── gp8/                           same three, saved by Guitar Pro 8 after loading a .gps
doc/
├── plan.html                          working plan, open in a browser
└── *.md                               research records
Generate/Attempt-02/记录.md            audio route log
```

Namespace packages, no `__init__.py`. Every script runs from the repository root as `python <path>`; `gp-workbench.py` adds the root to `sys.path` before calling `src.cli`.

`src/validator/benchmarker.py` runs after every decoder change, because tuning against a single file overfits: one run hit 33% on a single file while the whole library sat at 19%.

## Development

```bash
git clone <repo>
cd gp-workbench
python src/validator/benchmarker.py --library <your score library>
```

Output directories, both gitignored:

- `work/`: survey tables, benchmark reports
- `build/`: audio, stems, draft `.gp`

New style set: in Guitar Pro 8 load a `.gps`, save the score, then extract `BinaryStylesheet`, `LayoutConfiguration`, `PartConfiguration` from that `.gp` into `resource/style/gp8/`. Guitar Pro 8 only honors stylesheets it compiled itself: a GP7-era `BinaryStylesheet` pasted into a GP8 file opens but draws no chord diagrams, and `.gps` is text `key=value`, not pasteable.

Planning document: `doc/plan.html`. Research records: `doc/*.md`, audio route log in `Generate/Attempt-02/记录.md`.

## License

[MIT](LICENSE). © 2026 Hyrex Chia.
