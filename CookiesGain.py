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

def get_youtube_cookies(output_path, wait_time=60):
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    chrome_path = find_chrome()
    if chrome_path is None:
        raise FileNotFoundError("未找到 Chrome，请确认已安装")
    version_main = get_chrome_version(chrome_path)
    with uc.Chrome(options=options,version_main=version_main, browser_executable_path=chrome_path) as driver:
        driver.get("https://accounts.google.com/ServiceLogin?service=youtube")
        time.sleep(wait_time)
        raw_cookies = driver.get_cookies()

    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in raw_cookies:
            domain = c.get('domain', '.youtube.com')
            flag = "TRUE" if domain.startswith('.') else "FALSE"
            path = c.get('path', '/')
            secure = "TRUE" if c.get('secure', False) else "FALSE"
            expiry = str(int(c.get('expiry', 0)))
            name = c['name']
            value = c['value']
            f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")

    return output_path