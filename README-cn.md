# gp-workbench

[English](README.md) | **中文**

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Platform: Cross-platform](https://img.shields.io/badge/Platform-Cross--platform-blue.svg)
![Status: Research](https://img.shields.io/badge/Status-Research-orange.svg)

[Guitar Pro](https://www.guitar-pro.com/) 工作台。从音频或 PDF 谱面解析出音符与节奏，生成部分或完整的 `.gp` 文件。

<div align="center">

| 源头 | 输入 | 草稿来源 | 识别 |
|---|---|---|---|
| <img src="https://img.shields.io/badge/A-源音轨-e36209" alt="A 源音轨" align="middle"> | 一个音轨链接 | demucs 吉他分轨，basic-pitch 转录，品位映射 | 模型驱动，草稿之后手改 |
| <img src="https://img.shields.io/badge/B-成谱PDF-d1242f" alt="B 成谱PDF" align="middle"> | 制谱软件导出的吉他谱 PDF | PDF 自身的文本层与矢量算子 | 无，不用 OCR，不用 LLM |
| <img src="https://img.shields.io/badge/C-图片合成谱PDF-bf8700" alt="C 图片合成谱PDF" align="middle"> | 扫描或图片嵌入的 PDF | — | 未探索 & 实装 |
| <img src="https://img.shields.io/badge/D-纯图片-0969da" alt="D 纯图片" align="middle"> | 谱面截图 png / jpg | — | 未探索 & 实装 |

</div>

## 目的

把一份现成的 PDF 六线谱手工敲进 Guitar Pro 需要数小时。现有工具都至少踩中一条：需要上传、要付费、只做五线谱不做六线谱、或者依赖 OCR 因而带误差。

<div align="center">

| 工具 | 离线 | 免费 | 六线谱 | 无需 OCR | 说明 |
|---|---|---|---|---|---|
| Audiveris | ✓ | ✓ | ✗ | ✗ | 五线谱 OMR，不处理六线谱 |
| oemer | ✓ | ✓ | ✗ | ✗ | 五线谱 OMR，需要 ML 权重 |
| SmartScore | ✓ | ✗ | 部分 | ✗ | 商业软件，识别为主 |
| PDF to MusicXML 类在线服务 | ✗ | 有限 | 部分 | ✗ | 需要上传 |
| **gp-workbench** | **✓** | **✓** | **✓** | **✓** | 直接读 PDF 的文本层与矢量算子 |

</div>

制谱软件导出的 PDF 里，品位数字、谱表几何、节奏记号本来就精确存在。源头 B 直接读取这些数据，不做图像识别；解码出的 `.gp` 可以在 Guitar Pro 里继续编辑后重新导出。

## 生成路径

### A. <img src="https://img.shields.io/badge/源音轨-可用-2ea44f" alt="源音轨 可用" align="middle">

```bash
python src/tools/chord-finder/fetch_audio.py --url <url>
python src/tools/chord-finder/split_stem.py --in build/audio/raw.webm --seconds 40
python src/tools/chord-finder/transcribe_stem.py build/stems/htdemucs_6s/input/guitar.wav <template.gp> build/gp/draft.gp --start 5.5 --end 32
```

<div align="center">

| 步骤 | 脚本 | 产出 |
|---|---|---|
| 抓取 | `fetch_audio.py` | 原始下载落在 `build/audio/`，另出单声道 wav |
| 分轨 | `split_stem.py` | demucs `htdemucs_6s` 六轨，`guitar.wav` 与 `vocals.wav` 落在 `build/stems/` |
| 转录 | `transcribe_stem.py` | basic-pitch 双阈值转录，十六分网格拟合，品位映射，T-23 手型，草稿 `.gp` |

</div>

### B. <img src="https://img.shields.io/badge/成谱PDF-可用-2ea44f" alt="成谱PDF 可用" align="middle">

从仓库根运行：

```bash
python gp-workbench.py route   <file.pdf>
python gp-workbench.py read    <file.pdf> [--page N] [--dump]
python gp-workbench.py rhythm  <file.pdf> [--page N]
python gp-workbench.py convert <file.pdf> --template <any.gp> -o out.gp [--title T] [--artist A] [--tempo N] [--capo N]
python gp-workbench.py gp      <file.gp>  [--measures A-B]
python gp-workbench.py verify  <file.gp>...
```

<div align="center">

| 命令 | 作用 |
|---|---|
| `route` | 报告这个 PDF 需要哪条解码路线 |
| `read` | 谱表、小节线、TAB 音符 |
| `rhythm` | 每小节的时值序列 |
| `convert` | 解码 PDF 并写出 `.gp`，非 XML 的 zip 条目从 `--template` 复制 |
| `gp` | 反读一个 `.gp` 成逐小节结构 |
| `verify` | 检查悬空引用与小节时值闭合 |

</div>

曲库工具：

```bash
python src/tools/survey_route.py --library <path> --csv work/routes.tsv
python src/validator/benchmarker.py --library <path>
python src/validator/benchmarker.py --library <path> --detail "song name"
```

两条路径的草稿都进 `src/tabulator/` 收尾。在 Guitar Pro 里打开草稿手改并保存，再按顺序跑下面的脚本，每个脚本都是 `in.gp out.gp`。

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

| 脚本 | 写入 |
|---|---|
| `bars.py` | 小节。`add` 追加到末尾，`modify` 从 `--from` 起改写并逐位承接 Guitar Pro 挂在 beat 上的 `<Lyrics>` 与 `<Chord>`，装不下就报错退出，`replace` 是唯一允许丢的那个 |
| `header.py` | `setup` 写头信息：歌名、歌手、专辑、tabber、速度、调性、capo、调弦。只写给出的项 |
| `style.py` | `apply` 样式三件 `BinaryStylesheet`、`LayoutConfiguration`、`PartConfiguration`，取自 `resource/style/<gp7\|gp8>/`，格式按目标文件 `<GPVersion>` 自动判。`--from` 改为从任意 `.gp` 抄这三项，`--format` 强制指定 |
| `chord_pattern.py` | `sample` 把一小节读成槽位型，与 `src/sampling` 同一种写法。`apply` 把型铺到一串和弦上，型来自 `--sample` 指定的小节或 `--figure` 字符串 |
| `chord_diagram.py` | `deduce` 从指板推和弦，扩充 `DiagramCollection` 与顶部和弦表，不打标记。`mark` 只用已有和弦图打标记，每小节都打，接不上的小节留空。`refresh` 审计并把和弦图的改动级联到指向它的标记 |
| `analyse_vocal_onset.py` | 人声轨音节起点转成 `小节.拍位`，歌词落位依据，仅源头 A |
| `lyrics.py` | `add` 新歌词按每行起始小节定 spacing。`modify` 移动已落位的词，spacing 不动。`refresh` 检查词是否还在谱面上，并从 beat 反排 track 块 |

</div>

模板：仓库不附带 `.gp`。`--template` 接你自己的任意 `.gp`。`style.py` 不需要，`resource/style/` 自带的样式集覆盖 gp7 与 gp8。

## 词条库

`src/sampling/` 扫已有的 `.gp`，把常用和弦的分解形式打包成词条。一条词条是一个和弦加一种分解形式，形式只记哪个槽位在哪一拍被拨，品位扔掉，所以能铺到任何和弦上。

```bash
python src/sampling/scan.py "D:/scores/**/*.gp"
```

| 调用 | 取到 |
|---|---|
| `sampling.call("D7M")` | D7M 的全部分解形式，按跨谱数排 |
| `sampling.call("D7M@1")` | 最通用的那条 |
| `sampling.figures(songs=3)` | 至少三份谱共用的型，不分和弦 |
| `sampling.dialect()` | 和弦名与用量，用的是库里的拼法 |

`corpus.db` 是 gzip 的 JSON，由 `scan.py` 重建，不直接读。不存音符也不存歌词文本。

## 依赖

<div align="center">

| 源头 | 安装 |
|---|---|
| B 成谱PDF | Python 3.10 以上，只用标准库 |
| A 源音轨，抓取与分析 | `pip install --user numpy scipy yt-dlp imageio-ffmpeg` |
| A 源音轨，分轨 | `pip install --user torch torchaudio --index-url https://download.pytorch.org/whl/cpu` 然后 `pip install --user demucs` |
| A 源音轨，转录 | `pip install --user onnxruntime` 然后 `pip install --user --no-deps basic-pitch` 然后 `pip install --user pretty_midi mir_eval librosa resampy` |

</div>

约束：Python 3.13 下 basic-pitch 必须 `--no-deps` 装，依赖另行补齐，直接装会依赖冲突。torch 与 demucs 分两条 pip 命令。

## 源码布局

```
gp-workbench.py                        命令行入口
src/
├── cli.py                             子命令分发
├── converter/
│   ├── converter.py                   把解码结果写成 .gp
│   └── pdf/
│       ├── probe_route.py             判定 PDF 该走哪条解码路径
│       ├── extract_content.py         读出谱面上的字符与位置
│       ├── find_staff.py              还原谱表结构与六线谱音符
│       ├── group_outline.py           还原没有文本层的品位数字
│       ├── read_rhythm_notation.py    从五线谱推算节奏
│       └── read_rhythm_tab.py         没有五线谱时从六线谱推算节奏
├── gp_ops/
│   ├── reader.py                      读取 .gp 的谱面内容
│   ├── writer.py                      新建 .gp
│   └── patcher.py                     就地修改已有 .gp
├── validator/
│   ├── verifier.py                    检查 .gp 是否完整可用
│   ├── benchmarker.py                 用有真值的曲目测解码准确率
│   └── test/                          测试用例
├── tabulator/
│   ├── bars.py                        增改替小节
│   ├── header.py                      曲目头信息
│   ├── style.py                       排版样式
│   ├── chord_pattern.py               拨弦型
│   ├── chord_diagram.py               和弦图与标记
│   └── lyrics.py                      beat 上的歌词
├── sampling/
│   ├── scan.py                        批量分析 .gp 树
│   └── corpus.db                      打包的型、和弦与惯例
└── tools/
    ├── chord-finder/
    │   ├── analyse_vocal_onset.py     定位人声音节落在第几拍
    │   ├── fetch_audio.py             下载音频
    │   ├── split_stem.py              分离吉他音轨
    │   └── transcribe_stem.py         把吉他音轨转成草稿 .gp
    └── survey_route.py                按解码路径给整个 PDF 曲库分类

resource/
└── style/
    ├── gp7/                           Guitar Pro 7 样式集
    └── gp8/                           Guitar Pro 8 样式集
doc/
└── *.md                               研究记录
```

所有脚本从仓库根以 `python <路径>` 运行。

## 许可

[MIT](LICENSE). © 2026 Hyrex Chia.
