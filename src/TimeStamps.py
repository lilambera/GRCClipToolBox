import re
"""
逻辑：提取ASS文件第2（开始时间戳），3（结束时间戳）行的内容生成连续时间戳字符串
使用场景：用于先打轴后翻译场景下让whisper先提取一遍日语文本（提取更精确）
返回的格式也是完全用依照whisper的输入要求进行返回的，其他地方（我也不知道还有什么地方）不适用
"""
def format_timestamp(timestamp):
    match = re.match(r'(\d+):(\d+):(\d+)\.(\d+)', timestamp)
    if match:
        hours, minutes, seconds, centiseconds = match.groups()
        deciseconds = centiseconds[0] if centiseconds else '0'
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}.{deciseconds}"
    return timestamp


def time_to_seconds(time_str):
    match = re.match(r'(\d+):(\d+):(\d+)\.(\d+)', time_str)
    if match:
        hours, minutes, seconds, deciseconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(deciseconds) / 10.0
    return 0


def ass_timestamps(ass_file, start_after=None):
    start_after_seconds = time_to_seconds(start_after) if start_after else None

    with open(ass_file, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()

    timestamps = []
    for line in lines:
        if line.startswith('Dialogue:'):
            parts = line.split(',', 9)
            if len(parts) >= 3:
                start_formatted = format_timestamp(parts[1].strip())
                end_formatted   = format_timestamp(parts[2].strip())

                if start_after_seconds is not None:
                    if time_to_seconds(start_formatted) < start_after_seconds:
                        continue

                timestamps.append(f"{start_formatted}-{end_formatted}")

    return ';'.join(timestamps), len(timestamps)