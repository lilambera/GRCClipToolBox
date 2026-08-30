# 管人吃烤肉工具集 (videofloder)

视频处理与字幕烧录桌面工具，支持 YouTube 下载、Whisper 字幕生成等功能。

## 功能

- 字幕烧录到视频
- YouTube 视频下载（支持批量抓取直播窗）
- 基于 faster-whisper 的字幕生成（需自行下载模型）
- ASS → TXT、YouTube 字幕重断句、时间戳提取
- YouTube Cookies 获取

## 环境要求

- Windows 10/11
- Python 3.10+
- （可选）NVIDIA GPU + CUDA，用于 Whisper GPU 加速

## 快速开始

### 1. 克隆并安装 Python 依赖

```powershell
git clone <your-repo-url>
cd videofloder
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 准备 ffmpeg 与 deno（打包和下载功能需要）

这两个目录体积较大，未纳入 Git。请手动放置：

```
videofloder/
  ffmpeg/
    bin/
      ffmpeg.exe
      ffprobe.exe
  deno/
    deno.exe
```

- **ffmpeg**：从 [ffmpeg.org](https://ffmpeg.org/download.html) 下载 Windows build，解压后将 `bin` 目录放到 `ffmpeg/bin/`。
- **deno**：从 [deno.land](https://deno.land/) 下载 Windows 可执行文件，放到 `deno/deno.exe`。

### 3. 配置文件

```powershell
copy config.json.example config.json
```

按需编辑 `config.json` 中的路径与 Whisper 参数。

### 4. 运行

```powershell
python main.py
```

## 打包为 exe

确保 `ffmpeg/`、`deno/`、`config.json`、`icon.ico` 已就绪后：

```powershell
pyinstaller main.spec
```

输出在 `dist/main/`。可用以下命令验证打包结果：

```powershell
python verify_bundle.py
python verify_bundle.py --launch-gui
```

## 不应提交的文件

以下文件已在 `.gitignore` 中排除：

| 路径 | 原因 |
|------|------|
| `dist/`, `build/` | PyInstaller 构建产物（约 2GB） |
| `ffmpeg/`, `deno/` | 大型二进制依赖 |
| `config.json` | 含本机绝对路径 |
| `cookies.txt` | YouTube 登录凭证 |
| `toolbox/` | 旧版嵌套 Git 仓库 |

## License

MIT License
