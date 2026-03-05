import yt_dlp
import os
import time
import random
import tempfile
import shutil
import subprocess
from datetime import datetime

DELAY_MIN = 1.0
DELAY_MAX = 3.0

_BASE = os.path.dirname(os.path.abspath(__file__))
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
    }
    ydl_opts, tmp = _apply_cookie(ydl_opts, cookie_path)

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
                        log(f"处理条目 {entry.get('id','?')} 时出错，跳过: {e}")

    except Exception as e:
        log(f"获取频道信息出错: {e}")
    finally:
        _cleanup(tmp2)
        _cleanup(tmp)

    return videos

# 单个视频下载
def download_video(video_url, output_dir,
                   time_start=None, time_end=None,
                   cookie_path=None, log=print, progress_hook=None):
    os.makedirs(output_dir, exist_ok=True)

    # 基本信息获取
    info_opts = {"quiet": True, "no_warnings": True, "skip_download": True,"js_runtimes": {"deno": {"path": _DENO_PATH}}}
    info_opts, tmp_c = _apply_cookie(info_opts, cookie_path)
    title = "video"
    upload_date = ""
    try:
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            title = info.get("title", "video")
            upload_date = info.get("upload_date", "")
    finally:
        _cleanup(tmp_c)

    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    date_prefix = ""
    if upload_date and len(upload_date) == 8:
        date_prefix = datetime.strptime(upload_date, "%Y%m%d").strftime("%m_%d_")

    temp_path  = os.path.join(output_dir, f"{date_prefix}{safe_title}_temp.mp4")
    final_path = os.path.join(output_dir, f"{date_prefix}{safe_title}.mp4")

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
        "quiet": True,
        "no_warnings": True,
        "js_runtimes": {"deno": {"path": _DENO_PATH}},
        "external_downloader": "ffmpeg",
        "external_downloader_args": {
            "ffmpeg_i": input_args,
            "ffmpeg": output_args,
        },
    }

    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    ydl_opts, tmp_c2 = _apply_cookie(ydl_opts, cookie_path)

   #下载
    try:
        log(f"开始下载: {title}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])


        subprocess.run(
            [_FFMPEG_PATH, "-y", "-i", temp_path,
             "-c", "copy", "-movflags", "+faststart", final_path],
            check=True, capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW
        )
        log(f"✅ 完成: {final_path}")
        return True, final_path

    except Exception as e:
        log(f"❌ 下载/处理出错: {e}")
        return False, ""

    finally:
        _cleanup(tmp_c2)
        _cleanup(temp_path)
