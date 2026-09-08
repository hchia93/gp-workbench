# score-pdf-to-gp

[English](README.md) | **中文**

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Platform: Cross-platform](https://img.shields.io/badge/Platform-Cross--platform-blue.svg)
![Status: Research](https://img.shields.io/badge/Status-Research-orange.svg)

把吉他谱 PDF 转成 Guitar Pro `.gp` 文件。对由制谱软件导出的 PDF，品位数字、谱表几何、节奏记号全部能从 PDF 自身的文本与矢量算子精确取出，不需要 OCR，也不需要任何 LLM。

## 它解决什么

手工把一首谱敲进 Guitar Pro 要两三个小时。现有工具都至少踩中一条：需要上传、要付费、只做五线谱不做六线谱、或者依赖 OCR 因而必然带误差。

<div align="center">

| 工具 | 离线 | 免费 | 六线谱 | 无需 OCR | 说明 |
|---|---|---|---|---|---|
| Audiveris | ✓ | ✓ | ✗ | ✗ | 五线谱 OMR，不处理六线谱 |
| oemer | ✓ | ✓ | ✗ | ✗ | 五线谱 OMR，需要 ML 权重 |
| SmartScore | ✓ | ✗ | 部分 | ✗ | 商业软件，识别为主 |
| PDF to MusicXML 类在线服务 | ✗ | 有限 | 部分 | ✗ | 需要上传 |
| **score-pdf-to-gp** | **✓** | **✓** | **✓** | **✓** | 从 PDF 算子直接解码，不识别 |

</div>

关键区别：主流工具都在做识别，而制谱软件导出的 PDF 里，这些信息本来就是精确存在的，只是没人去读。

## 适合谁

- **手上有一批吉他谱 PDF 的人。** 谱在硬盘里是死的，不可检索不可改调不可换指法。转成 `.gp` 之后才能用
- **想省下重新录入时间的人。** 就算只有七成正确，也是在一个骨架上改，而不是从零敲两三个小时
- **需要可验证结果的人。** 每个小节的时值加总必须等于拍号，不闭合就是错。这个自检不需要人工比对

## 使用

从仓库直接运行：

```bash
python score-pdf-to-gp.py route   <file.pdf>
python score-pdf-to-gp.py read    <file.pdf> [--page N] [--dump]
python score-pdf-to-gp.py rhythm  <file.pdf> [--page N]
python score-pdf-to-gp.py gp      <file.gp>  [--measures A-B]
python score-pdf-to-gp.py verify  <file.gp>...
```

命令：

<div align="center">

| 命令 | 作用 |
|---|---|
| `python score-pdf-to-gp.py route <file.pdf>` | 报告这个 PDF 需要哪条解码路线 |
| `python score-pdf-to-gp.py read <file.pdf> [--page N] [--dump]` | 谱表、小节线、TAB 音符 |
| `python score-pdf-to-gp.py rhythm <file.pdf> [--page N]` | 每小节的时值序列 |
| `python score-pdf-to-gp.py gp <file.gp> [--measures A-B]` | 反读一个 `.gp` |
| `python score-pdf-to-gp.py verify <file.gp>...` | 检查悬空引用与小节时值闭合 |

</div>

工具脚本：

```bash
python tools/survey/survey.py --library <path> --csv work/routes.tsv
python tools/bench/bench.py --library <path>
python tools/bench/bench.py --library <path> --detail "song name"
```

## 工作原理

`.gp` 是 ZIP 包，核心数据 `Content/score.gpif` 是纯 XML。写入端用模板法，只重写这个 XML，其余条目原样复制，所以那些没有公开文档的二进制块保持有效。

读取端按 PDF 能给出什么分三条路线。判据不是 PDF 的 Producer 字段，而是品位数字能否从文本层取出：

<div align="center">

| 路线 | 文件数 | 占比 | 是否需要识别 |
|---|---|---|---|
| text-layer | 38 | 22.5% | 否 |
| image | 46 | 27.2% | 否，形状有限且逐点相同，只需一次标注 |
| no-staff | 85 | 50.3% | 是 |

</div>

`text-layer` 这条的解码链：内容流解释器跟踪 CTM 与文本矩阵得到定位字形，ToUnicode CMap 还原字符，路径算子给出谱表线与小节线，品位数字的基线固定落在所属弦线下方一个常量，标定后弦位归属是一次最近邻匹配。

节奏有两套编码，取决于导出设置：五线谱在场时看符干与符杠层数，TAB-only 时看谱表下方的符尾字形与符杠。

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
src/
├── pdf/        PDF content stream: positioned glyphs and vector segments
├── score/      staff geometry, TAB notes, rhythm from beams and flags
├── gp/         .gp read, write and verify
├── classify.py which route a PDF needs
└── cli.py      command line entry

tools/
├── survey/       全库分类普查
├── bench/        配对回归基准
├── fetch_audio/  抓音轨（音频链路）
└── ab_render/    A/B 片段渲染（音频链路）

doc/
├── plan.html   the working plan, open in a browser
└── *.md        research records
```

模块之间用相对 import，`score-pdf-to-gp.py` 把仓库根加进 `sys.path` 后调用 `src.cli`。刻意不提供 console script，因为 `src/pdf` 与 `src/score` 这类顶层名字装进 site-packages 会撞车。

`tools/bench/bench.py` 是最重要的一个。解码器每改一次都要跑，因为单文件调参会过拟合：曾出现单文件 33% 而全库 19% 的情况。

## 开发

要求 Python 3.10 以上，无第三方依赖，不需要安装。

```bash
git clone <repo>
cd score-pdf-to-gp
python tools/bench/bench.py --library <your score library>
```

`work/` 是 gitignored 的输出目录，分类表与基准报告写在那里。

计划文档见 `doc/plan.html`，用浏览器打开。研究记录是 `doc/` 下的 markdown 文件。

## 路线图

<div align="center">

| 版本 | 内容 |
|---|---|
| v0.1 | 文本层路线，音符与时值解码，回归基准 **（当前）** |
| v0.2 | 修小节切分与连杠组短钩，精度目标 70% |
| v0.3 | 矢量轮廓路线，覆盖率目标 50% |
| 待定 | 纯位图路线 |

</div>

## 许可

[MIT](LICENSE). © 2026 Hyrex Chia.
