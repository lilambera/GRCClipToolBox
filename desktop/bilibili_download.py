import os
import shutil
import traceback
from datetime import datetime
from urllib.parse import urlparse

import yt_dlp


def is_bilibili_url(url):
    if not isinstance(url, str):
        return False
    raw = url.strip()
    if not raw:
        return False
    parsed = urlparse(raw if "://" in raw else "https://" + raw)
    host = (parsed.hostname or "").lower().rstrip(".")
    return host == "bilibili.com" or host.endswith(".bilibili.com")


def _proxy_for_url(video_url):
    """B 站直连。空字符串让 yt-dlp 忽略环境变量和系统代理。"""
    if is_bilibili_url(video_url):
        return ""
    return None


def _output_paths(output_dir, title, upload_date):
    custom_name = os.path.splitext(output_dir)[1]
    save_dir = os.path.dirname(os.path.abspath(output_dir)) if custom_name else output_dir
    os.makedirs(save_dir or ".", exist_ok=True)
    if custom_name:
        name = os.path.splitext(os.path.basename(output_dir))[0]
    else:
        name = "".join(c if c.isalnum() or c in " -_" else "_" for c in (title or "video"))
        if upload_date and len(upload_date) == 8:
            name = datetime.strptime(upload_date, "%Y%m%d").strftime("%m_%d_") + name
    temp_path = os.path.join(save_dir, f"{name}_temp.mp4")
    final_path = os.path.join(save_dir, f"{name}.mp4")
    return temp_path, final_path


def _take_downloaded_file(info, temp_path):
    candidates = []
    if isinstance(info, dict):
        for item in info.get("requested_downloads") or []:
            filepath = item.get("filepath")
            if filepath:
                candidates.append(filepath)
        if info.get("filepath"):
            candidates.append(info["filepath"])
    candidates.append(temp_path)
    for filepath in candidates:
        if filepath and os.path.isfile(filepath):
            if os.path.abspath(filepath) != os.path.abspath(temp_path):
                os.makedirs(os.path.dirname(os.path.abspath(temp_path)) or ".", exist_ok=True)
                if os.path.isfile(temp_path):
                    os.remove(temp_path)
                shutil.move(filepath, temp_path)
            return temp_path
    return None


def download_bilibili_video(video_url, output_dir,
                            time_start=None, time_end=None,
                            cookie_path=None, log=print, progress_hook=None):
    """下载单个 B 站视频到临时 mp4。失败返回 None，成功返回 (临时路径, 最终路径)。"""
    from YTdownload import _YtdlpLogger, _apply_cookie, _cleanup, _common_ydl_opts, _hms_to_sec

    proxy = _proxy_for_url(video_url)
    if proxy is None:
        log("❌ 不是 B 站视频链接")
        return None
    log("  B 站链接，不使用代理")

    info_opts = _common_ydl_opts(
        log,
        quiet=False,
        no_warnings=False,
        skip_download=True,
        noplaylist=True,
        proxy=proxy,
        http_headers={"Referer": "https://www.bilibili.com/"},
        logger=_YtdlpLogger(log),
    )
    info_opts, tmp_c = _apply_cookie(info_opts, cookie_path)
    temp_path = None
    tmp_c2 = None
    ok = False
    try:
        log("▶ 正在获取视频信息…")
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
        if not info:
            log("❌ 获取视频信息失败")
            return None
        if info.get("_type") in ("playlist", "multi_video"):
            log("❌ 当前只支持单个 B 站视频，不支持空间或合集链接")
            return None

        title = info.get("title", "video")
        upload_date = info.get("upload_date", "")
        log(f"  标题: {title}")
        temp_path, final_path = _output_paths(output_dir, title, upload_date)
        log(f"[调试] 临时文件  = {temp_path}")
        log(f"[调试] 输出文件  = {final_path}")

        ydl_opts = _common_ydl_opts(
            log,
            format="bestvideo+bestaudio/best",
            merge_output_format="mp4",
            outtmpl=temp_path,
            noplaylist=True,
            proxy=proxy,
            quiet=False,
            no_warnings=False,
            noprogress=False,
            progress_with_newline=True,
            http_headers={"Referer": "https://www.bilibili.com/"},
            logger=_YtdlpLogger(log, progress_callback=progress_hook),
        )
        if progress_hook:
            ydl_opts["progress_hooks"] = [progress_hook]
        if time_start or time_end:
            from yt_dlp.utils import download_range_func
            start_sec = _hms_to_sec(time_start) if time_start else 0
            end_sec = _hms_to_sec(time_end) if time_end else float("inf")
            ydl_opts["download_ranges"] = download_range_func(None, [(start_sec, end_sec)])
            ydl_opts["force_keyframes_at_cuts"] = True
            log(f"  时间区间: {time_start or '开头'} → {time_end or '结尾'}")
        ydl_opts, tmp_c2 = _apply_cookie(ydl_opts, cookie_path)

        log(f"▶ 开始下载: {title}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            downloaded = ydl.extract_info(video_url, download=True)
        if not _take_downloaded_file(downloaded, temp_path):
            log("❌ 下载结束但未找到视频文件")
            return None
        ok = True
        return temp_path, final_path
    except Exception as e:
        log(f"❌ 下载出错: {e}")
        log(traceback.format_exc())
        return None
    finally:
        _cleanup(tmp_c2)
        _cleanup(tmp_c)
        if not ok:
            _cleanup(temp_path)
