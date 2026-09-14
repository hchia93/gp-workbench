# gp-workbench

**English** | [中文](README-cn.md)

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Platform: Cross-platform](https://img.shields.io/badge/Platform-Cross--platform-blue.svg)
![Status: Research](https://img.shields.io/badge/Status-Research-orange.svg)

[Guitar Pro](https://www.guitar-pro.com/) workbench. Parses notes and rhythm out of audio or a score PDF and writes a partial or complete `.gp` file.

<div align="center">

| Source | Input | Draft comes from | Recognition |
|---|---|---|---|
| <img src="https://img.shields.io/badge/A-Audio_Track-e36209" alt="A Audio Track" align="middle"> | A track URL | demucs guitar stem, basic-pitch transcription, fret mapping | Model based, draft is hand-edited afterwards |
| <img src="https://img.shields.io/badge/B-Engraved_PDF-d1242f" alt="B Engraved PDF" align="middle"> | Score PDF exported by notation software | Text layer and vector operators of the PDF itself | None, no OCR, no LLM |
| <img src="https://img.shields.io/badge/C-Image--Composed_PDF-bf8700" alt="C Image-Composed PDF" align="middle"> | Scanned or image-embedded PDF | — | Unexplored & unimplemented |
| <img src="https://img.shields.io/badge/D-Plain_Image-0969da" alt="D Plain Image" align="middle"> | Score screenshots, png / jpg | — | Unexplored & unimplemented |

</div>

## Purpose

Entering an existing PDF tablature into Guitar Pro by hand takes hours. Existing tools all hit at least one of: upload required, paywalled, standard notation only with no tablature, or OCR-based and therefore lossy.

<div align="center">

| Tool | Offline | Free | TAB | No OCR | Notes |
|---|---|---|---|---|---|
| Audiveris | ✓ | ✓ | ✗ | ✗ | Standard notation OMR, no tablature |
| oemer | ✓ | ✓ | ✗ | ✗ | Standard notation OMR, needs ML weights |
| SmartScore | ✓ | ✗ | Partial | ✗ | Commercial software, recognition driven |
| Online PDF to MusicXML services | ✗ | Limited | Partial | ✗ | Upload required |
| **gp-workbench** | **✓** | **✓** | **✓** | **✓** | Reads the PDF text layer and vector operators directly |

</div>

Inside a PDF exported by notation software the fret numbers, staff geometry and rhythm marks already exist exactly. Source B reads that data instead of recognizing images; the decoded `.gp` can be edited further in Guitar Pro and re-exported.

## Generation Route

### A. <img src="https://img.shields.io/badge/Audio_Track-Available-2ea44f" alt="Audio Track available" align="middle">

```bash
python src/tools/chord-finder/fetch_audio.py --url <url>
python src/tools/chord-finder/split_stem.py --in build/audio/raw.webm --seconds 40
python src/tools/chord-finder/transcribe_stem.py build/stems/htdemucs_6s/input/guitar.wav <template.gp> build/gp/draft.gp --start 5.5 --end 32
```

<div align="center">

| Step | Script | Output |
|---|---|---|
| Fetch | `fetch_audio.py` | Raw download under `build/audio/` plus a mono wav |
| Split | `split_stem.py` | demucs `htdemucs_6s` stems, `guitar.wav` and `vocals.wav` under `build/stems/` |
| Transcribe | `transcribe_stem.py` | basic-pitch dual-threshold transcription, sixteenth-grid fit, fret mapping, T-23 fingering, draft `.gp` |

</div>

### B. <img src="https://img.shields.io/badge/Engraved_PDF-Available-2ea44f" alt="Engraved PDF available" align="middle">

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
python src/tools/survey_route.py --library <path> --csv work/routes.tsv
python src/validator/benchmarker.py --library <path>
python src/validator/benchmarker.py --library <path> --detail "song name"
```

Either draft then goes through `src/tabulator/`. Open the draft in Guitar Pro, fix it by hand, save, then run the scripts below in order. Every script takes `in.gp out.gp`.

```bash
python src/tabulator/bars.py          add|modify|replace in.gp out.gp section.json [--from N]
python src/tabulator/header.py        setup in.gp out.gp --title ... --artist ... --tempo 72 --key D
python src/tabulator/style.py         apply in.gp out.gp [--from reference.gp] [--format gp7|gp8]
python src/tabulator/chord_pattern.py apply in.gp out.gp --from N --chords "xx0222:2 x20222:2" [--figure "e:F0+F1+T0 e:F2"]
python src/tabulator/chord_diagram.py deduce in.gp out.gp [--key D]
python src/tabulator/chord_diagram.py mark in.gp out.gp [--clear]
python src/tools/chord-finder/analyse_vocal_onset.py vocals.wav --bpm 72.1 --phase 0.045 --grid0 22 --json build/vox.json
python src/tabulator/lyrics.py        add in.gp out.gp lyrics.json [--raw]
```

<div align="center">

| Script | Writes |
|---|---|
| `bars.py` | Bars. `add` appends, `modify` rewrites from `--from` on and carries the `<Lyrics>` and `<Chord>` Guitar Pro hangs on each beat across position by position, stopping when a bar is too short to hold one; `replace` is the one allowed to lose it |
| `header.py` | `setup` writes the header: title, artist, album, tabber, tempo, key, capo, tuning. Only the fields given |
| `style.py` | `apply` writes the style triplet `BinaryStylesheet`, `LayoutConfiguration`, `PartConfiguration` from `resource/style/<gp7\|gp8>/`, format read from the target's `<GPVersion>`. `--from` copies the three from any `.gp` instead, `--format` forces one |
| `chord_pattern.py` | `sample` reads one bar as a slot figure, the spelling `src/sampling` uses. `apply` lays a figure over a run of chords, the figure coming from the `--sample` bar or a `--figure` string |
| `chord_diagram.py` | `deduce` reads the frets, grows `DiagramCollection` and the chart at the top of the page, places no mark. `mark` marks every bar and only from a diagram already on file, leaving a bar it cannot account for blank. `refresh` audits and carries a change to a diagram onto the marks pointing at it |
| `analyse_vocal_onset.py` | Syllable onsets from the vocal stem as `measure.beat`, the placement basis for lyrics, source A only |
| `lyrics.py` | `add` places lyrics the score does not have yet, spacing from where each line starts. `modify` moves words already placed, spacing untouched. `refresh` answers whether the words are still on the staff and respells the track block from the beats |

</div>

Templates: the repository ships no `.gp`. `--template` takes any `.gp` of your own. `style.py` needs none, the bundled sets under `resource/style/` cover gp7 and gp8.

## Figure pack

`src/sampling/` scans the scores already written and packs the ways they break a chord up. An entry is one chord plus one figure; a figure records which slot is plucked when with the frets thrown away, so it lays onto any chord.

```bash
python src/sampling/scan.py "D:/scores/**/*.gp"
```

| Call | Gives |
|---|---|
| `sampling.call("D7M")` | every form the library uses for D7M, widest first |
| `sampling.call("D7M@1")` | the one it uses most widely |
| `sampling.figures(songs=3)` | figures at least three scores share, chord dropped |
| `sampling.dialect()` | chord name and uses, in the library's own spelling |

`corpus.db` is gzipped JSON rebuilt by `scan.py` and never read directly. It carries no notes and no lyric text.

## Dependencies

<div align="center">

| Source | Install |
|---|---|
| B Engraved PDF | Python 3.10 or newer, standard library only |
| A Audio Track, fetch and analysis | `pip install --user numpy scipy yt-dlp imageio-ffmpeg` |
| A Audio Track, stem split | `pip install --user torch torchaudio --index-url https://download.pytorch.org/whl/cpu` then `pip install --user demucs` |
| A Audio Track, transcription | `pip install --user onnxruntime` then `pip install --user --no-deps basic-pitch` then `pip install --user pretty_midi mir_eval librosa resampy` |

</div>

Constraints: on Python 3.13 basic-pitch must be installed with `--no-deps` and its dependencies added separately, the plain install hits a dependency conflict. torch and demucs go in separate pip commands.

## Source layout

```
gp-workbench.py                        CLI entry
src/
├── cli.py                             subcommand dispatch
├── converter/
│   ├── converter.py                   write the decode result as .gp
│   └── pdf/
│       ├── probe_route.py             decide which decode route a PDF needs
│       ├── extract_content.py         read the characters and their positions on the page
│       ├── find_staff.py              recover staff structure and tablature notes
│       ├── group_outline.py           recover fret numbers where there is no text layer
│       ├── read_rhythm_notation.py    work out rhythm from the standard staff
│       └── read_rhythm_tab.py         work out rhythm from tablature when there is no standard staff
├── gp_ops/
│   ├── reader.py                      read the score content of a .gp
│   ├── writer.py                      create a new .gp
│   └── patcher.py                     edit an existing .gp in place
├── validator/
│   ├── verifier.py                    check a .gp is complete and usable
│   ├── benchmarker.py                 measure decode accuracy against ground-truth songs
│   └── test/                          test cases
├── tabulator/
│   ├── bars.py                        add, modify or replace bars
│   ├── header.py                      the song header
│   ├── style.py                       the layout style
│   ├── chord_pattern.py               picking figures
│   ├── chord_diagram.py               diagrams and the marks on them
│   └── lyrics.py                      lyrics on the beats
├── sampling/
│   ├── scan.py                        batch analysis over a .gp tree
│   └── corpus.db                      packed figures, chords, conventions
└── tools/
    ├── chord-finder/
    │   ├── analyse_vocal_onset.py     locate which beat each vocal syllable lands on
    │   ├── fetch_audio.py             download audio
    │   ├── split_stem.py              isolate the guitar stem
    │   └── transcribe_stem.py         turn the guitar stem into a draft .gp
    └── survey_route.py                classify a whole PDF library by decode route

resource/
└── style/
    ├── gp7/                           Guitar Pro 7 style set
    └── gp8/                           Guitar Pro 8 style set
doc/
└── *.md                               research records
```

Every script runs from the repository root as `python <path>`.

## License

[MIT](LICENSE). © 2026 Hyrex Chia.
