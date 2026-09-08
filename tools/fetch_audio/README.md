# fetch_audio

抓音轨并归一化成分析层要的单声道 wav。

## 依赖

```bash
pip install --user yt-dlp imageio-ffmpeg
```

两者都不需要管理员权限。

## 用法

```bash
python tools/fetch_audio/fetch_audio.py --url <链接>
```

输出：`build/audio/song.wav`，单声道 11025 Hz

| 参数 | 默认 | 说明 |
|---|---|---|
| `--url` | 无 | 必填 |
| `--out` | `build/audio/song.wav` | 输出路径 |
| `--rate` | `11025` | 采样率 |
