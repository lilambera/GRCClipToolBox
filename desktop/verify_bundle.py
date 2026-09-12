"""
本地验证打包是否自洽，尽量排除「本机已安装 ffmpeg / conda」的干扰。

重点：
  - 请测 dist/main/main.exe，不要测 python main.py（后者一定走开发环境）
  - 打包后的 main.exe 不会用本机 Python/conda 里的库
  - ffmpeg/deno 已改为 bundled 资源：paths.py 在打包后指向 _internal，不依赖系统 PATH
  - 本脚本会额外把 PATH/conda 清掉再跑一遍，确认包内工具自己能执行

用法:
  python verify_bundle.py
  python verify_bundle.py --dist dist/main
  python verify_bundle.py --launch-gui
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile


# 只保留 Windows 系统目录，故意去掉 ffmpeg / conda / python 等
MINIMAL_PATH = os.pathsep.join([
    r"C:\Windows\System32",
    r"C:\Windows",
])

STRIP_ENV_KEYS = (
    "PATH",
    "PYTHONPATH",
    "PYTHONHOME",
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV",
    "CONDA_PYTHON_EXE",
    "VIRTUAL_ENV",
    "CUDA_PATH",
    "CUDA_HOME",
)


def make_isolated_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV_KEYS}
    env["PATH"] = MINIMAL_PATH
    env["SystemRoot"] = os.environ.get("SystemRoot", r"C:\Windows")
    env["WINDIR"] = os.environ.get("WINDIR", r"C:\Windows")
    return env


def check_dist(dist_dir: str) -> list[str]:
    errors: list[str] = []
    exe = os.path.join(dist_dir, "main.exe")
    internal = os.path.join(dist_dir, "_internal")
    ffmpeg = os.path.join(internal, "ffmpeg", "bin", "ffmpeg.exe")
    ffprobe = os.path.join(internal, "ffmpeg", "bin", "ffprobe.exe")
    deno = os.path.join(internal, "deno", "deno.exe")
    icon = os.path.join(internal, "icon.ico")

    for label, path in (
        ("main.exe", exe),
        ("_internal", internal),
        ("ffmpeg.exe", ffmpeg),
        ("ffprobe.exe", ffprobe),
        ("deno.exe", deno),
        ("icon.ico", icon),
    ):
        if os.path.exists(path):
            print(f"  [OK] {label}")
        else:
            print(f"  [缺失] {label}: {path}")
            errors.append(label)
    return errors


def simulate_frozen_paths(internal_dir: str) -> list[str]:
    errors: list[str] = []
    sys.modules.pop("paths", None)

    sys.frozen = True  # type: ignore[attr-defined]
    sys._MEIPASS = internal_dir  # type: ignore[attr-defined]

    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from paths import deno_bin, ffmpeg_bin, get_resource_dir

    ffmpeg = ffmpeg_bin()
    deno = deno_bin()
    print(f"  get_resource_dir() -> {get_resource_dir()}")
    print(f"  ffmpeg_bin()       -> {ffmpeg}")
    print(f"  deno_bin()         -> {deno}")

    for label, path in (("ffmpeg_bin()", ffmpeg), ("deno_bin()", deno)):
        if os.path.isfile(path):
            print(f"  [OK] {label}")
        else:
            print(f"  [失败] {label} 不存在")
            errors.append(label)

    del sys.frozen  # type: ignore[attr-defined]
    del sys._MEIPASS  # type: ignore[attr-defined]
    sys.modules.pop("paths", None)
    return errors


def run_tool(exe_path: str, args: list[str], env: dict[str, str] | None = None) -> bool:
    try:
        result = subprocess.run(
            [exe_path, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception as exc:
        print(f"  [失败] 无法运行 {exe_path}: {exc}")
        return False

    if result.returncode != 0:
        print(f"  [失败] {os.path.basename(exe_path)} {' '.join(args)}")
        if result.stderr.strip():
            print(f"         {result.stderr.strip()[:200]}")
        return False

    first_line = (result.stdout or result.stderr).strip().splitlines()[0]
    print(f"  [OK] {os.path.basename(exe_path)}: {first_line[:120]}")
    return True


def where_in_env(command: str, env: dict[str, str]) -> str | None:
    try:
        result = subprocess.run(
            ["where", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    return line or None


def test_isolated_tools(internal_dir: str) -> list[str]:
    """在剥离 PATH/conda 的环境里，确认只能依赖 _internal 里的工具。"""
    errors: list[str] = []
    env = make_isolated_env()
    ffmpeg = os.path.join(internal_dir, "ffmpeg", "bin", "ffmpeg.exe")
    deno = os.path.join(internal_dir, "deno", "deno.exe")

    print("  隔离环境 PATH =", env["PATH"])
    sys_ffmpeg = where_in_env("ffmpeg", env)
    sys_deno = where_in_env("deno", env)
    if sys_ffmpeg:
        print(f"  [注意] 隔离环境里仍能找到系统 ffmpeg: {sys_ffmpeg}")
        print("         若存在，请暂时把 ffmpeg 从系统 PATH 移除后再测，结果更可靠。")
    else:
        print("  [OK] 隔离环境里找不到系统 ffmpeg")

    if sys_deno:
        print(f"  [注意] 隔离环境里仍能找到系统 deno: {sys_deno}")
    else:
        print("  [OK] 隔离环境里找不到系统 deno")

    print("  在隔离环境里运行 bundled ffmpeg/deno:")
    if not run_tool(ffmpeg, ["-version"], env=env):
        errors.append("isolated bundled ffmpeg")
    if not run_tool(deno, ["--version"], env=env):
        errors.append("isolated bundled deno")

    return errors


def copy_dist(dist_dir: str) -> str:
    temp_root = tempfile.mkdtemp(prefix="videofloder_bundle_test_")
    copied = os.path.join(temp_root, "main")
    print(f"  复制到: {copied}")
    shutil.copytree(dist_dir, copied)
    return copied


def launch_gui(exe_path: str) -> None:
    env = make_isolated_env()
    cwd = os.path.dirname(exe_path)
    print(f"  启动: {exe_path}")
    print("  使用隔离 PATH（不含 conda / 全局 ffmpeg）")
    subprocess.Popen([exe_path], cwd=cwd, env=env)


def print_manual_tips(copied_dir: str | None) -> None:
    print("\n=== 怎么理解测试结果 ===")
    print("1. python main.py 只能测开发环境，不能代表打包结果。")
    print("2. main.exe 里的 Python 库来自 _internal，不会读你 conda 里的 site-packages。")
    print("3. ffmpeg/deno 走 bundled 路径（_internal/ffmpeg、_internal/deno），不依赖系统 PATH。")
    print("   干净电脑上已经能跑通的话，这块可以视为没问题；本脚本只是打包后复查文件是否还在。")
    print("4. 仍可能依赖本机的东西：")
    print("   - Chrome（Cookie 获取功能，本来就要装 Chrome）")
    print("   - NVIDIA 驱动/CUDA（Whisper GPU 模式；CPU 模式更独立）")
    print("5. 最接近「另一台干净电脑」的办法：Windows 沙盒")
    print("   - Win+R 输入 optionalfeatures，启用 Windows 沙盒")
    print("   - 把整个 dist/main 文件夹复制进沙盒桌面再运行 main.exe")

    if copied_dir:
        print(f"\n隔离测试目录: {copied_dir}")
        print("建议手动操作:")
        print(f"  1. 打开 {copied_dir}\\main.exe")
        print("  2. 下载页看日志: DENO路径/FFMPEG路径 存在=True")
        print("  3. 字幕烧录页试一个短视频")
        print("  4. Whisper 先用 CPU + int8 测，避免 CUDA 干扰")


def main() -> int:
    parser = argparse.ArgumentParser(description="本地验证 PyInstaller 打包结果")
    parser.add_argument(
        "--dist",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "main"),
        help="打包输出目录，默认 dist/main",
    )
    parser.add_argument(
        "--launch-gui",
        action="store_true",
        help="在隔离环境里启动复制后的 main.exe",
    )
    args = parser.parse_args()
    dist_dir = os.path.abspath(args.dist)

    print("=== 打包本地验证（隔离环境） ===")
    print(f"目标目录: {dist_dir}\n")

    if not os.path.isdir(dist_dir):
        print("未找到打包目录。请先执行:")
        print(r'  F:\anaconda3\envs\fuwayear\python.exe -m PyInstaller main.spec --noconfirm')
        return 1

    errors: list[str] = []

    print("[1/5] 检查 _internal 里关键文件是否存在")
    errors.extend(check_dist(dist_dir))

    internal = os.path.join(dist_dir, "_internal")
    print("\n[2/5] 模拟 frozen 路径解析")
    errors.extend(simulate_frozen_paths(internal))

    print("\n[3/5] 复制到临时目录，模拟拷到 U 盘/别的路径")
    copied = copy_dist(dist_dir)
    copied_internal = os.path.join(copied, "_internal")

    print("\n[4/5] 在隔离 PATH/conda 环境里测试 bundled 工具")
    errors.extend(test_isolated_tools(copied_internal))

    print("\n[5/5] 对比：当前开发环境下系统 ffmpeg 是否可见")
    dev_ffmpeg = shutil.which("ffmpeg")
    if dev_ffmpeg:
        print(f"  当前系统 ffmpeg: {dev_ffmpeg}")
        print("  这不影响 main.exe 走 bundled 路径，但会影响你用 python main.py 时的测试结果。")
    else:
        print("  当前 shell 找不到系统 ffmpeg")

    if args.launch_gui:
        print("\n[附加] 启动 GUI（隔离环境）")
        launch_gui(os.path.join(copied, "main.exe"))

    print("\n=== 结果 ===")
    if errors:
        print("未通过项:", ", ".join(dict.fromkeys(errors)))
        return 1

    print("自动检查全部通过。")
    print_manual_tips(copied)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
