# ab_render

把有争议的和弦渲染成可听的 A/B 片段，候选和弦叠在原曲上，错的打架，对的扣住。

## 依赖

numpy。音轨需先由 `tools/fetch_audio` 产出。

## 用法

```bash
python tools/ab_render/ab_render.py
python tools/ab_render/ab_render.py --only d13
```

输出：`build/ab/<id>_<字母>_<和弦>.wav`

| 参数 | 默认 | 说明 |
|---|---|---|
| `--wav` | `build/audio/song.wav` | 音轨 |
| `--disputes` | `Generate/Attempt-02/disputes.json` | 分歧清单 |
| `--out` | `build/ab` | 输出目录 |
| `--only` | 无 | 只渲染指定 id |

裁决结果填回 `disputes.json` 的 `verdict` 字段。
