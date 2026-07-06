import os
import sys


def get_resource_dir():
    """Bundled read-only assets: ffmpeg, deno, icon, etc."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_app_dir():
    """User-writable app directory (config.json lives here when frozen)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def ffmpeg_bin(name="ffmpeg.exe"):
    return os.path.join(get_resource_dir(), "ffmpeg", "bin", name)


def deno_bin():
    return os.path.join(get_resource_dir(), "deno", "deno.exe")
