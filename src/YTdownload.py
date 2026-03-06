import yt_dlp
import os
import time
import random
import tempfile
import shutil
import subprocess
import sys
import traceback
from datetime import datetime

DELAY_MIN = 1.0
DELAY_MAX = 3.0

def _get_base_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS  # _internal 目录
    return os.path.dirname(os.path.abspath(__file__))

_BASE = _get_base_dir()
_DENO_PATH = os.path.join(_BASE, "deno", "deno.exe")
_FFMPEG_PATH = os.path.join(_BASE, "ffmpeg", "bin", "ffmpeg.exe")

def ensure_ejs():
    try:
        with yt_dlp.YoutubeDL({
            "quiet": True,
            "no_warnings": True,
            "remote_components": ["ejs:github"],
            "js_runtimes": [f"deno:{_DENO_PATH}"],
        }) as ydl:
            pass
    except Exception:
        pass

ensure_ejs()

#Cookie设定
def _apply_cookie(ydl_opts, cookie_path):
    if not cookie_path or not os.path.isfile(cookie_path):
        return dict(ydl_opts), None
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    shutil.copy2(cookie_path, temp.name)
    ydl_opts = dict(ydl_opts)
    ydl_opts["cookiefile"] = temp.name
    return ydl_opts, temp.name

#删除临时文件用的
def _cleanup(path):
    if path:
        try:
            os.remove(path)
        except Exception:
            pass


#频道视频列表抓取
def get_channel_videos(channel_url, start_date, end_date=None,
                       cookie_path=None, log=print):
    date_start_str = start_date.strftime("%Y%m%d")
    date_end_str = end_date.strftime("%Y%m%d") if end_date else None

    ydl_opts = {
        "quiet":           True,
        "no_warnings":     True,
        "extract_flat":    True,
        "js_runtimes": {"deno": {"path": _DENO_PATH}},
        "logger": _YtdlpLogger(log, filter_tab=True)
    }
    ydl_opts, tmp = _apply_cookie(ydl_opts, cookie_path)
    tmp2 = None

    videos = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            log(f"正在获取频道列表（{date_start_str} ~ {date_end_str or '今天'}）: {channel_url}")
            result = ydl.extract_info(channel_url, download=False)

            if not result or "entries" not in result:
                log("未找到视频列表")
                return videos

            entries = list(result["entries"])
            detail_opts = {"quiet": True, "no_warnings": True,"js_runtimes": {"deno": {"path": _DENO_PATH}}}
            detail_opts, tmp2 = _apply_cookie(detail_opts, cookie_path)

            with yt_dlp.YoutubeDL(detail_opts) as ydl2:
                for entry in entries:
                    if not entry or not entry.get("id"):
                        continue
                    try:
                        vid_url = f"https://www.youtube.com/watch?v={entry['id']}"
                        info = ydl2.extract_info(vid_url, download=False)
                        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

                        # 日期解析
                        upload_date = info.get("upload_date")
                        if not upload_date:
                            log(f"无法确定日期，跳过: {info.get('title', entry['id'])}")
                            continue

                        video_date = datetime.strptime(upload_date, "%Y%m%d")
                        if video_date < start_date:
                            log("已到达起始日期之前，停止搜索。")
                            break
                        if end_date and video_date > end_date:
                            log(f"跳过（超过结束日期）: {info.get('title')}")
                            continue

                        videos.append({
                            "id":          entry["id"],
                            "title":       info.get("title", "Unknown"),
                            "url":         vid_url,
                            "upload_date": upload_date,
                            "processed":   False,
                        })
                        log(f"找到: {info.get('title')} ({video_date.strftime('%Y-%m-%d')})")


                    except Exception as e:
                        err = str(e)
                        if "This live event will begin" in err or "Premiere will begin" in err:
                            log(f"跳过（预定/首播未开始）: {entry.get('id', '?')}")
                        else:
                            log(f"处理条目 {entry.get('id', '?')} 时出错，跳过: {e}")

    except Exception as e:
        log(f"获取频道信息出错: {e}")
        log(traceback.format_exc())
    finally:
        _cleanup(tmp2)
        _cleanup(tmp)

    return videos

# 单个视频下载
def download_video(video_url, output_dir,
                   time_start=None, time_end=None,
                   cookie_path=None, log=print, progress_hook=None):

    # 启动时打印路径信息，方便排查
    log(f"[调试] _BASE     = {_BASE}")
    log(f"[调试] DENO路径  = {_DENO_PATH}  存在={os.path.isfile(_DENO_PATH)}")
    log(f"[调试] FFMPEG路径= {_FFMPEG_PATH}  存在={os.path.isfile(_FFMPEG_PATH)}")

    os.makedirs(output_dir, exist_ok=True)

    # 基本信息获取
    info_opts = {
        "quiet": False,
        "no_warnings": False,
        "skip_download": True,
        "js_runtimes": {"deno": {"path": _DENO_PATH}},
        "remote_components": ["ejs:github"],
        "logger": _YtdlpLogger(log),
    }
    info_opts, tmp_c = _apply_cookie(info_opts, cookie_path)
    title = "video"
    upload_date = ""
    try:
        log("▶ 正在获取视频信息…")
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            title = info.get("title", "video")
            upload_date = info.get("upload_date", "")
        log(f"  标题: {title}")
    except Exception as e:
        log(f"❌ 获取视频信息失败: {e}")
        log(traceback.format_exc())
        return False, ""
    finally:
        _cleanup(tmp_c)

    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    date_prefix = ""
    if upload_date and len(upload_date) == 8:
        date_prefix = datetime.strptime(upload_date, "%Y%m%d").strftime("%m_%d_")

    temp_path  = os.path.join(output_dir, f"{date_prefix}{safe_title}_temp.mp4")
    final_path = os.path.join(output_dir, f"{date_prefix}{safe_title}.mp4")
    log(f"[调试] 临时文件  = {temp_path}")
    log(f"[调试] 输出文件  = {final_path}")

    #时间区间组
    input_args = []
    output_args = ["-loglevel", "error", "-nostats"]

    if time_start:
        input_args += ["-ss", time_start]
    if time_end:
        input_args += ["-to", time_end]

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": temp_path,
        "quiet": False,
        "no_warnings": False,
        "js_runtimes": {"deno": {"path": _DENO_PATH}},
        "remote_components": ["ejs:github"],
        "external_downloader": "ffmpeg",
        "external_downloader_args": {
            "ffmpeg_i": input_args,
            "ffmpeg": output_args,
        },
        "logger": _YtdlpLogger(log),
    }

    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    ydl_opts, tmp_c2 = _apply_cookie(ydl_opts, cookie_path)

    # 下载
    try:
        log(f"▶ 开始下载: {title}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        log("  下载完成，正在封装…")

        result = subprocess.run(
            [_FFMPEG_PATH, "-y", "-i", temp_path,
             "-c", "copy", "-movflags", "+faststart", final_path],
            capture_output=True, text=True,encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode != 0:
            log(f"❌ ffmpeg封装失败，返回码: {result.returncode}")
            log(f"   stderr: {result.stderr}")
            return False, ""

        log(f"✅ 完成: {final_path}")
        return True, final_path

    except Exception as e:
        log(f"❌ 下载/处理出错: {e}")
        log(traceback.format_exc())
        return False, ""

    finally:
        _cleanup(tmp_c2)
        _cleanup(temp_path)


class _YtdlpLogger:
    """把 yt-dlp 内部日志转发到 log 回调"""
    def __init__(self, log_fn, filter_tab=False):
        self._log = log_fn
        self._filter_tab = filter_tab
    def debug(self, msg):
        if msg.startswith("[debug]"):
            return
        if self._filter_tab and "[youtube:tab]" in msg:
            return
        self._log(msg)
    def info(self, msg):
        if self._filter_tab and "[youtube:tab]" in msg:
            return
        self._log(msg)
    def warning(self, msg):
        self._log(f"[警告] {msg}")
    def error(self, msg):
        self._log(f"[错误] {msg}")