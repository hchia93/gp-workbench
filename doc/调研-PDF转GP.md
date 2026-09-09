# 调研: PDF 转 GP

## 结论

`.gp`（GP7/GP8）本质是 ZIP 包，核心数据 `Content/score.gpif` 是纯 XML。用模板法（保留除 `score.gpif` 外的所有条目，只重写 XML）可以程序化生成 Guitar Pro 能打开的文件。已生成《空港曲》24 小节验证通过。

## .gp 文件结构

文件头 4 字节: `PK\003\004`（标准 ZIP）

| 条目 | 内容 |
| --- | --- |
| `Content/score.gpif` | 核心乐谱数据，纯 XML |
| `Content/BinaryStylesheet` | 排版样式，二进制 |
| `Content/LayoutConfiguration` | 布局，二进制 |
| `Content/PartConfiguration` | 分谱配置，二进制 |
| `Content/Preferences.json` | JSON |
| `Content/ScoreViews/*.gpsv` | 视图 |
| `Content/Stylesheets/*.gpss` | 样式表 |
| `VERSION` / `meta.json` | 版本与元数据 |

历史格式:

| 扩展名 | 版本 | 容器 |
| --- | --- | --- |
| `.gp3` / `.gp4` / `.gp5` | GP3-GP5 | 专有二进制 |
| `.gpx` | GP6 | 专有压缩容器 BCFZ/BCFS |
| `.gp` | GP7/GP8 | ZIP + XML |

## gpif 是扁平 id 表 + 引用图

不是嵌套树。引用链:

```text
MasterBar → <Bars>0 1</Bars>
  Bar     → <Voices>0 -1 -1 -1</Voices>
    Voice → <Beats>0 1 2 3</Beats>
      Beat→ <Notes>0 1</Notes> + <Rhythm ref="5"/>
```

生成器必须自己分配 id 并保证交叉引用一致。`-1` 表示空声部。

## 音高计算规则

实测反推，已在 34 个文件上验证。

| 项 | 值 |
| --- | --- |
| `Tuning` 的 `Pitches` | `40 45 50 55 59 64`，低音到高音 |
| `String` 索引 0 | 六弦（最低音） |
| `String` 索引 5 | 一弦 |
| 公式 | `midi = Tuning[stringIndex] + fret + CapoFret` |
| `ConcertPitch` 的 Octave | `midi // 12`，音级取 `midi % 12` |
| `TransposedPitch` 的 Octave | 比 ConcertPitch 大 1（Track 上有 `Transpose/Octave = -1`） |

TAB 上的品位数字是相对变调夹的，不是绝对品位。

## 技巧词汇表可穷举

扫描全部 34 个 `.gp`，只出现 40 种 `Property name`。去掉音高和音色相关的，演奏技巧只有八个:

`Muted` `PalmMuted` `Brush` `HopoOrigin` `HopoDestination` `Slide` `PickStroke` `Harmonic`

每个都能用 diff 法反推: GP 里加一个技巧，存盘，解压对比 XML。

`XProperty` 的 id 是无名魔数（如 `687935489`），推测属于显示层，生成时整块省略未影响打开。

Property 在 `<Properties>` 内按字母序排列，生成时保持该顺序。

## PDF 分类结果

样本 169 个文件，`src/tools/survey_route.py` 产出。

| 类别 | 数量 | 判定依据 | 转换路径 |
| --- | --- | --- | --- |
| `image` | 66 | 有图无字体 | 抽图 + 视觉识别 |
| `qt-export` | 41 | Producer 含 `Qt`，Guitar Pro 导出 | 文本层带坐标，几何定位，无需 OCR |
| `text` | 36 | 有字体无图 | 同上，排版各异 |
| `mixed` | 20 | 图和字体都有 | 视情况 |
| `vector` | 6 | 两者皆无 | 待查 |

`qt-export` 那批的内容流里，品位数字是带精确坐标的文本对象（`Td` 偏移），六线是矢量线段。判断数字属于哪根弦是坐标匹配，属于几何计算不是识别。

## 难点: 静默失败

gpif 没有公开 schema，没有 validator。Guitar Pro 对坏输入是降级不报错，最大风险是写错了不知道。

实证: 34 个由 Guitar Pro 自己生成的文件里，17 个存在小节时值不闭合（beats 加总不等于拍号），GP 照常打开。时值错误不会被 GP 拦截。

对策是 `src/validator/verifier.py`，检查两件 GP 不会报的事: 悬空 id 引用、小节时值不闭合。

## 工具清单

目录: `Automate/`

| 文件 | 作用 | 备注 |
| --- | --- | --- |
| `src/tools/survey_route.py` | 扫描全库 PDF 分类，产出 `work/routes.tsv` | 只读，幂等 |
| `src/gp_ops/writer.py` | 模板法生成 `.gp` | 只重写 score.gpif，其余条目原样复制 |
| `kongangqu.py` | 《空港曲》曲谱数据 + 生成入口 | pattern 来自 `笔技.txt` |
| `src/validator/verifier.py` | 校验引用图与时值闭合 | 支持多文件，失败返回非零 |

## 《空港曲》验证结果

| 项 | 值 |
| --- | --- |
| 输出 | `Automate/out/空港曲 - 宋冬野 (generated).gp` |
| 规模 | 24 小节 / 144 beats / 144 notes |
| 拍号 | 6/8 |
| 变调夹 | 2 品 |
| Tempo | 76 |
| 校验 | 无悬空引用，24 小节时值全部闭合 |
| GP 打开 | 已由 Guitar Pro 打开并保存，模板法验证通过 |

内容来源: 和弦序列读自 PDF 图像，右手弹奏型来自同目录的 `空港曲 - 宋冬野 (笔技).txt`。该 txt 用 3 个八分音符为一组的记法（如 `Dm = 654 654 654 654`），四组为一个标签，即一个标签跨两个 6/8 小节。

| pattern | 来源形态 | 处理 |
| --- | --- | --- |
| `Dm` `Am` `Em` `F` | txt 里是明确的弦序数字 | 直接编码 |
| `C1` `C2` `C3` `F1` `F2` | txt 里是文字描述（如 `C1 = Cmaj7 + 敲2弦1品 + Cmaj7 + 敲3弦2品`） | 按三音一组惯例实现，属于解读而非逐字照搬 |

已知偏差: 谱面标注是「变调夹夹 1-5 弦第二品，第六弦空弦」即部分变调夹，生成时用了整体 `CapoFret = 2`。gpif 有 `PartialCapoFret` 和 `PartialCapoStringFlags`（Bitset）字段，bitset 位序未验证，故未使用。

## 校对结果

用户在 Guitar Pro 里修改生成文件的第 1 到 7 小节并保存，逐小节 diff。

记法: `s5f3` 为五弦 3 品，`ᴴ` 为 Hopo（击弦或勾弦），`/` 分隔两个三音组。

| 小节 | 生成的 | 修正后 | 差异 |
| --- | --- | --- | --- |
| 1 | `s5f3 s3f0 s2f0 / s5f3 s3f0 s2f1` | `s5f3+s1f0 s3f0 s2f0 / s5f3 s3f0 s2f1` | 第 1 拍加一弦空弦 |
| 2 | `s5f3 s3f0 s2f0 / s5f3 s3f2 s2f0` | `s5f3 s3f0 s2f0 / s5f3 s3f0 s3f2` | 敲弦落在第 3 音 |
| 3 | `s6f1 s5f3 s3f2 / s6f1 s5f3 s3f2` | `s6f1 s5f3 s3f2 / s6f1 s5f3 s2f1` | 第 2 组第 3 音换到二弦 |
| 4 | `s6f1 s5f3 s3f0 / s6f1 s5f3 s2f3` | 一致 | 无 |
| 5 | 同 1 | 同 1 修正 | 同 1 |
| 6 | `s5f3 s3f0 s2f0 / s5f3 s2f1 s2f1` | `s5f3 s3f0 s2f0 / s2f1ᴴ s2f0ᴴ s3f0` | 真击勾，且无低音 |
| 7 | `s4f3 s3f2 s2f1 / s4f3 s3f2 s2f1` | `s6f1 s5f3 s3f0 / s6f1 s5f3 s3f2` | 整小节应为大横按 653 |
| 8 | `s4f3 s3f0 s2f1 / s4f3 s3f2 s2f1` | 未改 | 无 |

## 四个结构性错误

| 错误 | 表现 | 根因 |
| --- | --- | --- |
| 三音组第三音是换弦不是换品 | `敲3弦2品` 被实现成「本组三弦改弹 2 品」，实际是「第 3 个音换到三弦 2 品」，前两音不变 | `unit()` 抽象本身建模错 |
| 漏了双音 | C 组第 1 拍应为 `s5f3 + s1f0`，低音与一弦空弦同时 | 记法未表达同时发声 |
| 击勾按普通音符写 | 应使用 `HopoOrigin` / `HopoDestination` | 生成器未支持该属性 |
| `F2` 两小节把位搞反 | 第 1 小节是大横按 653，第 2 小节才是半横按 432 | 对 `半横按F + 3弦交替` 的解读错误 |

## 关键判断: 瓶颈在输入记法

| 记法类型 | 例子 | 结果 |
| --- | --- | --- |
| 数字弦序 | `Dm = 654 654 654 654` | 第 4、8 小节完全正确 |
| 文字描述 | `C1 = Cmaj7 + 敲2弦1品` | 6 个小节全错 |

同一个模型读数字记法准确，读文字描述出错。提升准确率最便宜的动作是规范记法，不是更换执行者或加大算力。

## Guitar Pro 的两个行为

| 行为 | 观测 | 影响 |
| --- | --- | --- |
| 保存时去重 | 生成的 144 个 Note 被收敛到 17 个，Beat 之间复用 id | 生成器不必自己去重 |
| 容忍时值不闭合 | 34 个由 GP 自己生成的文件里，17 个有 beats 加总不等于拍号的小节，照常打开 | 时值错误不会被 GP 拦截，必须靠 `src/validator/verifier.py` |

## Token 实测

数据取自 session transcript，非估算。范围为本次调研全程。

| 项 | 值 |
| --- | --- |
| output | 165,487 |
| cache_write（新增内容） | 575,622 |
| cache_read（累计复读） | 13,405,137 |
| 未缓存 input | 227 |
| 工具调用 | 54 |
| 图片读取 | 5 |
| 子代理（写文档） | 56,977 |

成本结构: output 的绝大部分花在探索 gpif 格式，属一次性投入，结论已写入本文档。格式已知后，生成第二首曲子的边际 output 预计在 10k 到 20k 量级。

cache_read 是每轮重读已缓存前缀的累计值，不代表独立内容量。独立内容量看 `cache_write + input`，约 576k。

## 三条路线

三条不互斥，尚未决定采用哪条。

| 路线 | 做法 | 准的层 | 不准的层 | 前置投入 | 边际成本 |
| --- | --- | --- | --- | --- | --- |
| A 模型补全 | 模型读图后直接补和弦、歌词、段落结构 | 拍号、调号、变调夹、tempo、和弦序列、段落 | 具体弦位、双音、技巧、组内落点 | 无 | 每首 10k 到 20k output |
| B 图像提时值 | 几何定位六线与小节线，识别符干符尾与 beam 分组 | 时值、小节边界 | 弦位仍需分类器 | 高，需写 blob 分类 | 每首低 |
| C 脚本加组合 | 脚本做确定性部分，模型做解读部分，人做验收 | 确定性部分 100% | 解读部分同 A | 中，已完成大半 | 每首 10k 到 20k output |

已完成的确定性部分: ZIP 打包、XML 生成、id 分配、音高换算、时值闭合校验、悬空引用校验。

本次实测对 C 的支持最强: 第 4 和第 8 小节正确，正是因为输入是数字记法；错的全部来自文字描述。

## 后续方向

1. 验证 `PartialCapoStringFlags` 的位序

## 下一步候选

1. 把 `笔技.txt` 的文字描述改写成数字弦序记法，消除解读环节
2. 给生成器加 Hopo 与同拍多音支持，这两项已知缺失
3. 从修正后的 1 到 7 小节反向抽取 pattern 定义，作为 pattern 库首批条目
4. 打通 41 个 `qt-export` PDF 的坐标提取

方向与分层设计见 [研究方向](研究方向.md)。
