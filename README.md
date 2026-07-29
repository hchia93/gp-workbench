# score-pdf-to-gp

**English** | [中文](README-cn.md)

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Platform: Cross-platform](https://img.shields.io/badge/Platform-Cross--platform-blue.svg)
![Status: Research](https://img.shields.io/badge/Status-Research-orange.svg)

Converts guitar score PDFs into Guitar Pro `.gp` files. For PDFs exported by notation software, fret numbers, staff geometry, and rhythm marks can all be extracted exactly from the PDF's own text and vector operators, no OCR, no LLM.

## What it solves

Entering one song into Guitar Pro by hand takes two to three hours. Existing tools all hit at least one of: upload required, paywalled, standard notation only with no tablature, or OCR-based and therefore inherently lossy.

<div align="center">

| Tool | Offline | Free | TAB | No OCR | Notes |
|---|---|---|---|---|---|
| Audiveris | ✓ | ✓ | ✗ | ✗ | Standard notation OMR, no tablature |
| oemer | ✓ | ✓ | ✗ | ✗ | Standard notation OMR, needs ML weights |
| SmartScore | ✓ | ✗ | Partial | ✗ | Commercial software, recognition driven |
| Online PDF to MusicXML services | ✗ | Limited | Partial | ✗ | Upload required |
| **score-pdf-to-gp** | **✓** | **✓** | **✓** | **✓** | Decodes PDF operators directly, no recognition |

</div>

The key difference: mainstream tools all perform recognition, while inside a PDF exported by notation software this information already exists exactly, nobody just reads it.

## Who it's for

- **People sitting on a pile of guitar score PDFs.** A score on disk is dead, not searchable, not transposable, not refingerable. It becomes usable only after conversion to `.gp`
- **People who want the re-entry time back.** Even at seventy percent correct, you edit on top of a skeleton instead of typing for two to three hours from zero
- **People who need verifiable results.** Every measure's durations must sum to the time signature, and if it does not close, it is wrong. That self-check needs no manual comparison

## Usage

Run from the repository:

```bash
python score-pdf-to-gp.py route   <file.pdf>
python score-pdf-to-gp.py read    <file.pdf> [--page N] [--dump]
python score-pdf-to-gp.py rhythm  <file.pdf> [--page N]
python score-pdf-to-gp.py gp      <file.gp>  [--measures A-B]
python score-pdf-to-gp.py verify  <file.gp>...
```

Commands:

<div align="center">

| Command | Purpose |
|---|---|
| `python score-pdf-to-gp.py route <file.pdf>` | Report which decode route this PDF needs |
| `python score-pdf-to-gp.py read <file.pdf> [--page N] [--dump]` | Staves, barlines, TAB notes |
| `python score-pdf-to-gp.py rhythm <file.pdf> [--page N]` | Duration sequence per measure |
| `python score-pdf-to-gp.py gp <file.gp> [--measures A-B]` | Read a `.gp` back |
| `python score-pdf-to-gp.py verify <file.gp>...` | Check dangling references and measure duration closure |

</div>

Tool scripts:

```bash
python tools/survey.py --library <path> --csv work/routes.tsv
python tools/bench.py --library <path>
python tools/bench.py --library <path> --detail "song name"
```

## How it works

A `.gp` is a ZIP package, and its core data `Content/score.gpif` is plain XML. The writer uses a template approach, rewriting only this XML and copying every other entry verbatim, so the undocumented binary blocks stay valid.

The reader splits into three routes by what the PDF can give. The criterion is not the PDF's Producer field, it is whether fret numbers can be pulled from the text layer:

<div align="center">

| Route | Files | Share | Needs recognition |
|---|---|---|---|
| text-layer | 38 | 22.5% | No |
| image | 46 | 27.2% | No, shapes are limited and identical point by point, one annotation pass suffices |
| no-staff | 85 | 50.3% | Yes |

</div>

The decode chain for `text-layer`: the content stream interpreter tracks the CTM and the text matrix to get positioned glyphs, the ToUnicode CMap restores characters, path operators give staff lines and barlines, the baseline of a fret number sits at a fixed constant below its owning string line, and after calibration the string assignment is a single nearest-neighbor match.

Rhythm has two encodings depending on export settings: when standard notation is present, read stems and beam layers, and in TAB-only exports, read the flag glyphs and beams below the staff.

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
src/
├── pdf/        PDF content stream: positioned glyphs and vector segments
├── score/      staff geometry, TAB notes, rhythm from beams and flags
├── gp/         .gp read, write and verify
├── classify.py which route a PDF needs
└── cli.py      command line entry

tools/
├── survey.py   classify a whole library
└── bench.py    regression against songs that have both .gp and PDF

doc/
├── plan.html   the working plan, open in a browser
└── *.md        research records
```

Modules import each other relatively, and `score-pdf-to-gp.py` adds the repository root to `sys.path` before calling `src.cli`. No console script is provided on purpose, because top-level names like `src/pdf` and `src/score` would collide once installed into site-packages.

`tools/bench.py` is the most important one. It runs after every decoder change, because tuning against a single file overfits: one run hit 33% on a single file while the whole library sat at 19%.

## Development

Requires Python 3.10 or newer, no third-party dependencies, no install step.

```bash
git clone <repo>
cd score-pdf-to-gp
python tools/bench.py --library <your score library>
```

`work/` is a gitignored output directory, the classification table and benchmark reports are written there.

Planning document: `doc/plan.html`, open it in a browser. Research records are the markdown files under `doc/`.

## Roadmap

<div align="center">

| Version | Contents |
|---|---|
| v0.1 | Text-layer route, note and duration decoding, regression benchmark **(current)** |
| v0.2 | Fix measure splitting and short hooks in beam groups, accuracy target 70% |
| v0.3 | Vector outline route, coverage target 50% |
| TBD | Pure bitmap route |

</div>

## License

[MIT](LICENSE). © 2026 Hyrex Chia.
