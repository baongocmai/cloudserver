import json
import re
from pathlib import Path

def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(len(words), start + chunk_size)
        chunks.append(' '.join(words[start:end]))
        start += chunk_size - overlap
    return chunks

def extract_text_from_json(file_path: Path, text_fields: list[str]) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    texts = []
    if isinstance(data, list):
        for item in data:
            for field in text_fields:
                if field in item and item[field]:
                    texts.append(str(item[field]))
    elif isinstance(data, dict):
        for field in text_fields:
            if field in data and data[field]:
                texts.append(str(data[field]))
    else:
        print(f"Unsupported JSON structure in {file_path.name}")
    return " ".join(texts)


def process_files(input_dir: Path, output_dir: Path, json_fields: list[str]):
    output_dir.mkdir(parents=True, exist_ok=True)
    for file_path in input_dir.iterdir():
        if file_path.suffix == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                raw_text = f.read()
        elif file_path.suffix == ".json":
            raw_text = extract_text_from_json(file_path, json_fields)
        else:
            continue

        cleaned = clean_text(raw_text)
        chunks = chunk_text(cleaned, chunk_size=300, overlap=50)

        output_file = output_dir / f"{file_path.stem}.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n\n".join(chunks))
        print(f"[Saved] {output_file.name}")

# Ví dụ gọi hàm:
input_dir = Path("E:/VHC/cloudserver/data/text/extracted")
output_dir = Path("E:/VHC/cloudserver/data/text/cleaned")
json_fields = ["title", "body"]  # chỉnh theo dữ liệu bạn có

process_files(input_dir, output_dir, json_fields)
