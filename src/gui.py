import os
import threading
import json
import tkinter as tk
import tempfile
from datetime import datetime
from tkinter import ttk, filedialog, messagebox
import webbrowser

from addSubtitle import burn_subtitles
from AssToTxt import extract_ass_text
from YTTxtReformat import reformat_text
from TimeStamps import ass_timestamps
from YTdownload import get_channel_videos, download_video
from CookiesGain import get_youtube_cookies
from whisperLocal import whisper_trans

CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except:
        pass

def addSubtitle_gui(parent):
    var_input    = tk.StringVar()
    var_sub      = tk.StringVar()
    var_output   = tk.StringVar()
    config = load_config()
    default_workdir = config.get("work_dir", os.path.join(tempfile.gettempdir(), "subtitle_workdir"))
    var_workdir = tk.StringVar(value=default_workdir)
    var_crf      = tk.IntVar(value=23)
    var_abitrate = tk.StringVar(value="192k")

    pad = dict(padx=12, pady=5)

    #文件选择
    frame_files = ttk.LabelFrame(parent, text="文件选择", padding=10)
    frame_files.grid(row=0, column=0, sticky="ew", **pad)

    def make_row(parent, row, label, var, browse_fn):
        ttk.Label(parent, text=label, width=8, anchor="e").grid(
            row=row, column=0, sticky="e", padx=(0, 6))
        ttk.Entry(parent, textvariable=var, width=58).grid(
            row=row, column=1, sticky="ew")
        ttk.Button(parent, text="浏览…", command=browse_fn, width=7).grid(
            row=row, column=2, padx=(6, 0))

    def browse_input():
        path = filedialog.askopenfilename(
            title="选择输入视频",
            filetypes=[
                ("视频文件", "*.mp4 *.mkv *.avi *.mov *.flv *.wmv")
            ]
        )
        if path:
            var_input.set(path)

            #输出同步
            if not var_output.get():
                base, ext = os.path.splitext(path)
                var_output.set(base + "_STadded" + ext)

    def browse_sub():
        path = filedialog.askopenfilename(
            title="选择字幕文件",
            filetypes=[
                ("ASS/SSA 字幕", "*.ass *.ssa"),
                ("SRT 字幕",     "*.srt")
            ]
        )
        if path:
            var_sub.set(path)

    def browse_output():
        path = filedialog.asksaveasfilename(
            title="输出文件保存位置",
            defaultextension=".mp4",
            filetypes=[("MP4 文件", "*.mp4"), ("所有文件", "*.*")]
        )
        if path:
            var_output.set(path)

    def browse_workdir():
        path = filedialog.askdirectory(title="选择工作目录")
        if path:
            var_workdir.set(path)
            config["work_dir"] = path
            save_config(config)

    make_row(frame_files, 0, "输入视频", var_input,   browse_input)
    make_row(frame_files, 1, "字幕文件", var_sub,     browse_sub)
    make_row(frame_files, 2, "输出路径", var_output,  browse_output)
    make_row(frame_files, 3, "工作目录", var_workdir, browse_workdir)
    ttk.Label(frame_files, text="工作目录用于临时存放文件，必须为纯英文路径，所占空间大于视频本身",
              foreground="gray").grid(row=4, column=1, sticky="w", pady=(0,4))

    #编码参数
    frame_param = ttk.LabelFrame(parent, text="编码参数", padding=10)
    frame_param.grid(row=1, column=0, sticky="ew", **pad)

    ttk.Label(frame_param, text="CRF:").grid(
        row=0, column=0, sticky="w")
    ttk.Spinbox(frame_param, from_=0, to=51, textvariable=var_crf,
                width=6).grid(row=0, column=1, sticky="w", padx=8)

    ttk.Label(frame_param, text="音频码率:").grid(
        row=0, column=2, sticky="w", padx=(20, 0))
    ttk.Combobox(frame_param, textvariable=var_abitrate,
                 values=["128k", "192k", "256k", "320k"],
                 width=7, state="readonly").grid(
        row=0, column=3, sticky="w", padx=8)

    #日志输出
    frame_log = ttk.LabelFrame(parent, text="运行日志", padding=10)
    frame_log.grid(row=2, column=0, sticky="nsew", **pad)

    log_text = tk.Text(
        frame_log, width=82, height=20, wrap="word",
        bg="#1e1e1e", fg="#d4d4d4",
        font=("Consolas", 9), state="disabled"
    )
    scrollbar = ttk.Scrollbar(frame_log, orient="vertical", command=log_text.yview)
    log_text.configure(yscrollcommand=scrollbar.set)
    log_text.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")

    def append_log(msg):
        parent.after(0, _append_log, msg)

    def _append_log(msg):
        log_text.configure(state="normal")
        log_text.insert("end", msg + "\n")
        log_text.see("end")
        log_text.configure(state="disabled")

    #烤录执行方式
    btn = ttk.Button(parent, text="▶  开始烧录")
    btn.grid(row=3, column=0, pady=12)

    def start():
        inp = var_input.get().strip()
        sub = var_sub.get().strip()
        out = var_output.get().strip()

        if not inp or not sub or not out:
            messagebox.showwarning("缺少参数", "请填写输入视频、字幕文件和输出路径！")
            return
        if not os.path.isfile(inp):
            messagebox.showerror("文件不存在", f"找不到输入视频：\n{inp}")
            return
        if not os.path.isfile(sub):
            messagebox.showerror("文件不存在", f"找不到字幕文件：\n{sub}")
            return

        btn.configure(state="disabled", text="处理中…")

        def task():
            success = burn_subtitles(
                input_video=inp,
                subtitle_file=sub,
                output_video=out,
                work_dir=var_workdir.get().strip(),
                crf=var_crf.get(),
                audio_bitrate=var_abitrate.get(),
                log_callback=append_log
            )
            parent.after(0, on_done, success, out)

        threading.Thread(target=task, daemon=True).start()

    def on_done(success, out_path):
        btn.configure(state="normal", text="▶  开始烧录")
        if success:
            if messagebox.askyesno("完成", f"烧录完成！\n\n{out_path}\n\n是否打开所在文件夹？"):
                os.startfile(os.path.dirname(os.path.abspath(out_path)))
        else:
            messagebox.showerror("失败", "烧录失败，请查看日志。")

    btn.configure(command=start)

def assExtract_gui(parent):
    parent.pack(fill="x", padx=12, pady=5)
    parent.columnconfigure(1, weight=1)
    var_input  = tk.StringVar()
    var_output = tk.StringVar()

    def make_row(row, label, var, browse_fn):
        ttk.Label(parent, text=label, width=8, anchor="e").grid(
            row=row, column=0, sticky="e", padx=(0, 6))
        ttk.Entry(parent, textvariable=var, width=52).grid(
            row=row, column=1, sticky="ew")
        ttk.Button(parent, text="浏览…", command=browse_fn, width=7).grid(
            row=row, column=2, padx=(6, 0))

    def browse_input():
        path = filedialog.askopenfilename(
            title="选择 ASS 字幕文件",
            filetypes=[("ASS/SSA 字幕", "*.ass *.ssa"), ("所有文件", "*.*")]
        )
        if path:
            var_input.set(path)
            if not var_output.get():
                base, _ = os.path.splitext(path)
                var_output.set(base + "_text.txt")

    def browse_output():
        path = filedialog.asksaveasfilename(
            title="输出文件保存位置",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if path:
            var_output.set(path)

    make_row(0, "ASS 文件", var_input,  browse_input)
    make_row(1, "输出路径", var_output, browse_output)

    btn = ttk.Button(parent, text="▶  开始提取")
    btn.grid(row=2, column=0, columnspan=3, pady=(10, 2))

    def start():
        inp = var_input.get().strip()
        out = var_output.get().strip() or None

        if not inp or not os.path.isfile(inp):
            messagebox.showerror("文件不存在", "请选择有效的ass文件")
            return

        btn.configure(state="disabled", text="处理中…")

        def on_done(out_path, count):
            btn.configure(state="normal", text="▶  开始提取")
            if messagebox.askyesno("完成", f"提取完成，共 {count} 行\n\n{out_path}\n\n是否打开所在文件夹？"):
                os.startfile(os.path.dirname(os.path.abspath(out_path)))

        def task():
            try:
                out_path, count = extract_ass_text(inp, out)
                parent.after(0, on_done, out_path, count)
            except Exception as e:
                parent.after(0, lambda: btn.configure(state="normal", text="▶  开始提取"))
                parent.after(0, lambda: messagebox.showerror("错误", f"提取失败：{e}"))
        threading.Thread(target=task, daemon=True).start()

    btn.configure(command=start)

def txtTransform_gui(parent):
    var_input  = tk.StringVar()
    var_output = tk.StringVar()

    parent.pack(fill="x", padx=12, pady=5)
    parent.columnconfigure(1, weight=1)

    def make_row(row, label, var, browse_fn):
        ttk.Label(parent, text=label, width=8, anchor="e").grid(
            row=row, column=0, sticky="e", padx=(0, 6))
        ttk.Entry(parent, textvariable=var, width=52).grid(
            row=row, column=1, sticky="ew")
        ttk.Button(parent, text="浏览…", command=browse_fn, width=7).grid(
            row=row, column=2, padx=(6, 0))

    def browse_input():
        path = filedialog.askopenfilename(
            title="选择文本文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if path:
            var_input.set(path)

    def browse_output():
        path = filedialog.asksaveasfilename(
            title="输出文件保存位置",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if path:
            var_output.set(path)

    make_row(0, "输入文件", var_input,  browse_input)
    make_row(1, "输出路径", var_output, browse_output)
    ttk.Label(parent, foreground="gray").grid(row=2, column=1, sticky="w", pady=(0, 4))

    btn = ttk.Button(parent, text="▶  开始转换")
    btn.grid(row=3, column=0, columnspan=3, pady=(6, 2))

    def start():
        inp = var_input.get().strip()
        out = var_output.get().strip() or None

        if not inp:
            messagebox.showwarning("缺少参数", "请选择输入文件！")
            return
        if not os.path.isfile(inp):
            messagebox.showerror("文件不存在", f"找不到文件：\n{inp}")
            return

        btn.configure(state="disabled", text="处理中…")

        def on_done(out_path, count):
            btn.configure(state="normal", text="▶  开始转换")
            if messagebox.askyesno("完成", f"转换完成，共 {count} 行\n\n{out_path}\n\n是否打开所在文件夹？"):
                os.startfile(os.path.dirname(os.path.abspath(out_path)))

        def task():
            out_path, count = reformat_text(inp, out)
            parent.after(0, on_done, out_path, count)

        threading.Thread(target=task, daemon=True).start()

    btn.configure(command=start)

def timestamps_gui(parent):
    var_input       = tk.StringVar()
    var_start_after = tk.StringVar()

    parent.pack(fill="x", padx=12, pady=5)
    parent.columnconfigure(1, weight=1)

    # 文件选择行
    ttk.Label(parent, text="ASS 文件", width=10, anchor="e").grid(
        row=0, column=0, sticky="e", padx=(0, 6))
    ttk.Entry(parent, textvariable=var_input, width=50).grid(
        row=0, column=1, sticky="ew")
    ttk.Button(parent, text="浏览…", width=7,
               command=lambda: var_input.set(
                   filedialog.askopenfilename(
                       title="选择 ASS 字幕文件",
                       filetypes=[("ASS/SSA 字幕", "*.ass *.ssa"), ("所有文件", "*.*")]
                   ) or var_input.get()
               )).grid(row=0, column=2, padx=(6, 0))

    # 起始过滤行
    ttk.Label(parent, text="起始过滤", width=10, anchor="e").grid(
        row=1, column=0, sticky="e", padx=(0, 6))
    ttk.Entry(parent, textvariable=var_start_after, width=16).grid(
        row=1, column=1, sticky="w")
    ttk.Label(parent, text="格式：00:01:30.0，留空则提取全部",
              foreground="gray").grid(row=2, column=1, sticky="w", pady=(0, 4))

    btn = ttk.Button(parent, text="▶  开始提取")
    btn.grid(row=3, column=0, columnspan=3, pady=(4, 6))

    # 结果文本框 + 复制按钮
    result_frame = ttk.Frame(parent)
    result_frame.grid(row=4, column=0, columnspan=3, sticky="ew")
    result_frame.columnconfigure(0, weight=1)

    result_text = tk.Text(result_frame, height=4, wrap="word",bg="#1e1e1e", fg="#d4d4d4",
                          font=("Consolas", 9), state="disabled")
    result_text.grid(row=0, column=0, sticky="ew")

    def copy_result():
        content = result_text.get("1.0", "end").strip()
        if content:
            parent.clipboard_clear()
            parent.clipboard_append(content)

    ttk.Button(result_frame, text="复制", width=6,
               command=copy_result).grid(row=0, column=1, padx=(6, 0), sticky="n")

    def start():
        inp = var_input.get().strip()
        start_after = var_start_after.get().strip() or None

        if not inp:
            messagebox.showwarning("缺少参数", "请选择 ASS 字幕文件！")
            return
        if not os.path.isfile(inp):
            messagebox.showerror("文件不存在", f"找不到字幕文件：\n{inp}")
            return

        btn.configure(state="disabled", text="处理中…")

        def on_done(result, count):
            btn.configure(state="normal", text="▶  开始提取")
            result_text.configure(state="normal")
            result_text.delete("1.0", "end")
            result_text.insert("end", result)
            result_text.configure(state="disabled")

        def task():
            result, count = ass_timestamps(inp, start_after)
            parent.after(0, on_done, result, count)

        threading.Thread(target=task, daemon=True).start()

    btn.configure(command=start)

def ytDownload_gui(parent):
    config = load_config()
    pad = dict(padx=12, pady=5)

    parent.columnconfigure(0, weight=1)

    #下载模式
    frame_mode = ttk.LabelFrame(parent, text="下载模式", padding=10)
    frame_mode.grid(row=0, column=0, sticky="ew", **pad)
    var_mode = tk.StringVar(value="single")

    def on_mode_change():
        is_single = var_mode.get() == "single"
        for w in (ent_d_start, ent_d_end):
            w.configure(state="disabled" if is_single else "normal")

    ttk.Radiobutton(frame_mode, text="单个视频",
                    variable=var_mode, value="single",
                    command=on_mode_change).grid(row=0, column=0, sticky="w", padx=(0, 30))
    ttk.Radiobutton(frame_mode, text="批量频道（注意要用对应视频/直播列表的URL）",
                    variable=var_mode, value="channel",
                    command=on_mode_change).grid(row=0, column=1, sticky="w",padx=(50, 0))

    # URL
    frame_url = ttk.LabelFrame(parent, text="URL", padding=10)
    frame_url.grid(row=1, column=0, sticky="ew", **pad)
    frame_url.columnconfigure(1, weight=1)

    var_url = tk.StringVar()
    ttk.Label(frame_url, text="URL", width=14).grid(
        row=0, column=0, sticky="e")
    ttk.Entry(frame_url, textvariable=var_url, width=72).grid(
        row=0, column=1, sticky="w")

    #时间区间切片
    frame_time = ttk.LabelFrame(parent, text="视频时间区间（留空默认完整视频）", padding=10)
    frame_time.grid(row=2, column=0, sticky="ew", **pad)

    var_t_start = tk.StringVar()
    var_t_end   = tk.StringVar()

    ttk.Label(frame_time, text="开始时间", width=10, anchor="e").grid(
        row=0, column=0, sticky="e", padx=(0, 6))
    ent_t_start = ttk.Entry(frame_time, textvariable=var_t_start, width=12)
    ent_t_start.grid(row=0, column=1, sticky="w")
    ttk.Label(frame_time, text="格式：HH:MM:SS", foreground="gray").grid(
        row=0, column=2, sticky="w", padx=(6, 24))

    ttk.Label(frame_time, text="结束时间", width=10, anchor="e").grid(
        row=0, column=3, sticky="e", padx=(0, 6))
    ent_t_end = ttk.Entry(frame_time, textvariable=var_t_end, width=12)
    ent_t_end.grid(row=0, column=4, sticky="w")
    ttk.Label(frame_time, text="格式：HH:MM:SS", foreground="gray").grid(
        row=0, column=5, sticky="w", padx=(6, 0))

    #频道日期区间
    frame_date = ttk.LabelFrame(parent, text="频道日期区间（批量模式专用）", padding=10)
    frame_date.grid(row=3, column=0, sticky="ew", **pad)

    var_d_start = tk.StringVar()
    var_d_end   = tk.StringVar()

    ttk.Label(frame_date, text="开始日期", width=10, anchor="e").grid(
        row=0, column=0, sticky="e", padx=(0, 6))
    ent_d_start = ttk.Entry(frame_date, textvariable=var_d_start, width=12, state="disabled")
    ent_d_start.grid(row=0, column=1, sticky="w")
    ttk.Label(frame_date, text="格式：YYYY-MM-DD", foreground="gray").grid(
        row=0, column=2, sticky="w", padx=(6, 24))

    ttk.Label(frame_date, text="结束日期", width=10, anchor="e").grid(
        row=0, column=3, sticky="e", padx=(0, 6))
    ent_d_end = ttk.Entry(frame_date, textvariable=var_d_end, width=12, state="disabled")
    ent_d_end.grid(row=0, column=4, sticky="w")
    ttk.Label(frame_date, text="留空默认当天", foreground="gray").grid(
        row=0, column=5, sticky="w", padx=(6, 0))

    #保存位置
    frame_path = ttk.LabelFrame(parent, text="保存位置", padding=10)
    frame_path.grid(row=4, column=0, sticky="ew", **pad)
    frame_path.columnconfigure(1, weight=1)

    var_save_dir = tk.StringVar(value=config.get("yt_save_dir", ""))

    def browse_save():
        path = filedialog.askdirectory(title="选择保存目录")
        if path:
            var_save_dir.set(path)
            config["yt_save_dir"] = path
            save_config(config)

    ttk.Label(frame_path, text="保存目录", width=8, anchor="e").grid(
        row=0, column=0, sticky="e", padx=(0, 6))
    ttk.Entry(frame_path, textvariable=var_save_dir, width=58).grid(
        row=0, column=1, sticky="ew")
    ttk.Button(frame_path, text="浏览…", command=browse_save, width=7).grid(
        row=0, column=2, padx=(6, 0))

    #Cookie
    frame_cookie = ttk.LabelFrame(parent, text="Cookie", padding=10)
    frame_cookie.grid(row=5, column=0, sticky="ew", **pad)
    frame_cookie.columnconfigure(1, weight=1)

    var_use_cookie  = tk.BooleanVar(value=bool(config.get("yt_cookie_path", "")))
    var_cookie_path = tk.StringVar(value=config.get("yt_cookie_path", ""))

    def on_cookie_toggle():
        ent_cookie.configure(state="normal" if var_use_cookie.get() else "disabled")
        btn_cookie.configure(state="normal" if var_use_cookie.get() else "disabled")
        if not var_use_cookie.get():
            var_cookie_path.set("")
            config["yt_cookie_path"] = ""
            save_config(config)

    def browse_cookie():
        path = filedialog.askopenfilename(
            title="选择 Cookie 文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )

        if path:
            var_cookie_path.set(path)
            config["yt_cookie_path"] = path
            save_config(config)

    ttk.Checkbutton(frame_cookie, text="使用 Cookie 文件",
                    variable=var_use_cookie,
                    command=on_cookie_toggle).grid(
        row=0, column=0, sticky="w", padx=(0, 10))
    ent_cookie = ttk.Entry(frame_cookie, textvariable=var_cookie_path, width=52,
                           state="normal" if var_use_cookie.get() else "disabled")
    ent_cookie.grid(row=0, column=1, sticky="ew")
    btn_cookie = ttk.Button(frame_cookie, text="浏览…", command=browse_cookie, width=7,
                            state="normal" if var_use_cookie.get() else "disabled")
    btn_cookie.grid(row=0, column=2, padx=(6, 0))

    #运行日志
    frame_log = ttk.LabelFrame(parent, text="运行日志", padding=10)
    frame_log.grid(row=6, column=0, sticky="nsew", **pad)
    frame_log.columnconfigure(0, weight=1)
    frame_log.rowconfigure(0, weight=1)

    log_text = tk.Text(
        frame_log, width=82, height=6, wrap="word",
        bg="#1e1e1e", fg="#d4d4d4",
        font=("Consolas", 9), state="disabled"
    )
    scrollbar = ttk.Scrollbar(frame_log, orient="vertical", command=log_text.yview)
    log_text.configure(yscrollcommand=scrollbar.set)
    log_text.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")

    # 进度覆盖行
    var_progress = tk.StringVar(value="")
    ttk.Label(frame_log, textvariable=var_progress,
              foreground="#4ec9b0", font=("Consolas", 9)).grid(
        row=1, column=0, sticky="w", pady=(2, 0))

    def append_log(msg):
        parent.after(0, _append_log, msg)

    def _append_log(msg):
        log_text.configure(state="normal")
        log_text.insert("end", msg + "\n")
        log_text.see("end")
        log_text.configure(state="disabled")

    def make_progress_hook():
        def hook(d):
            if d["status"] == "downloading":
                pct   = d.get("_percent_str", "N/A")
                speed = d.get("_speed_str",   "N/A")
                eta   = d.get("_eta_str",     "N/A")
                parent.after(0, var_progress.set,
                             f"下载中: {pct}  速度: {speed}  预计剩余: {eta}")
        return hook

    #开始按钮
    btn = ttk.Button(parent, text="▶  开始下载")
    btn.grid(row=7, column=0, pady=(4,4))

    def start():
        url         = var_url.get().strip()
        save_dir    = var_save_dir.get().strip()
        cookie_path = var_cookie_path.get().strip() if var_use_cookie.get() else None
        t_start     = var_t_start.get().strip() or None
        t_end       = var_t_end.get().strip()   or None

        if not url:
            messagebox.showwarning("缺少参数", "请粘贴视频或频道 URL！")
            return
        if not save_dir:
            messagebox.showwarning("缺少参数", "请选择保存目录！")
            return

        btn.configure(state="disabled", text="处理中…")
        var_progress.set("")

        if var_mode.get() == "single":
            def task():
                success, out_path = download_video(
                    video_url=url,
                    output_dir=save_dir,
                    time_start=t_start,
                    time_end=t_end,
                    cookie_path=cookie_path,
                    log=append_log,
                    progress_hook=make_progress_hook()
                )
                parent.after(0, on_done_single, success, out_path)

            threading.Thread(target=task, daemon=True).start()

        else:  # channel
            d_start_str = var_d_start.get().strip()
            d_end_str   = var_d_end.get().strip()

            if not d_start_str:
                messagebox.showwarning("缺少参数", "批量模式请填写开始日期！")
                btn.configure(state="normal", text="▶  开始下载")
                return

            try:
                start_date = datetime.strptime(d_start_str, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("日期格式错误", "开始日期格式应为 YYYY-MM-DD")
                btn.configure(state="normal", text="▶  开始下载")
                return

            try:
                end_date = datetime.strptime(d_end_str, "%Y-%m-%d") if d_end_str else None
            except ValueError:
                messagebox.showerror("日期格式错误", "结束日期格式应为 YYYY-MM-DD")
                btn.configure(state="normal", text="▶  开始下载")
                return

            def task():
                append_log(f"▶ 开始抓取频道: {url}")
                videos = get_channel_videos(url, start_date, end_date, log=append_log)

                if not videos:
                    append_log("未找到符合条件的视频。")
                    parent.after(0, btn.configure,
                                 {"state": "normal", "text": "▶  开始下载"})
                    return

                append_log(f"共找到 {len(videos)} 个视频，开始依次下载…")
                ok = 0
                for i, v in enumerate(videos, 1):
                    append_log(f"\n[{i}/{len(videos)}] {v['title']}")
                    success, _ = download_video(
                        video_url=v["url"],
                        output_dir=save_dir,
                        time_start=t_start,
                        time_end=t_end,
                        cookie_path=cookie_path,
                        log=append_log,
                        progress_hook=make_progress_hook()
                    )
                    if success:
                        ok += 1

                append_log(f"\n✅ 全部完成：{ok}/{len(videos)} 个视频下载成功。")
                parent.after(0, on_done_channel, ok, len(videos), save_dir)

            threading.Thread(target=task, daemon=True).start()

    def on_done_single(success, out_path):
        var_progress.set("")
        btn.configure(state="normal", text="▶  开始下载")
        if success:
            if messagebox.askyesno("完成", f"下载完成！\n\n{out_path}\n\n是否打开所在文件夹？"):
                os.startfile(os.path.dirname(os.path.abspath(out_path)))
        else:
            messagebox.showerror("失败", "下载失败，请查看日志。")

    def on_done_channel(ok, total, save_dir):
        var_progress.set("")
        btn.configure(state="normal", text="▶  开始下载")
        if messagebox.askyesno("完成", f"批量下载完成！\n成功 {ok}/{total} 个\n\n是否打开保存目录？"):
            os.startfile(os.path.abspath(save_dir))

    btn.configure(command=start)

def cookiesGain_gui(parent):
    var_output = tk.StringVar(value="youtube_cookies.txt")

    parent.pack(fill="x", padx=12, pady=5)
    parent.columnconfigure(1, weight=1)

    ttk.Label(parent, text="输出路径", width=8, anchor="e").grid(row=0, column=0, sticky="e", padx=(0, 6))
    ttk.Entry(parent, textvariable=var_output, width=52).grid(row=0, column=1, sticky="ew")
    ttk.Button(parent, text="浏览…", width=7, command=lambda: var_output.set(
        filedialog.asksaveasfilename(title="保存 Cookie 文件", defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]) or var_output.get()
    )).grid(row=0, column=2, padx=(6, 0))
    ttk.Label(parent, text="请在窗口弹出60s内完成登录",foreground="gray").grid(row=1, column=1, sticky="w")

    btn = ttk.Button(parent, text="▶  获取 Cookie")
    btn.grid(row=2, column=0, columnspan=3, pady=(4, 2))

    def start():
        out = var_output.get().strip()
        if not out:
            messagebox.showwarning("缺少参数", "请填写输出路径！")
            return
        btn.configure(state="disabled", text="处理中…")

        def task():
            out_path = get_youtube_cookies(out)
            parent.after(0, on_done, out_path)

        def on_done(out_path):
            btn.configure(state="normal", text="▶  获取 Cookie")
            if messagebox.askyesno("完成", f"Cookie 已保存！\n\n{out_path}\n\n是否打开所在文件夹？"):
                os.startfile(os.path.dirname(os.path.abspath(out_path)))

        threading.Thread(target=task, daemon=True).start()

    btn.configure(command=start)

def whisper_gui(parent):
    config = load_config()

    parent.columnconfigure(0, weight=1)
    pad = dict(padx=12, pady=5)

    #模型选择
    model_select = ttk.LabelFrame(parent, text="whisper模型", padding=10)
    model_select.grid(row=0, column=0, sticky="ew", **pad)
    model_select.columnconfigure(1, weight=1)

    var_model_path = tk.StringVar(value=config.get("whisper_model", ""))

    def make_row(parent, row, label, var, browse_fn):
        ttk.Label(parent, text=label, width=10, anchor="e").grid(
            row=row, column=0, sticky="e", padx=(0, 6))
        ttk.Entry(parent, textvariable=var, width=62).grid(
            row=row, column=1, sticky="ew")
        ttk.Button(parent, text="浏览…", command=browse_fn, width=7).grid(
            row=row, column=2, padx=(6, 0))

    def browse_model():
        path = filedialog.askdirectory(title="选择模型")
        if path:
            var_model_path.set(path)
            config["whisper_model"] = path
            save_config(config)

    make_row(model_select, 0, "模型地址", var_model_path, browse_model)
    ttk.Label(model_select, text="请选择bin文件所在的地址",
              foreground="gray").grid(row=1, column=1, sticky="w", pady=(0,4))
    ttk.Label(model_select, text="模型下载", width=10, anchor="e").grid(
        row=2, column=0, sticky="e", padx=(0, 6))
    link = tk.Label(model_select, text="faster-whisper模型", fg="#1a73e8",
                    cursor="hand2", font=("微软雅黑", 9, "underline"))
    link.grid(row=2, column=1, sticky="w")
    link.bind("<Button-1>", lambda e: webbrowser.open("https://huggingface.co/Systran"))

    #输入文件
    frame_input = ttk.LabelFrame(parent, text="输入文件", padding=10)
    frame_input.grid(row=1, column=0, sticky="ew", **pad)
    frame_input.columnconfigure(1, weight=1)

    var_audio_path = tk.StringVar()
    var_output_dir = tk.StringVar()

    def make_row2(parent, row, label, var, browse_fn):
        ttk.Label(parent, text=label, width=10, anchor="e").grid(
            row=row, column=0, sticky="e", padx=(0, 6))
        ttk.Entry(parent, textvariable=var, width=62).grid(
            row=row, column=1, sticky="ew")
        ttk.Button(parent, text="浏览…", command=browse_fn, width=7).grid(
            row=row, column=2, padx=(6, 0))

    def browse_audio():
        path = filedialog.askopenfilename(
            title="选择音频/视频文件",
            filetypes=[
                ("音频/视频文件", "*.mp3 *.wav *.m4a *.flac *.ogg *.mp4 *.mkv *.mov *.avi"),
                ("所有文件", "*.*")
            ]
        )
        if path:
            var_audio_path.set(path)
            if not var_output_dir.get():
                var_output_dir.set(os.path.dirname(os.path.abspath(path)))

    def browse_output_dir():
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            var_output_dir.set(path)

    make_row2(frame_input, 0, "音频/视频", var_audio_path, browse_audio)
    make_row2(frame_input, 1, "输出目录",  var_output_dir, browse_output_dir)

    #转录参数
    frame_param = ttk.LabelFrame(parent, text="转录参数", padding=10)
    frame_param.grid(row=2, column=0, sticky="ew", **pad)


    ttk.Label(frame_param, text="引擎:").grid(row=0, column=0, sticky="e", padx=(0, 4))
    var_engine = tk.StringVar(value=config.get("whisper_engine", "auto"))
    ttk.Combobox(
        frame_param, textvariable=var_engine,
        values=["cpu", "cuda", "auto"],
        width=6, state="readonly"
    ).grid(row=0, column=1, sticky="w", padx=(0, 20))

    ttk.Label(frame_param, text="线程数:").grid(row=0, column=2, sticky="e", padx=(0, 4))
    var_threads = tk.IntVar(value=config.get("whisper_threads", 4))
    ttk.Spinbox(frame_param, from_=1, to=32, textvariable=var_threads, width=5).grid(
        row=0, column=3, sticky="w", padx=(0, 20))

    ttk.Label(frame_param, text="并发数:").grid(row=0, column=4, sticky="e", padx=(0, 4))
    var_workers = tk.IntVar(value=config.get("whisper_workers", 1))
    ttk.Spinbox(frame_param, from_=1, to=16, textvariable=var_workers, width=5).grid(
        row=0, column=5, sticky="w")


    ttk.Label(frame_param, text="音频语言:").grid(row=1, column=0, sticky="e", padx=(0, 4), pady=(8, 0))
    var_language = tk.StringVar(value=config.get("whisper_language", "auto"))
    ttk.Combobox(
        frame_param, textvariable=var_language,
        values=["auto", "ja", "zh", "en"],
        width=8, state="readonly"
    ).grid(row=1, column=1, sticky="w", padx=(0, 20), pady=(8, 0))

    ttk.Label(frame_param, text="计算精度:").grid(row=1, column=2, sticky="e", padx=(0, 4))
    var_compute_type = tk.StringVar(value=config.get("whisper_compute_type", "float16"))
    ttk.Combobox(
        frame_param, textvariable=var_compute_type,
        values=["int8", "int8_float16", "int8_bfloat16","int16",
                "float16","float32","bfloat16"],
        width=10, state="readonly"
    ).grid(row=1, column=3, sticky="w", padx=(0, 20))

    var_vad = tk.BooleanVar(value=config.get("whisper_vad", True))
    ttk.Checkbutton(frame_param, text="启用 VAD（语音活动检测，减少幻觉）",
                    variable=var_vad).grid(
        row=2, column=0, columnspan=6, sticky="w", pady=(8, 0))
    ttk.Label(frame_param, text="这里只提供基本的参数选择",
              foreground="gray").grid(row=3, column=0, columnspan=6,sticky="w")
    #运行日志
    frame_log = ttk.LabelFrame(parent, text="运行日志", padding=10)
    frame_log.grid(row=3, column=0, sticky="nsew", **pad)
    frame_log.columnconfigure(0, weight=1)
    frame_log.rowconfigure(0, weight=1)

    log_text = tk.Text(
        frame_log, width=82, height=12, wrap="word",
        bg="#1e1e1e", fg="#d4d4d4",
        font=("Consolas", 9), state="disabled"
    )
    log_scrollbar = ttk.Scrollbar(frame_log, orient="vertical", command=log_text.yview)
    log_text.configure(yscrollcommand=log_scrollbar.set)
    log_text.grid(row=0, column=0, sticky="nsew")
    log_scrollbar.grid(row=0, column=1, sticky="ns")

    def append_log(msg):
        parent.after(0, _append_log, msg)

    def _append_log(msg):
        log_text.configure(state="normal")
        log_text.insert("end", msg + "\n")
        log_text.see("end")
        log_text.configure(state="disabled")

    #开始按钮
    btn_run = ttk.Button(parent, text="▶  开始转录")
    btn_run.grid(row=4, column=0, pady=10)

    def save_whisper_config():
        config["whisper_engine"]       = var_engine.get()
        config["whisper_threads"]      = var_threads.get()
        config["whisper_workers"]      = var_workers.get()
        config["whisper_language"]     = var_language.get()
        config["whisper_vad"]          = var_vad.get()
        config["whisper_compute_type"] =var_compute_type.get()
        save_config(config)

    def start():
        model_path = var_model_path.get().strip()
        audio_path = var_audio_path.get().strip()
        output_dir = var_output_dir.get().strip()

        if not model_path:
            messagebox.showwarning("缺少参数", "请选择 Whisper 模型路径")
            return
        if not audio_path:
            messagebox.showwarning("缺少参数", "请选择音频/视频文件")
            return
        if not output_dir:
            messagebox.showwarning("缺少参数", "请选择输出目录")
            return
        if not os.path.isfile(audio_path):
            messagebox.showerror("文件不存在", f"找不到音频文件：\n{audio_path}")
            return

        save_whisper_config()
        btn_run.configure(state="disabled", text="转录中…")

        engine   = var_engine.get()
        compute_type = var_compute_type.get()
        threads  = var_threads.get()
        workers  = var_workers.get()
        language = var_language.get() if var_language.get() != "auto" else None
        vad      = var_vad.get()

        def task():
            try:
                success, out, msg =whisper_trans(
                    model_path   = model_path,
                    audio_path   = audio_path,
                    output_dir   = output_dir,
                    engine       = engine,
                    compute_type = compute_type,
                    threads      = threads,
                    workers      = workers,
                    language     = language,
                    vad          = vad,
                    log_callback = append_log
                )
                if not success:
                    append_log(f"❌ 错误: {msg}")
                parent.after(0, on_done, success, output_dir)
            except Exception as e:
                append_log(f"❌ 异常: {e}")
                parent.after(0, on_done, False, output_dir)

        threading.Thread(target=task, daemon=True).start()

    def on_done(success, out_dir):
        btn_run.configure(state="normal", text="▶  开始转录")
        if success:
            if messagebox.askyesno("完成", f"转录完成！\n\n输出目录：{out_dir}\n\n是否打开？"):
                os.startfile(os.path.abspath(out_dir))
        else:
            messagebox.showerror("失败", "转录过程中发生错误，请查看日志。")

    btn_run.configure(command=start)

def gui():
    root = tk.Tk()
    root.title("自用工具整合")
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)
    tab1 = ttk.Frame(notebook)
    tab2 = ttk.Frame(notebook)
    tab3 = ttk.Frame(notebook)
    tab4 = ttk.Frame(notebook)

    notebook.add(tab1, text="字幕烧录工具")
    notebook.add(tab2, text="视频下载工具")
    notebook.add(tab3, text="whisper工具")
    notebook.add(tab4, text="一些小工具")

    addSubtitle_gui(tab1)
    ytDownload_gui(tab2)
    whisper_gui(tab3)
    assExtract_gui(ttk.LabelFrame(tab4, text="ASS转TXT（只保留字幕没有时间戳）", padding=10))
    txtTransform_gui(ttk.LabelFrame(tab4, text="油管字幕断句（用于字幕乱断时）", padding=10))
    timestamps_gui(ttk.LabelFrame(tab4, text="时间戳提取(用于whisper手打时间戳，适合先轴后翻）", padding=10))
    cookiesGain_gui(ttk.LabelFrame(tab4, text="油管Cookie获取", padding=10))
    root.mainloop()