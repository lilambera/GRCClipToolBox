# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

spec_dir = os.path.dirname(os.path.abspath(SPEC))

ffmpeg_dir = os.path.join(spec_dir, "ffmpeg")
deno_dir = os.path.join(spec_dir, "deno")
ffmpeg_bin_dir = os.path.join(ffmpeg_dir, "bin")

for label, path in (
    ("ffmpeg", ffmpeg_dir),
    ("deno", deno_dir),
    ("ffmpeg/bin/ffmpeg.exe", os.path.join(ffmpeg_bin_dir, "ffmpeg.exe")),
    ("ffmpeg/bin/ffprobe.exe", os.path.join(ffmpeg_bin_dir, "ffprobe.exe")),
):
    if not os.path.exists(path):
        raise SystemExit(f"打包缺少依赖，请先准备: {path} ({label})")

datas = [
    (os.path.join(spec_dir, "config.json"), "."),
    (os.path.join(spec_dir, "icon.ico"), "."),
    (ffmpeg_dir, "ffmpeg"),
    (deno_dir, "deno"),
]
datas += collect_data_files("faster_whisper")

binaries = []

# Optional CUDA runtime DLLs for faster-whisper GPU mode.
conda_prefix = os.environ.get("CONDA_PREFIX", r"F:\anaconda3\envs\fuwayear")
cuda_bin = os.path.join(conda_prefix, "Library", "bin")
for dll in ("cublas64_12.dll", "cublasLt64_12.dll", "cudart64_12.dll"):
    src = os.path.join(cuda_bin, dll)
    if os.path.isfile(src):
        binaries.append((src, "."))

binaries += collect_dynamic_libs("ctranslate2")

hiddenimports = [
    "paths",
    "bilibili_download",
    "yt_dlp",
    "faster_whisper",
    "undetected_chromedriver",
]

a = Analysis(
    ["main.py"],
    pathex=[spec_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="main",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(spec_dir, "icon.ico")],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="main",
)
