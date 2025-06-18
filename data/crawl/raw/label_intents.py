import json
from collections import defaultdict

# File paths
sentences_file = "cloudserver/data/crawl/raw/cleaned_sentences.json"
labeled_file = "cloudserver/data/crawl/raw/intents_labeled.json"
knowledge_file = "cloudserver/data/crawl/raw/knowledge_data.json"

# Định nghĩa các category cần ĐƯA VÀO TRI THỨC
category_to_knowledge_intent = {
    "HƯỚNG DẪN SỬ DỤNG": "get_guide",
    "TIN TỨC": "get_news",
    "TÀI LIỆU": "get_manual",
    "GIỚI THIỆU": "get_about",
    "CÂU HỎI THƯỜNG GẶP": "manual_ques",
}

# Gán nhãn intent cụ thể theo từ khóa
keyword_to_intent = {
    "báo giá": "pricing",
    "giá": "pricing",
    "chi phí": "pricing",
    "hướng dẫn sử dụng": "how_to_use",
    "cách sử dụng": "how_to_use",
    "quy trình triển khai": "deployment_process",
    "triển khai": "deployment_process",
    "thông số kỹ thuật": "technical_spec",
    "cấu hình": "technical_spec",
    "hiệu suất": "technical_spec"
}

# Load dữ liệu
with open(sentences_file, "r", encoding="utf-8") as f:
    sentences = json.load(f)

labeled_data = []
knowledge_data = defaultdict(list)

def find_intent_by_keyword(text):
    """Trả về intent dựa trên từ khóa nếu khớp."""
    for keyword, intent in keyword_to_intent.items():
        if keyword.lower() in text.lower():
            return intent
    return "unknown"

# Xử lý từng câu
for item in sentences:
    sentence = item["sentence"]
    category = item.get("category", "").strip().upper()
    source = item.get("source", "")

    if category in category_to_knowledge_intent:
        intent = category_to_knowledge_intent[category]
        knowledge_data[intent].append({
            "sentence": sentence,
            "source": source,
            "category": category
        })
    else:
        intent = find_intent_by_keyword(sentence)
        labeled_data.append({
            "text": sentence,
            "intent": intent
        })

# Ghi file
with open(labeled_file, "w", encoding="utf-8") as f:
    json.dump(labeled_data, f, ensure_ascii=False, indent=2)

with open(knowledge_file, "w", encoding="utf-8") as f:
    json.dump(knowledge_data, f, ensure_ascii=False, indent=2)

print("✅ Gán nhãn & tạo tri thức hoàn tất.")
