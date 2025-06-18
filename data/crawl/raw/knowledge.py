# cloudserver/data/crawl/raw/build_knowledge_from_web.py
import json
from collections import defaultdict

sentences_file = "cloudserver/data/crawl/raw/cleaned_sentences.json"
knowledge_file = "cloudserver/data/crawl/raw/knowledge_data.json"

# Load dữ liệu crawl từ web
with open(sentences_file, "r", encoding="utf-8") as f:
    sentences = json.load(f)

# Gom nhóm theo category → intent tri thức
category_to_knowledge_intent = {
    "HƯỚNG DẪN SỬ DỤNG": "get_guide",
    "TIN TỨC": "get_news",
    "TÀI LIỆU": "get_manual",
    "GIỚI THIỆU": "get_about",
    "CÂU HỎI THƯỜNG GẶP": "manual_ques",
    "BẢNG GIÁ": "get_price",
    "LIÊN HỆ": "get_contact",
    "DỊCH VỤ": "get_service",
}

knowledge_data = defaultdict(list)

for item in sentences:
    sentence = item["sentence"]
    category = item.get("category", "").strip().upper()
    source = item.get("source", "")

    # Dù category có hay không, vẫn cho vào tri thức
    intent = category_to_knowledge_intent.get(category, "get_general")
    knowledge_data[intent].append({
        "sentence": sentence,
        "source": source,
        "category": category
    })

# Ghi tri thức ra file
with open(knowledge_file, "w", encoding="utf-8") as f:
    json.dump(knowledge_data, f, ensure_ascii=False, indent=2)

print("✅ Tri thức từ web đã được xây dựng.")
