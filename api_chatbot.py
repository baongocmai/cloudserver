from fastapi import FastAPI, Request
import weaviate
import google.generativeai as genai
import json
import re
from rapidfuzz import process, fuzz
from typing import List, Optional
from weaviate.classes.query import Filter
app = FastAPI()

# Load dữ liệu FAQ khi server khởi động
with open("E:/VHC/cloudserver/data/faq_data.json", "r", encoding="utf-8") as f:
    FAQ_DATA = json.load(f)

# CẤU HÌNH GEMINI + WEAVIATE
genai.configure(api_key="AIzaSyCpZTbJSQPZnQRf1RxFF7mzpWgy_0UhPjg")

client = weaviate.connect_to_custom(
    http_host="localhost",
    http_port=8080,
    http_secure=False,
    grpc_host="localhost",
    grpc_port=50051,
    grpc_secure=False
)

# UTILS
def find_faq_answer(question, faq_data, threshold=89, min_question_length=3):
    question = question.strip().lower()
    if len(question) < min_question_length:
        return None

    questions = [item["question"].lower() for item in faq_data]

    for idx, q in enumerate(questions):
        if q == question:
            return faq_data[idx]["answer"]

    match = process.extractOne(question, questions)
    if match:
        matched_question, score, idx = match
        if score >= threshold:
            return faq_data[idx]["answer"]
    return None

def query_embedding(text: str):
    response = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type="retrieval_query"
    )
    return response['embedding']

def extract_service_type_from_question(question: str) -> Optional[str]:
    match = re.search(r"cloud\s*([1-9])", question.lower())
    if match:
        return f"CLOUD{match.group(1)}".upper()
    return None


def search_similar_hybrid_with_filters(question, embedding, service_type=None, term=None, storage=None, top_k=5):
    collection = client.collections.get("DocumentChunk")

    filters = []
    if service_type:
        filters.append(Filter.by_property("serviceType").equal(service_type))
    if term:
        filters.append(Filter.by_property("term").equal(term))
    if storage:
        filters.append(Filter.by_property("storageType").equal(storage))

    if filters:
        # Kết hợp filter bằng AND (logical &)
        filter_combined = filters[0]
        for f in filters[1:]:
            filter_combined &= f
    else:
        filter_combined = None

    result = collection.query.hybrid(
        query=question,
        vector=embedding,
        limit=top_k,
        alpha=0.5,
        filters=filter_combined,
        return_properties=["fileName", "chunkIndex", "text", "serviceType", "term", "storageType"]
    )
    return result.objects

def postprocess_answer(answer: str, context_texts: List[str]) -> str:
    # Bỏ kiểm tra quá chặt, chỉ lọc câu trả lời nếu nó quá ngắn hoặc chứa câu từ phủ định không mong muốn
    # Ví dụ loại bỏ câu trả lời kiểu "Thông tin không được cung cấp"
    negative_phrases = [
        "không được cung cấp",
        "không có trong tài liệu",
        "không đề cập",
        "chưa rõ",
        "không tìm thấy",
        "không có thông tin"
    ]
    answer_lower = answer.lower()
    for phrase in negative_phrases:
        if phrase in answer_lower:
            return "Vui lòng liên hệ trực tiếp qua số điện thoại (+84) 931.101.101 hoặc Mail: support.cloud@mobifone.vn để được hỗ trợ các vấn đề kỹ thuật đồng thời nhận tư vấn chi tiết và chính xác nhất."

    # Nếu trả lời quá ngắn hoặc chỉ là số thì trả fallback
    if len(answer.strip()) < 15 or answer.strip().isdigit():
        return "Vui lòng liên hệ trực tiếp qua số điện thoại (+84) 931.101.101 hoặc Mail: support.cloud@mobifone.vn để được hỗ trợ các vấn đề kỹ thuật đồng thời nhận tư vấn chi tiết và chính xác nhất."

    return answer.strip()
def add_question_mark_if_missing(text: str) -> str:
    text = text.strip()
    if not text.endswith('?'):
        text += '?'
    return text

def rewrite_query(original_query: str) -> str:
    q = original_query.strip().lower()

    # Rewrite nhanh một số mẫu thường gặp
    if re.match(r"^cài đặt\s+", q):
        q = re.sub(r"^cài đặt", "cách cài đặt", q)

    # Chuyển các từ không chuẩn sang dạng chuẩn
    q = q.replace("làm sao", "cách")
    q = q.replace("thế nào", "như thế nào")

    # Bổ sung dấu hỏi
    if not q.endswith("?"):
        q += "?"

    # Prompt Gemini để cải tiến thêm câu hỏi
    prompt = (
        "Bạn là trợ lý AI cho khách hàng dịch vụ Cloud MobiFone. Hãy viết lại câu sau thành một câu hỏi rõ ràng, đầy đủ, có cấu trúc tốt hơn. "
        "Nếu là câu hỏi dạng ngắn (ví dụ 'Tạo máy ảo thế nào'), hãy chuyển thành 'Cách tạo máy ảo như thế nào?'. "
        "Nếu chưa phải câu hỏi, hãy viết lại thành câu hỏi và thêm dấu '?'\n\n"
        f"Câu hỏi gốc: \"{q}\"\n\n"
        "Câu hỏi đã viết lại:"
    )

    try:
        response = genai.chat.completions.create(
            model="models/chat-bison-001",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=64,
        )
        rewritten_query = response.choices[0].message.content.strip()
        return rewritten_query
    except:
        return q


def build_prompt(user_question: str, context_texts: List[str]):
    return f"""
Bạn là trợ lý AI của dịch vụ MobiFone Cloud. Hãy coi đầu vào là một câu hỏi và trả lời câu hỏi ấy dựa trên các đoạn thông tin bên dưới.
Câu hỏi: {user_question}

Ngữ cảnh:

{chr(10).join(context_texts)}

Chỉ sử dụng thông tin từ ngữ cảnh để trả lời. Nếu thông tin không có trong ngữ cảnh, trả lời đúng y như sausau: 
'Vui lòng liên hệ trực tiếp qua số điện thoại (+84) 931.101.101 hoặc Mail: support.cloud@mobifone.vn để được hỗ trợ các vấn đề kỹ thuật đồng thời nhận tư vấn chi tiết và chính xác nhất.'
Trả lời một cách tự nhiên, dễ hiểu và rõ ràng, không chỉ lặp lại ngữ cảnh gốc. Không được trả lời thêm tương tự như này 'Thông tin chi tiết về vị trí và cấu hình của các trung tâm này không được cung cấp trong tài liệu hiện có.'
- Không được bịa thêm thông tin hoặc viết kiểu: "Thông tin không được cung cấp", "Tài liệu không đề cập", "Chưa rõ vị trí", hay các câu nói giảm nói tránh tương tự.
Câu trả lời phải tự nhiên, rõ ràng và đúng trọng tâm.
"""

def generate_answer(question: str, context_texts: List[str]) -> str:
    prompt = build_prompt(question, context_texts)
    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)
    answer = response.text if hasattr(response, "text") else ""
    
    return postprocess_answer(answer, context_texts)



def extract_price_query_info(question: str):
    service = None
    term = None
    storage = None
    
    m = re.search(r"cloud\s*([1-9])", question, re.I)
    if m:
        service = f"CLOUD{m.group(1)}"
    
    if re.search(r"1 tháng", question, re.I):
        term = "1 tháng"
    elif re.search(r"6 tháng", question, re.I):
        term = "6 tháng"
    elif re.search(r"12 tháng", question, re.I):
        term = "12 tháng"

    if re.search(r"ssd", question, re.I):
        storage = "SSD"
    elif re.search(r"hdd", question, re.I):
        storage = "HDD"

    return service, term, storage

def search_similar_with_price_filters(embedding, question, top_k=5):
    collection = client.collections.get("DocumentChunk")
    service, term, storage = extract_price_query_info(question)
    
    filters = []
    if service:
        filters.append({
            "path": ["serviceType"],
            "operator": "Equal",
            "valueText": service
        })
    if term:
        filters.append({
            "path": ["term"],
            "operator": "Equal",
            "valueText": term
        })
    if storage:
        filters.append({
            "path": ["storageType"],
            "operator": "Equal",
            "valueText": storage
        })

    filter_obj = None
    if filters:
        if len(filters) == 1:
            filter_obj = filters[0]
        else:
            filter_obj = {
                "operator": "And",
                "operands": filters
            }

    result = collection.query.near_vector(
        embedding,
        filters=filter_obj,
        limit=top_k,
        return_properties=["fileName", "chunkIndex", "text", "serviceType", "term", "storageType"]
    )
    
    return result.objects

# API
@app.post("/query")
async def query_endpoint(request: Request):
    data = await request.json()
    question = data.get("question", "").strip()
    if not question:
        return {"error": "Missing question"}

    if not question.endswith("?"):
        question += "?"

    print(f">>> [STEP 1] Original question = {question}")

    # 1. Tìm câu trả lời trong Frag (FAQ) trước
    frag_answer = find_faq_answer(question, FAQ_DATA)
    print(f">>> [STEP 1] Frag match = {frag_answer}")
    if frag_answer:
        return {"answer": frag_answer, "source": "frag"}

    # 2. Nếu không có trong FAQ, gọi RAG
    try:
        expanded_question = rewrite_query(question)
    except Exception:
        expanded_question = question

    embedding = query_embedding(expanded_question)
    service_type, term, storage = extract_price_query_info(expanded_question)

    results = search_similar_hybrid_with_filters(
        expanded_question,
        embedding,
        service_type=service_type,
        term=term,
        storage=storage
    )

    print(f">>> expanded_question = {expanded_question}")
    print(f">>> embedding = {embedding[:5]}...")
    print(f">>> Filters: service_type = {service_type}, term = {term}, storage = {storage}")
    print(f">>> Top results: {[r.properties.get('text', '')[:100] for r in results]}")

@app.get("/")
async def root():
    return {"message": "API chatbot is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
