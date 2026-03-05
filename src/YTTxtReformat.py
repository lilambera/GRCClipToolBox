import re


def reformat_text(input_file, output_file=None):

    if output_file is None:
        output_file = input_file

    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read()

    text = text.replace("\n", "").replace("\r", "")
    text = re.sub(r"([。．！？!?])", r"\1\n", text)
    text = re.sub(r"\n+", "\n", text)
    text = text.strip()

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(text)

    return output_file, len(text.splitlines())