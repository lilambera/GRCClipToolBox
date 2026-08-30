# ClipBox（GRCClipToolBox）

视频处理与字幕工具，包含 **Windows 桌面端** 与 **Android 端**。
Android端口处于开发阶段不可使用

| 目录 | 说明 |
|------|------|
| [`desktop/`](desktop/) | Python 桌面版：YouTube 下载、Whisper 字幕、字幕烧录等 |
| [`android/`](android/) | Android 版（Kotlin + Jetpack Compose） |

## 桌面端

```powershell
cd desktop
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.json.example config.json
python main.py
```

详细说明见 [desktop/README.md](desktop/README.md)。

## Android 端

用 Android Studio 打开 `android/` 目录即可构建运行。

```powershell
cd android
.\gradlew assembleDebug
```

## 仓库说明

本仓库整合了原先的两个项目：

- 桌面端：[GRCClipToolBox](https://github.com/lilambera/GRCClipToolBox)
- Android 端：[ClipBox-android](https://github.com/lilambera/ClipBox-android)（已迁入 `android/`，旧仓库可 archive）

## License

MIT License
