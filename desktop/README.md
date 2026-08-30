# ClipBox 桌面端（Windows）

Python 桌面工具：YouTube 下载、Whisper 字幕生成、字幕烧录等。

## 环境要求

- Windows 10/11
- Python 3.10+
- （可选）NVIDIA GPU + CUDA，用于 Whisper GPU 加速

## 快速开始

```powershell
cd desktop
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.json.example config.json
python main.py
```

## 准备 ffmpeg 与 deno

体积较大，未纳入 Git。可手动放置，或运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_deps.ps1
```

目录结构：

```
desktop/
  ffmpeg/bin/ffmpeg.exe
  ffmpeg/bin/ffprobe.exe
  deno/deno.exe
```

## 打包为 exe

```powershell
cd desktop
pyinstaller main.spec
python verify_bundle.py
```

输出在 `desktop/dist/main/`。

## 不应提交的文件

`config.json`、`cookies.txt`、`dist/`、`build/`、`ffmpeg/`、`deno/` 已在仓库根目录 `.gitignore` 中排除。
