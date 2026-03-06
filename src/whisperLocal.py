from faster_whisper import WhisperModel
import os
from multiprocessing import Process, Queue

def _worker(q, model_path, audio_path, output_dir, engine, compute_type, threads, workers, language, vad):
    try:
        model = WhisperModel(model_path, device=engine, compute_type=compute_type,
                             cpu_threads=threads, num_workers=workers)

        segments, info = model.transcribe(
            audio_path,
            language=language,
            vad_filter=vad,
        )

        def seconds_to_srt_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        os.makedirs(output_dir, exist_ok=True)
        name = os.path.splitext(os.path.basename(audio_path))[0]
        output_file = os.path.join(output_dir, name + ".srt")

        with open(output_file, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, start=1):
                f.write(f"{i}\n")
                f.write(f"{seconds_to_srt_time(segment.start)} --> {seconds_to_srt_time(segment.end)}\n")
                f.write(f"{segment.text.strip()}\n\n")
                f.flush()
                q.put(("log", f"[{seconds_to_srt_time(segment.start)}] {segment.text.strip()}"))

        q.put(("done", output_file))

    except Exception as e:
        q.put(("error", str(e)))


def whisper_trans(model_path, audio_path, output_dir, engine,
    compute_type, threads, workers, language, vad, log_callback
):
    log_callback("▶ 开始转录，请稍候…")

    q = Queue()
    p = Process(target=_worker, args=(
        q, model_path, audio_path, output_dir,
        engine, compute_type, threads, workers, language, vad
    ))
    p.start()

    while True:
        msg = q.get()
        if msg[0] == "log":
            log_callback(msg[1])
        elif msg[0] == "done":
            p.join()
            log_callback(f"字幕已保存到 {msg[1]}")
            return True, output_dir, ""
        elif msg[0] == "error":
            p.join()
            log_callback(f"❌ 错误: {msg[1]}")
            return False, output_dir, msg[1]