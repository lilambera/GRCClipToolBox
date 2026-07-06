import yt_dlp
import os
import re
import time
import random
import tempfile
import shutil
import subprocess
import sys
import traceback
import winreg
from datetime import datetime

from paths import deno_bin, ffmpeg_bin

DELAY_MIN = 1.0
DELAY_MAX = 3.0

def _get_system_proxy():
    """从 Windows 注册表读取系统代理设置，返回 http://host:port 或 None"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        )
        enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if not enable:
            return None
        server, _ = winreg.QueryValueEx(key, "ProxyServer")
        winreg.CloseKey(key)
        if not server:
            return None
        # 格式可能是 "host:port" 或 "http=host:port;https=host:port;..."
        if "=" in server:
            # 多协议格式，优先取 https，其次 http
            parts = dict(p.split("=", 1) for p in server.split(";") if "=" in p)
            addr = parts.get("https") or parts.get("http")
            if addr:
                return f"http://{addr}" if not addr.startswith("http") else addr
            return None
        else:
            return f"http://{server}" if not server.startswith("http") else server
    except (OSError, FileNotFoundError, ValueError):
        return None


def _resolve_proxy():
    """按优先级获取代理：环境变量 > 系统代理 > 默认值"""
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if proxy:
        return proxy
    sys_proxy = _get_system_proxy()
    if sys_proxy:
        return sys_proxy
    return "http://127.0.0.1:1829"

def _hms_to_sec(t):
    parts = t.strip().split(":")
    parts = [float(p) for p in parts]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0]

_DENO_PATH = deno_bin()
_FFMPEG_PATH = ffmpeg_bin()
_FFMPEG_DIR = os.path.dirname(_FFMPEG_PATH)


def _setup_ytdlp_ffmpeg():
    """CLI 会自动设置；Python API 必须手动设置，否则分段下载/合并检测不到 ffmpeg。"""
    from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor

    FFmpegPostProcessor._ffmpeg_location.set(_FFMPEG_PATH)


def _ytdlp_ffmpeg_status():
    from yt_dlp.downloader.external import FFmpegFD
    from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor

    pp = FFmpegPostProcessor()
    return pp.available, FFmpegFD.available()


def _common_ydl_opts(log, **extra):
    _setup_ytdlp_ffmpeg()
    opts = {
        "ffmpeg_location": _FFMPEG_PATH,
        "js_runtimes": {"deno": {"path": _DENO_PATH}},
    }
    opts.update(extra)
    return opts

def ensure_ejs():
    try:
        _setup_ytdlp_ffmpeg()
        with yt_dlp.YoutubeDL({
            "quiet": True,
            "no_warnings": True,
            "remote_components": ["ejs:github"],
            "js_runtimes": [f"deno:{_DENO_PATH}"],
            "ffmpeg_location": _FFMPEG_PATH,
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

    ydl_opts = _common_ydl_opts(
        log,
        quiet=True,
        no_warnings=True,
        extract_flat=True,
        logger=_YtdlpLogger(log, filter_tab=True),
    )
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
            detail_opts = _common_ydl_opts(log, quiet=True, no_warnings=True)
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
    log(f"[调试] DENO路径  = {_DENO_PATH}  存在={os.path.isfile(_DENO_PATH)}")
    log(f"[调试] FFMPEG路径= {_FFMPEG_PATH}  存在={os.path.isfile(_FFMPEG_PATH)}")
    _setup_ytdlp_ffmpeg()
    pp_ok, fd_ok = _ytdlp_ffmpeg_status()
    log(f"[调试] yt-dlp识别ffmpeg={pp_ok}, 分段下载可用={fd_ok}")
    if (time_start or time_end) and not fd_ok:
        log("❌ yt-dlp 未识别到 ffmpeg，无法使用时间段下载")
        return False, ""

    os.makedirs(output_dir, exist_ok=True)

    # 基本信息获取
    info_opts = _common_ydl_opts(
        log,
        quiet=False,
        no_warnings=False,
        skip_download=True,
        remote_components=["ejs:github"],
        logger=_YtdlpLogger(log),
    )
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

    is_nico = "nicovideo.jp" in video_url or "nico.ms" in video_url

    if is_nico:
        fmt = "bestvideo+bestaudio/best"
    else:
        fmt = "bestvideo[ext=mp4][protocol!*=m3u8]+bestaudio[ext=m4a][protocol!*=m3u8]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

    ydl_opts = _common_ydl_opts(
        log,
        format=fmt,
        outtmpl=temp_path,
        quiet=False,
        no_warnings=False,
        noprogress=False,
        progress_with_newline=True,
        remote_components=["ejs:github"],
        logger=_YtdlpLogger(log, progress_callback=progress_hook),
    )

    # 时间区间裁剪：使用 yt-dlp 原生的 download_ranges，保持最高画质
    need_trim = False
    if time_start or time_end:
        from yt_dlp.utils import download_range_func
        start_sec = _hms_to_sec(time_start) if time_start else 0
        end_sec   = _hms_to_sec(time_end) if time_end else float('inf')
        ydl_opts["download_ranges"] = download_range_func(None, [(start_sec, end_sec)])
        ydl_opts["force_keyframes_at_cuts"] = True
        need_trim = True
        # ffmpeg 下载分段时需要代理和 UA 才能连接 Google 视频服务器
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        proxy = _resolve_proxy()
        ydl_opts["external_downloader_args"] = {
            "ffmpeg_i": ["-user_agent", ua, "-http_proxy", proxy],
        }
        log(f"  时间区间: {time_start or '开头'} → {time_end or '结尾'}")

    # 全局代理设置，让 yt-dlp 本身的下载也走代理
    proxy = _resolve_proxy()
    ydl_opts["proxy"] = proxy
    log(f"  使用代理: {proxy}")

    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    ydl_opts, tmp_c2 = _apply_cookie(ydl_opts, cookie_path)

    # 下载
    try:
        log(f"▶ 开始下载: {title}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        log("  下载完成，正在检测编码…")

        # 检测视频编码
        ffprobe_path = _FFMPEG_PATH.replace("ffmpeg.exe", "ffprobe.exe")
        probe = subprocess.run(
            [ffprobe_path, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name",
             "-of", "default=noprint_wrappers=1:nokey=1", temp_path],
            capture_output=True, text=True, encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        codec = probe.stdout.strip().lower()
        log(f"  视频编码: {codec}")

        if codec not in ("h264", "avc", "avc1"):
            log(f"  编码为 {codec}，正在转换为H.264 …")
            result = subprocess.run(
                [_FFMPEG_PATH, "-y", "-i", temp_path,
                 "-c:v", "libx264", "-crf", "18", "-preset", "fast",
                 "-c:a", "aac", "-b:a", "192k",
                 "-movflags", "+faststart", final_path],
                capture_output=True, text=True, encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            log("  编码为 H.264，开始封装…")
            result = subprocess.run(
                [_FFMPEG_PATH, "-y", "-i", temp_path,
                 "-c", "copy", "-movflags", "+faststart", final_path],
                capture_output=True, text=True, encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW
            )

        if result.returncode != 0:
            log(f"❌ ffmpeg处理失败，返回码: {result.returncode}")
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
    """把 yt-dlp 内部日志转发到 log 回调，同时解析进度信息"""
    _ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')
    # 匹配多种 yt-dlp 进度格式：
    # [download]  45.2% of ~  50.00MiB at    5.00MiB/s ETA 00:05
    # [download]  45.2% of 50.00MiB at 5.00MiB/s ETA 00:05
    # [download] 100% of 50.00MiB
    _PROGRESS_RE = re.compile(
        r'\[download\]\s+([\d.]+)%'
        r'(?:\s+of\s+~?\s*([\d.]+\S+))?'
        r'(?:\s+at\s+([\d.]+\S+))?'
        r'(?:\s+ETA\s+(\S+))?'
    )

    def __init__(self, log_fn, filter_tab=False, progress_callback=None):
        self._log = log_fn
        self._filter_tab = filter_tab
        self._progress_callback = progress_callback

    def _clean(self, msg):
        """去除 ANSI 转义码，确保纯文本输出"""
        return self._ANSI_RE.sub('', msg)

    def _try_parse_progress(self, msg):
        """尝试解析 yt-dlp 输出的下载进度行并通知 GUI"""
        if not self._progress_callback:
            return False
        m = self._PROGRESS_RE.search(msg)
        if m:
            pct = m.group(1)
            size = m.group(2) or "N/A"
            speed = m.group(3) or "N/A"
            eta = m.group(4) or "N/A"
            self._progress_callback({
                "status": "downloading",
                "_percent_str": f"{pct}%",
                "_speed_str": speed,
                "_eta_str": eta,
                "_total_bytes_str": size,
            })
            # 100% 时额外发一个 finished
            try:
                if float(pct) >= 100:
                    self._progress_callback({
                        "status": "finished",
                        "_total_bytes_str": size,
                    })
            except ValueError:
                pass
            return True
        return False

    def debug(self, msg):
        msg = self._clean(msg)
        if msg.startswith("[debug]"):
            return
        if self._filter_tab and "[youtube:tab]" in msg:
            return
        # 进度行只通知 GUI，不重复写入日志（避免刷屏）
        if self._try_parse_progress(msg):
            return
        self._log(msg)

    def info(self, msg):
        msg = self._clean(msg)
        if self._filter_tab and "[youtube:tab]" in msg:
            return
        if self._try_parse_progress(msg):
            return
        self._log(msg)

    def warning(self, msg):
        msg = self._clean(msg)
        self._log(f"[警告] {msg}")

    def error(self, msg):
        msg = self._clean(msg)
        self._log(f"[错误] {msg}")