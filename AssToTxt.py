import re
import os


def extract_ass_text(ass_file, output_file=None):
    if not os.path.isfile(ass_file):
        return False, "", f"文件不存在：{ass_file}"

    if output_file is None:
        base, _ = os.path.splitext(ass_file)
        output_file = base + "_text.txt"

    '''
    提取逻辑：ass格式文本部分格式为dialogues：xxx
    其中xxx部分以逗号为间隔分割时间戳、说话人等不同内容，第十段才是所需要的文本内容
    '''
    dialogues = []
    with open(ass_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("Dialogue:"):
                parts = line.split(",", 9)
                if len(parts) >= 10:
                    text = parts[9].strip()
                    text = re.sub(r"\{[^}]*\}", "", text)
                    text = text.replace("\\N", " ").replace("\\n", " ").strip()
                    if text:
                        dialogues.append(text)

    if not dialogues:
        return False, 0, "未提取到任何对话内容，请检查文件格式"
    out_dir = os.path.dirname(os.path.abspath(output_file))
    os.makedirs(out_dir, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(dialogues))

    return output_file, len(dialogues)