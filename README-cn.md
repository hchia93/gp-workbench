# gp-workbench

[English](README.md) | **中文**

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Platform: Cross-platform](https://img.shields.io/badge/Platform-Cross--platform-blue.svg)
![Status: Research](https://img.shields.io/badge/Status-Research-orange.svg)

Guitar Pro 8 工作台。两个源头 **A 音频** 与 **B 图像·PDF** 各自出草稿 `.gp`，草稿进 `src/tabulator/` 收尾（`init_tabulate → apply_style → inject_chord_diagram → inject_lyrics`），tabulator 底下靠 `src/gp_ops/`（reader / writer / patcher）读写。

<div align="center">

| 源头 | 输入 | 草稿来源 | 识别 |
|---|---|---|---|
| A · 音频 | 一个音轨链接 | demucs 吉他分轨，basic-pitch 转录，品位映射 | 模型驱动，草稿之后手改 |
| B · 图像·PDF | 制谱软件导出的吉他谱 PDF | PDF 自身的文本层与矢量算子 | 无，不用 OCR，不用 LLM |

</div>

## 为什么

手工把一首谱敲进 Guitar Pro 要两三个小时。现有工具都至少踩中一条：需要上传、要付费、只做五线谱不做六线谱、或者依赖 OCR 因而带误差。

<div align="center">

| 工具 | 离线 | 免费 | 六线谱 | 无需 OCR | 说明 |
|---|---|---|---|---|---|
| Audiveris | ✓ | ✓ | ✗ | ✗ | 五线谱 OMR，不处理六线谱 |
| oemer | ✓ | ✓ | ✗ | ✗ | 五线谱 OMR，需要 ML 权重 |
| SmartScore | ✓ | ✗ | 部分 | ✗ | 商业软件，识别为主 |
| PDF to MusicXML 类在线服务 | ✗ | 有限 | 部分 | ✗ | 需要上传 |
| **gp-workbench** | **✓** | **✓** | **✓** | **✓** | 从 PDF 算子直接解码 |

</div>

制谱软件导出的 PDF 里，品位数字、谱表几何、节奏记号本来就精确存在。源头 B 直接读，不识别。

## Generation Route

### A. 音频 → .gp

```bash
python src/tools/chord-finder/fetch_audio.py --url <url>
python src/tools/chord-finder/stem_split.py --in build/audio/raw.webm --seconds 40
python src/tools/chord-finder/transcribe_stem.py build/stems/htdemucs_6s/input/guitar.wav <template.gp> build/gp/draft.gp --start 5.5 --end 32
```

<div align="center">

| 步骤 | 脚本 | 产出 |
|---|---|---|
| 抓取 | `fetch_audio.py` | 原始下载落在 `build/audio/`，另出单声道 wav |
| 分轨 | `stem_split.py` | demucs `htdemucs_6s` 六轨，`guitar.wav` 与 `vocals.wav` 落在 `build/stems/` |
| 转录 | `transcribe_stem.py` | basic-pitch 双阈值转录，十六分网格拟合，品位映射，T-23 手型，草稿 `.gp` |

</div>

### B. 图像·PDF → .gp

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
python src/tools/survey/surveyor.py --library <path> --csv work/routes.tsv
python src/validator/benchmarker.py --library <path>
python src/validator/benchmarker.py --library <path> --detail "song name"
```

两边的草稿之后都进 `src/tabulator/`。在 Guitar Pro 里打开草稿手改，保存，再按顺序跑脚本。每个脚本都是 `in.gp out.gp`，经 `src/gp_ops/patcher.py` 把 `Content/score.gpif` 当文本改，其余 zip 条目原样复制。

```bash
python src/tabulator/init_tabulate.py in.gp out.gp --title ... --artist ... --tempo 72 --key D
python src/tabulator/apply_style.py in.gp out.gp [--from reference.gp] [--format gp7|gp8]
python src/tabulator/inject_chord_diagram.py in.gp out.gp [--chart]
python src/tools/chord-finder/vocal_syllables.py vocals.wav --bpm 72.1 --phase 0.045 --grid0 22 --json build/vox.json
python src/tabulator/inject_lyrics.py in.gp out.gp lyrics.json [--raw]
```

<div align="center">

| 脚本 | 写入 |
|---|---|
| `init_tabulate.py` | 头信息：歌名、歌手、专辑、tabber、速度、调性、capo、调弦 |
| `apply_style.py` | 样式三件 `BinaryStylesheet`、`LayoutConfiguration`、`PartConfiguration`，取自 `resource/style/<gp7\|gp8>/`，格式按目标文件 `<GPVersion>` 自动判。`--from` 改为从任意 `.gp` 抄这三项，`--format` 强制指定 |
| `inject_chord_diagram.py` | 从谱面按小节推和弦，写 `DiagramCollection`，换和弦处打 `<Chord>` 标记，`--chart` 同时填页面顶部的和弦表 |
| `vocal_syllables.py` | 人声轨音节起点转成 `小节.拍位`，歌词落位依据，仅源头 A |
| `inject_lyrics.py` | 歌词行，每个 CJK 字一个 token，空格占一拍 |

</div>

模板：仓库不附带 `.gp`。`--template` 接你自己的任意 `.gp`。`apply_style.py` 不需要，`resource/style/` 自带的样式集覆盖 gp7 与 gp8。

## 依赖

<div align="center">

| 源头 | 安装 |
|---|---|
| B 图像·PDF | Python 3.10 以上，只用标准库 |
| A 音频，抓取与分析 | `pip install --user numpy scipy yt-dlp imageio-ffmpeg` |
| A 音频，分轨 | `pip install --user torch torchaudio --index-url https://download.pytorch.org/whl/cpu` 然后 `pip install --user demucs` |
| A 音频，转录 | `pip install --user onnxruntime` 然后 `pip install --user --no-deps basic-pitch` 然后 `pip install --user pretty_midi mir_eval librosa resampy` |

</div>

约束：Python 3.13 下 basic-pitch 必须 `--no-deps` 装，依赖另行补齐，直接装会依赖冲突。torch 与 demucs 分两条 pip 命令。

## 准确率

对 169 个 PDF 的库存实测：

<div align="center">

| 指标 | 值 |
|---|---|
| 能读出音符的文件 | 38 |
| 小节 | 1730 |
| 音符 | 19225 |
| TAB 谱表与五线谱小节数一致 | 198 / 198 |

</div>

准确率用有 `.gp` 真值的歌来测，`.gp` 与其导出 PDF 构成配对。12 首歌 669 个小节：

<div align="center">

| 指标 | 正确 | 比例 |
|---|---|---|
| 音符集合一致 | 368 | 55.0% |
| 时值序列一致 | 265 | 39.6% |
| 两者都一致 | 253 | 37.8% |

</div>

单首最好成绩：`南山南` 音符 58 / 63，`雪落下的声音` 音符 49 / 54。文本层这条路没有结构性障碍，剩下的都是工程问题。

## 源码布局

```
gp-workbench.py                        CLI 入口：route / read / rhythm / gp / convert / verify
src/
├── cli.py
├── converter/
│   ├── converter.py                   PDF 解码结果 -> .gp
│   └── pdf/
│       ├── router.py                  判定 PDF 走哪条解码路径
│       ├── extractor.py               文本层 PDF 取定位字形
│       ├── staff.py                   谱表几何与 TAB 内容
│       ├── outline.py                 TAB 谱表内矢量描边聚成字形
│       ├── rhythm_notation.py         从五线谱符干符杠推时值
│       └── rhythm_tab.py              无五线谱时从 TAB 推时值
├── gp_ops/
│   ├── reader.py                      读 .gp 成逐小节结构
│   ├── writer.py                      模板法写 .gp，只重建 score.gpif 的 id 表
│   └── patcher.py                     原地改 .gp，gpif 当文本改，其余 zip 条目原样复制
├── validator/
│   ├── verifier.py                    悬空引用、小节时值
│   ├── benchmarker.py                 有 .gp 与导出 PDF 的曲目做回归基准
│   └── test/                          测试用例
├── tabulator/
│   ├── init_tabulate.py               头信息
│   ├── apply_style.py                 样式三件，取自 resource/style/ 或参考 .gp
│   ├── inject_chord_diagram.py        和弦图与 <Chord> 标记
│   └── inject_lyrics.py               歌词 token
└── tools/
    ├── chord-finder/
    │   ├── fetch_audio.py             yt-dlp -> 单声道 wav
    │   ├── stem_split.py              demucs htdemucs_6s，取 guitar
    │   ├── transcribe_stem.py         basic-pitch -> 网格 -> 品位 -> 草稿 .gp
    │   └── vocal_syllables.py         音节起点 -> 小节.拍位
    └── survey/
        └── surveyor.py                扫一个 PDF 曲库，按解码路径分类

resource/
└── style/
    ├── gp7/                           BinaryStylesheet、LayoutConfiguration、PartConfiguration，Guitar Pro 7 存档
    └── gp8/                           同样三件，Guitar Pro 8 加载 .gps 后存档
doc/
├── plan.html                          计划文档，用浏览器打开
└── *.md                               研究记录
Generate/Attempt-02/记录.md            音频路径记录
```

命名空间包，无 `__init__.py`。所有脚本从仓库根以 `python <路径>` 运行；`gp-workbench.py` 把仓库根加进 `sys.path` 后调用 `src.cli`。

`src/validator/benchmarker.py` 在解码器每改一次后都要跑，因为单文件调参会过拟合：曾出现单文件 33% 而全库 19% 的情况。

## 开发

```bash
git clone <repo>
cd gp-workbench
python src/validator/benchmarker.py --library <your score library>
```

输出目录，均已 gitignored：

- `work/`：分类表、基准报告
- `build/`：音频、分轨、草稿 `.gp`

采集新样式集：在 Guitar Pro 8 里加载 `.gps`，存档，再从该 `.gp` 抽 `BinaryStylesheet`、`LayoutConfiguration`、`PartConfiguration` 三个条目到 `resource/style/gp8/`。Guitar Pro 8 只采信它自己编译出的样式表：GP7 时代的 `BinaryStylesheet` 塞进 GP8 文件能打开但谱内不画和弦图，`.gps` 是文本 `key=value`，不能直接塞。

计划文档：`doc/plan.html`。研究记录：`doc/*.md`，音频路径记录在 `Generate/Attempt-02/记录.md`。

## 许可

[MIT](LICENSE). © 2026 Hyrex Chia.
