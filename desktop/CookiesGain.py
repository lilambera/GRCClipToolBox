import undetected_chromedriver as uc
import time
import os
import tkinter as tk
from tkinter import filedialog
import winreg

"""
功能：通过调用chrome让用户手动通过验证登录的方式登录youtube，从而减少被反爬虫的概率，获取完整cookies

"""
def get_chrome_version(chrome_path):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Google\Chrome\BLBeacon")
        version, _ = winreg.QueryValueEx(key, "version")
        return int(version.split(".")[0])
    except Exception:
        # 注册表读不到就从文件版本读
        import subprocess
        result = subprocess.run(
            f'powershell (Get-Item "{chrome_path}").VersionInfo.ProductVersion',
            capture_output=True, text=True, shell=True
        )
        return int(result.stdout.strip().split(".")[0])

def find_chrome():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path

    # 自动搜索失败，弹窗让用户手动选
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    path = filedialog.askopenfilename(
        title="未找到 Chrome，请手动选择 chrome.exe",
        filetypes=[("Chrome", "chrome.exe"), ("所有文件", "*.*")]
    )
    root.destroy()
    return path if path else None

def _youtube_logged_in(cookies):
    wanted = {"LOGIN_INFO", "SID", "__Secure-1PSID", "SAPISID", "__Secure-3PSID"}
    return any(c.get("name") in wanted and c.get("value") for c in cookies)


def _write_youtube_cookies(output_path, cookies):
    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            domain = c.get("domain", ".youtube.com")
            flag = "TRUE" if domain.startswith(".") else "FALSE"
            path = c.get("path", "/")
            secure = "TRUE" if c.get("secure", False) else "FALSE"
            expiry = str(int(c.get("expiry", 0)))
            name = c["name"]
            value = c["value"]
            f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")


def get_youtube_cookies(output_path, wait_time=60):
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    chrome_path = find_chrome()
    if chrome_path is None:
        raise FileNotFoundError("未找到 Chrome，请确认已安装")
    version_main = get_chrome_version(chrome_path)
    saved = False
    collected = {}
    with uc.Chrome(options=options, version_main=version_main, browser_executable_path=chrome_path) as driver:
        driver.get("https://accounts.google.com/ServiceLogin?service=youtube")
        deadline = time.time() + wait_time
        while time.time() < deadline:
            try:
                cookies = driver.get_cookies()
                on_youtube = "youtube.com" in (driver.current_url or "")
            except Exception as e:
                text = str(e).lower()
                if "no such window" in text or "invalid session" in text:
                    raise RuntimeError("登录窗口已关闭，未完成登录") from e
                time.sleep(1)
                continue
            for c in cookies:
                collected[(c.get("domain"), c.get("name"))] = c
            if _youtube_logged_in(cookies) and not on_youtube:
                driver.get("https://www.youtube.com/")
                time.sleep(1)
                continue
            if _youtube_logged_in(collected.values()) and on_youtube:
                _write_youtube_cookies(output_path, list(collected.values()))
                saved = True
                break
            time.sleep(1)
    if not saved:
        raise RuntimeError("未在时限内完成 YouTube 登录")
    return output_path

def _find_edge():
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\Application\msedge.exe"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _edge_profile_dir():
    root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(root, "videofloder", "edge_bilibili_profile")


def _cdp_call(ws, msg_id, method, params=None):
    import json

    message = {"id": msg_id, "method": method}
    if params:
        message["params"] = params
    ws.send(json.dumps(message))
    while True:
        reply = json.loads(ws.recv())
        if reply.get("id") != msg_id:
            continue
        if "error" in reply:
            raise RuntimeError(reply["error"].get("message") or "读取 Edge Cookie 失败")
        return reply.get("result") or {}


def _cdp_cookies(port):
    import json
    import urllib.request
    import websocket

    # 调试端口在本机，不走系统代理。
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(f"http://127.0.0.1:{port}/json/list", timeout=2) as resp:
        targets = json.load(resp)
    # 与 “Get cookies.txt LOCALLY” 一样，只取当前 B 站页面会带上的 Cookie。
    pages = [
        t for t in targets
        if t.get("type") == "page"
        and t.get("webSocketDebuggerUrl")
        and "bilibili.com" in (t.get("url") or "")
    ]
    if not pages:
        raise ConnectionError("Edge 页面尚未就绪")
    page = pages[0]
    ws = websocket.create_connection(
        page["webSocketDebuggerUrl"],
        timeout=5,
        http_no_proxy=["127.0.0.1", "localhost"],
    )
    try:
        result = _cdp_call(ws, 1, "Network.getCookies", {"urls": [page["url"]]})
        return result.get("cookies") or []
    finally:
        ws.close()


def _close_process_tree(proc):
    import subprocess
    if proc is None or proc.poll() is not None:
        return
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _stop_profile_edge(profile_dir):
    import subprocess
    marker = profile_dir.replace("'", "''")
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name = 'msedge.exe'\" | "
        f"Where-Object {{ $_.CommandLine -like '*{marker}*' }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _write_bilibili_cookies(output_path, cookies):
    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    logged_in = False
    lines = [
        "# Netscape HTTP Cookie File\n",
        "# https://curl.haxx.se/rfc/cookie_spec.html\n",
        "# This is a generated file! Do not edit.\n",
        "\n",
    ]
    for c in cookies:
        domain = c.get("domain") or ""
        if "bilibili.com" not in domain:
            continue
        name = c.get("name") or ""
        value = c.get("value") or ""
        if name == "SESSDATA" and value:
            logged_in = True
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path") or "/"
        secure = "TRUE" if c.get("secure") else "FALSE"
        expiry = c.get("expires")
        try:
            expiry = str(int(expiry)) if expiry and float(expiry) > 0 else "0"
        except (TypeError, ValueError):
            expiry = "0"
        host = f"#HttpOnly_{domain}" if c.get("httpOnly") else domain
        lines.append(f"{host}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
    if not logged_in:
        return False
    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return True


def get_bilibili_cookies(output_path, wait_time=60):
    """新开一个独立的 Edge 窗口让用户登录 B 站，再从该窗口读取 Cookie。"""
    import socket
    import subprocess

    edge = _find_edge()
    if edge is None:
        raise FileNotFoundError("未找到 Edge，请确认已安装")

    profile_dir = _edge_profile_dir()
    os.makedirs(profile_dir, exist_ok=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    proc = subprocess.Popen([
        edge,
        f"--user-data-dir={profile_dir}",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-proxy-server",
        "--new-window",
        "https://passport.bilibili.com/login",
    ])
    try:
        deadline = time.time() + wait_time
        last_error = None
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError("Edge 窗口已关闭，未完成登录")
            try:
                cookies = _cdp_cookies(port)
            except RuntimeError:
                raise
            except Exception as e:
                last_error = e
                time.sleep(1)
                continue
            if _write_bilibili_cookies(output_path, cookies):
                _close_process_tree(proc)
                return output_path
            time.sleep(1)
        if last_error is not None:
            raise RuntimeError("未能连上新打开的 Edge 窗口，请重试") from last_error
        raise RuntimeError("未在时限内完成 B 站登录")
    finally:
        _stop_profile_edge(profile_dir)
        if proc.poll() is None:
            proc.terminate()