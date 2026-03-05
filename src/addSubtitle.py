import os
import subprocess
"""
功能：把字幕烤录进视频用的
临时文件夹作用：由于被ffmpeg路径搞破防，这里怕中文路径不行，
            因此用了纯英文路径做临时文件夹，将视频和字幕拷贝一份到这合并完了再转回去
            所以临时文件夹的位置剩余空间一定要比视频和字幕体积大
"""
def burn_subtitles(input_video, subtitle_file, output_video,
                   work_dir,crf=23, audio_bitrate="192k", log_callback=None):
    import shutil

    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    ext = os.path.splitext(subtitle_file)[1].lower().strip()
    video_ext = os.path.splitext(input_video)[1].lower().strip()

    os.makedirs(work_dir, exist_ok=True)

    tmp_video = os.path.join(work_dir, "input" + video_ext)
    tmp_sub   = os.path.join(work_dir, "subtitle" + ext)
    tmp_out   = os.path.join(work_dir, "output.mp4")

    log("▶ 开始处理...")
    log("  输入：" + input_video)
    log("  字幕：" + subtitle_file)
    log("  输出：" + output_video)
    log("  正在复制文件到工作目录：" + work_dir)

    for f in [tmp_video, tmp_sub, tmp_out]:
        try:
            os.remove(f)
        except FileNotFoundError:
            pass
    shutil.copy2(input_video, tmp_video)
    shutil.copy2(subtitle_file, tmp_sub)
    log("  复制完成")
    log("─" * 60)
    ffmpeg_exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), r"ffmpeg\bin\ffmpeg.exe")
    os.chdir(work_dir)

    vf_value = f"subtitles=subtitle{ext}"

    args = [
        ffmpeg_exe,
        "-y",
        "-i", "input" + video_ext,
        "-vf", vf_value,
        "-c:v", "libx264",
        "-crf", str(crf),
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "output.mp4"
    ]

    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        creationflags = subprocess.CREATE_NO_WINDOW
    )

    for line in process.stdout:
        log(line.rstrip())

    process.wait()
    log("─" * 60)

    success = process.returncode == 0

    if success:
        shutil.move(tmp_out, output_video)
        log("✅ 完成！输出：" + output_video)
    else:
        log(f"❌ 失败，返回码：{process.returncode}")

    for f in [tmp_video, tmp_sub, tmp_out]:
        try:
            os.remove(f)
        except Exception:
            pass

    return success