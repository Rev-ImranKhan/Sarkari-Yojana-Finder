import os
import time
import uuid
from google import genai
from google.genai import types
from pypdf import PdfReader
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

EMBEDDING_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
GENERATION_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-flash-latest")
EMBED_DIMENSIONS = 768  # Supabase table isi dimension pe bani hai

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
_supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
TABLE_NAME = "scheme_chunks"


def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    full_text = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        full_text.append(page_text)
    return "\n".join(full_text)


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 60) -> list:
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def get_embedding(text: str, task_type: str = "RETRIEVAL_DOCUMENT", max_retries: int = 6) -> list:
    if _client is None:
        raise RuntimeError("GEMINI_API_KEY set nahi hai. .env file check karo.")

    delay = 5
    for attempt in range(max_retries):
        try:
            result = _client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=EMBED_DIMENSIONS,
                ),
            )
            return result.embeddings[0].values
        except Exception as exc:
            is_rate_limit = (
                "429" in str(exc)
                or "RESOURCE_EXHAUSTED" in str(exc)
                or "503" in str(exc)
                or "UNAVAILABLE" in str(exc)
            )
            if is_rate_limit and attempt < max_retries - 1:
                print(f"    [RATE LIMIT/SERVER] {delay} second ruk kar dobara try kar rahe hain...")
                time.sleep(delay)
                delay = min(delay * 2, 60)
            else:
                raise


def add_document(file_path: str, filename: str) -> int:
    if _supabase is None:
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY set nahi hai. .env file check karo.")

    text = extract_text_from_pdf(file_path)
    chunks = chunk_text(text)

    if not chunks:
        return 0

    rows = []
    for i, chunk in enumerate(chunks):
        embedding = get_embedding(chunk, task_type="RETRIEVAL_DOCUMENT")
        rows.append({
            "id": f"{filename}_{uuid.uuid4().hex[:8]}_{i}",
            "content": chunk,
            "embedding": embedding,
            "source": filename,
            "chunk_index": i,
        })
        time.sleep(2)
        if (i + 1) % 10 == 0:
            print(f"    ... {i + 1}/{len(chunks)} chunks embed ho chuke hain")

    for i in range(0, len(rows), 100):
        _supabase.table(TABLE_NAME).insert(rows[i:i + 100]).execute()

    return len(chunks)


def retrieve_relevant_chunks(question: str, n_results: int = 5) -> list:
    if _supabase is None:
        return []

    query_embedding = get_embedding(question, task_type="RETRIEVAL_QUERY")

    response = _supabase.rpc(
        "match_scheme_chunks",
        {"query_embedding": query_embedding, "match_count": n_results},
    ).execute()

    chunks = []
    for row in response.data:
        chunks.append({
            "text": row["content"],
            "metadata": {"source": row["source"]},
        })
    return chunks


SYSTEM_INSTRUCTION = """Tum "Sarkari Yojana Finder" naam ke AI assistant ho jo Indian
government schemes (jaise PM Kisan, Ayushman Bharat, PMAY, etc.) ke baare mein
logon ki madad karta hai.

STRICT RULES (kabhi mat todna):
1. SIRF neeche diye gaye CONTEXT ke basis par answer do. Apni training
   knowledge ya assumptions se koi fact mat jodo.
2. Agar CONTEXT mein user ke sawal ka jawab nahi milta, saaf aur seedha bolo:
   "Ye information uploaded documents mein available nahi hai."
3. Agar user ne apni profile batayi hai (occupation, income, land, category,
   age, etc.), to CONTEXT ke eligibility criteria se compare karke batao ki
   wo eligible hai ya nahi, aur kyun.
4. Agar eligible lagta hai, to structure mein batao:
   - Konsi scheme
   - Kis criteria ke basis par eligible hai
   - Apply karne ke liye kaunse documents/steps chahiye (CONTEXT se hi)
5. User jis language ya style mein sawal poochhe (Hindi, Hinglish, Telugu,
   Kannada, Tamil, English, etc.), usi language mein jawab do - user ki
   language ko match karo, khud se koi language mat thopo.
6. Koi bhi scheme detail invent mat karo jo CONTEXT mein exist nahi karti."""


def generate_answer(question: str, retrieved_chunks: list) -> dict:
    if not retrieved_chunks:
        return {
            "answer": (
                "Abhi tak koi scheme document upload nahi hua hai. "
                "Pehle kuch government scheme PDFs upload karo, uske baad "
                "main tumhari madad kar sakta hoon."
            ),
            "sources": [],
        }

    if _client is None:
        return {"answer": "GEMINI_API_KEY set nahi hai. .env file check karo.", "sources": []}

    context = "\n\n---\n\n".join(c["text"] for c in retrieved_chunks)
    sources = sorted({c["metadata"]["source"] for c in retrieved_chunks})

    prompt = (
        f"CONTEXT (uploaded scheme documents se liya gaya):\n{context}\n\n"
        f"USER QUESTION:\n{question}\n\n"
        f"ANSWER:"
    )

    delay = 5
    for attempt in range(5):
        try:
            response = _client.models.generate_content(
                model=GENERATION_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION),
            )
            return {"answer": response.text, "sources": sources}
        except Exception as exc:
            is_temp = "429" in str(exc) or "503" in str(exc) or "UNAVAILABLE" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
            if is_temp and attempt < 4:
                time.sleep(delay)
                delay = min(delay * 2, 30)
            else:
                return {"answer": "Gemini server abhi busy hai. Thodi der mein dobara try karo.", "sources": sources}


def list_uploaded_documents() -> list:
    if _supabase is None:
        return []
    response = _supabase.table(TABLE_NAME).select("source").execute()
    return sorted({row["source"] for row in response.data})


def get_document_count() -> int:
    if _supabase is None:
        return 0
    response = _supabase.table(TABLE_NAME).select("id", count="exact").execute()
    return response.count or 0