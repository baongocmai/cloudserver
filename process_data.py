import weaviate
from weaviate.config import AdditionalConfig, Timeout
from weaviate.classes.config import Configure, Property, DataType
import google.generativeai as genai
import re, json, sys
from pathlib import Path
from typing import List

# ========== Cấu hình API và kết nối ==========
genai.configure(api_key="AIzaSyCpZTbJSQPZnQRf1RxFF7mzpWgy_0UhPjg")  

client = weaviate.connect_to_custom(
    http_host="localhost",
    http_port=8080,
    http_secure=False,
    grpc_host="localhost",
    grpc_port=50051,
    grpc_secure=False,
    additional_config=AdditionalConfig(timeout=Timeout(init=10))
)

# ========== Tạo schema nếu chưa có ==========
def ensure_schema():
    collections = client.collections.list_all()
    if "DocumentChunk" not in collections:
        client.collections.create(
            name="DocumentChunk",
            vectorizer_config=Configure.Vectorizer.none(),
            properties=[
                Property(name="fileName", data_type=DataType.TEXT),
                Property(name="chunkIndex", data_type=DataType.INT),
                Property(name="text", data_type=DataType.TEXT),
                Property(name="serviceType", data_type=DataType.TEXT),
                Property(name="term", data_type=DataType.TEXT),         # thêm term
                Property(name="storageType", data_type=DataType.TEXT),  # thêm storageType
            ]
        )


# ========== Tiện ích xử lý văn bản ==========
def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def chunk_text(text: str, max_chunk_words=600, overlap_words=150, max_chunk_chars=35000):
    # Nếu có nhiều dòng, tách theo dòng, nếu không, tách theo từ thẳng
    if '\n' in text:
        lines = text.split('\n')
    else:
        # Không có dòng: coi toàn bộ text là 1 dòng
        lines = [text]

    chunks = []
    current_chunk = []
    current_len_words = 0
    current_len_chars = 0

    for line in lines:
        words_in_line = line.split()
        line_len_words = len(words_in_line)
        line_len_chars = len(line) + 1  # +1 cho dấu xuống dòng nếu có

        # Nếu thêm dòng này không vượt giới hạn
        if (current_len_words + line_len_words <= max_chunk_words) and (current_len_chars + line_len_chars <= max_chunk_chars):
            current_chunk.append(line)
            current_len_words += line_len_words
            current_len_chars += line_len_chars
        else:
            chunk_text = '\n'.join(current_chunk).strip()
            if chunk_text:
                chunks.append(chunk_text)

            # Xử lý overlap
            overlap = []
            words_to_keep = 0
            chars_to_keep = 0
            for l in reversed(current_chunk):
                w = l.split()
                words_to_keep += len(w)
                chars_to_keep += len(l) + 1
                overlap.insert(0, l)
                if words_to_keep >= overlap_words or chars_to_keep >= max_chunk_chars:
                    break

            current_chunk = overlap + [line]
            current_len_words = sum(len(l.split()) for l in current_chunk)
            current_len_chars = sum(len(l) + 1 for l in current_chunk)

    # Thêm chunk cuối nếu không rỗng
    if current_chunk:
        chunk_text = '\n'.join(current_chunk).strip()
        if chunk_text:
            chunks.append(chunk_text)

    # Nếu chỉ có 1 chunk quá lớn (vẫn > max_chunk_chars), chia nhỏ theo từ thẳng
    final_chunks = []
    for c in chunks:
        if len(c) > max_chunk_chars:
            words = c.split()
            start = 0
            while start < len(words):
                end = min(len(words), start + max_chunk_words)
                sub_chunk = ' '.join(words[start:end])
                final_chunks.append(sub_chunk)
                start += max_chunk_words - overlap_words
        else:
            final_chunks.append(c)

    return final_chunks

def extract_service_metadata(text: str) -> dict:
    match = re.search(r"(CLOUD\s*\d+)", text.upper())
    if match:
        return {"serviceType": match.group(1).replace(" ", "")}  # Ex: CLOUD1
    return {}

def extract_text_from_json(file_path: Path, fields: List[str]) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return ' '.join(data[f] for f in fields if f in data and isinstance(data[f], str))
import re

def extract_price_metadata(text: str) -> dict:
    meta = {}

    # serviceType: Cloud 1, Cloud 2 ...
    m_service = re.search(r"cloud\s*([1-9])", text, re.I)
    if m_service:
        meta["serviceType"] = f"CLOUD{m_service.group(1)}"
    else:
        meta["serviceType"] = "UNKNOWN"

    # term: 1 tháng, 6 tháng, 12 tháng
    if re.search(r"1 tháng", text, re.I):
        meta["term"] = "1 tháng"
    elif re.search(r"6 tháng", text, re.I):
        meta["term"] = "6 tháng"
    elif re.search(r"12 tháng", text, re.I):
        meta["term"] = "12 tháng"
    else:
        meta["term"] = "UNKNOWN"

    # storageType: SSD hoặc HDD
    if re.search(r"\bssd\b", text, re.I):
        meta["storageType"] = "SSD"
    elif re.search(r"\bhdd\b", text, re.I):
        meta["storageType"] = "HDD"
    else:
        meta["storageType"] = "UNKNOWN"

    return meta

# ========== Tạo vector bằng Gemini ==========
def create_embedding(text: str) -> List[float]:
    response = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type="retrieval_query"
    )
    return response["embedding"]

# ========== Lưu vector và metadata ==========
def save_vector(vec, meta):
    price_meta = extract_price_metadata(meta["text"])
    full_meta = {**meta, **price_meta}
    collection = client.collections.get("DocumentChunk")
    collection.data.insert(properties=full_meta, vector=vec)

# ========== Xử lý và lưu toàn bộ file ==========
def process_files(input_dir: Path, json_fields: List[str]):
    ensure_schema()
    for file in input_dir.iterdir():
        if file.suffix not in [".txt", ".json"]:
            continue
        try:
            raw_text = file.read_text(encoding="utf-8") if file.suffix == ".txt" else extract_text_from_json(file, json_fields)
            print(f"Read {len(raw_text)} chars from {file.name}")  # Debug
            cleaned = clean_text(raw_text)
            print(f"Cleaned text length: {len(cleaned)}")  # Debug

            chunks = chunk_text(cleaned, max_chunk_words=1000, overlap_words=100, max_chunk_chars=10000)
            print(f"Number of chunks: {len(chunks)}")
            for i, chunk in enumerate(chunks):
                print(f"Chunk {i} length: {len(chunk)} chars, words: {len(chunk.split())}")

            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    print(f"Skipping empty chunk {i} from {file.name}")
                    continue  # Bỏ qua chunk rỗng

                embedding = create_embedding(chunk)
                metadata = {
                    "fileName": file.name,
                    "chunkIndex": i,
                    "text": chunk
                }
                save_vector(embedding, metadata)
                print(f"✅ Saved chunk {i} from {file.name}")
        except Exception as e:
            print(f"❌ Error processing {file.name}: {e}")


# ========== Xem lại dữ liệu đã lưu ==========
def view_chunks(limit: int = 10):
    try:
        collection = client.collections.get("DocumentChunk")
        results = collection.query.fetch_objects(limit=limit)
        print(f"\n📦 Found {len(results.objects)} chunks:\n")
        for obj in results.objects:
            meta = obj.properties
            print(f"📄 {meta['fileName']} - Chunk {meta['chunkIndex']}")
            print(f"Text: {meta['text'][:100]}...\n")
    except Exception as e:
        print(f"❌ Failed to retrieve data: {e}")

# ========== Chạy từ CLI ==========
if __name__ == "__main__":
    try:
        command = sys.argv[1] if len(sys.argv) > 1 else None

        if command == "process":
            input_dir = Path("E:/VHC/cloudserver/data/text/cleaned")  # ← sửa đường dẫn tùy bạn
            json_fields = ["title", "text"]
            process_files(input_dir, json_fields)

        elif command == "view":
            view_chunks(limit=10)

        else:
            print("⚠️ Usage:")
            print("  python script.py process   # xử lý và lưu dữ liệu")
            print("  python script.py view      # xem dữ liệu đã lưu")

    finally:
        client.close()
