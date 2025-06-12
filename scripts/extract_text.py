import sys
import os
from pathlib import Path

def extract_text_from_pdf(file_path):
    import pdfplumber
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def extract_text_from_docx(file_path):
    from docx import Document
    doc = Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_text_from_txt(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def extract_text_from_html(file_path):
    from bs4 import BeautifulSoup
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
        return soup.get_text(separator="\n")

def extract_text_from_csv(file_path):
    import csv
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        return "\n".join([", ".join(row) for row in reader])

def extract_text(file_path):
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return extract_text_from_docx(file_path)
    elif ext in [".txt", ".md"]:
        return extract_text_from_txt(file_path)
    elif ext == ".html":
        return extract_text_from_html(file_path)
    elif ext == ".csv":
        return extract_text_from_csv(file_path)
    else:
        return f"[Unsupported file format: {file_path}]"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_text.py <file_path>")
        sys.exit(1)

    file_path = Path(sys.argv[1])

    if not file_path.exists():
        print(f"[Error] File not found: {file_path}")
        sys.exit(1)

    try:
        text = extract_text(file_path)
        print(text)
    except Exception as e:
        print(f"[Error] {e}")
        sys.exit(1)

output_dir = Path("data/text/extracted")
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / f"{file_path.stem}.txt"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(text)
print(f"[Saved] Text saved to {output_file}")
