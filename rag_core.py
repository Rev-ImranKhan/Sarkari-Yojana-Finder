import os
import time
import uuid
import chromadb
from google import genai
from google.genai import types
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

EMBEDDING_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
GENERATION_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-flash-latest")

CHROMA_DB_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
COLLECTION_NAME = "sarkari_yojana"

# ChromaDB persistent client - data disk pe save rehta hai, restart pe bhi nahi udta
_chroma_client = chromadb.PersistentClient(
    path=CHROMA_DB_PATH,
    settings=chromadb.Settings(anonymized_telemetry=False),
)
_collection = _chroma_client.get_or_create_collection(name=COLLECTION_NAME)


# ---------------------------------------------------------------------------
# STEP 1: PDF se text nikalna
# ---------------------------------------------------------------------------
def extract_text_from_pdf(file_path: str) -> str:
    """PDF file ka poora text ek single string mein return karta hai."""
    reader = PdfReader(file_path)
    full_text = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        full_text.append(page_text)
    return "\n".join(full_text)


# ---------------------------------------------------------------------------
# STEP 2: Text ko chunks mein todna
# ---------------------------------------------------------------------------
def chunk_text(text: str, chunk_size: int = 400, overlap: int = 60) -> list:
    """
    Text ko word-based chunks mein todta hai, thoda overlap rakhte hue.

    Overlap kyun? Agar ek important sentence exactly do chunks ke beech
    mein cut ho jaye, to context incomplete ho jayega. Overlap us risk ko
    kam karta hai.
    """
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


# ---------------------------------------------------------------------------
# STEP 3: Embeddings banana (naye google-genai SDK se)
# ---------------------------------------------------------------------------
def get_embedding(text: str, task_type: str = "RETRIEVAL_DOCUMENT", max_retries: int = 6) -> list:
    """
    Gemini embedding model se text ka vector nikalta hai.
    task_type: 'RETRIEVAL_DOCUMENT' jab document store kar rahe ho,
               'RETRIEVAL_QUERY' jab user ka sawal embed kar rahe ho.

    Free tier mein per-minute request limit kaafi kam hoti hai, isliye
    agar 429 (rate limit) ya 503 (Google server temporary down) error
    aaye to yeh function khud thoda ruk kar (exponential backoff)
    dobara try karta hai, bajaye turant fail hone ke.
    """
    if _client is None:
        raise RuntimeError("GEMINI_API_KEY set nahi hai. .env file check karo.")

    delay = 5  # seconds - pehli retry se pehle itna rukenge
    for attempt in range(max_retries):
        try:
            result = _client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config=types.EmbedContentConfig(task_type=task_type),
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
                delay = min(delay * 2, 60)  # har baar zyada rukna, max 60 sec
            else:
                raise


# ---------------------------------------------------------------------------
# STEP 4: Document ko process karke ChromaDB mein add karna
# ---------------------------------------------------------------------------
def add_document(file_path: str, filename: str) -> int:
    """
    PDF file ko poora process karta hai: extract -> chunk -> embed -> store.
    Return karta hai kitne chunks add hue.
    """
    text = extract_text_from_pdf(file_path)
    chunks = chunk_text(text)

    if not chunks:
        return 0

    ids = []
    embeddings = []
    documents = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        chunk_id = f"{filename}_{uuid.uuid4().hex[:8]}_{i}"
        embedding = get_embedding(chunk, task_type="RETRIEVAL_DOCUMENT")

        ids.append(chunk_id)
        embeddings.append(embedding)
        documents.append(chunk)
        metadatas.append({"source": filename, "chunk_index": i})

        # Free tier ki per-minute limit se bachne ke liye har chunk ke
        # baad thoda ruk jaate hain (proactive throttling)
        time.sleep(2)

        if (i + 1) % 10 == 0:
            print(f"    ... {i + 1}/{len(chunks)} chunks embed ho chuke hain")

    _collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    return len(chunks)


# ---------------------------------------------------------------------------
# STEP 5: Retrieval - user ke sawal se relevant chunks dhoondhna
# ---------------------------------------------------------------------------
def retrieve_relevant_chunks(question: str, n_results: int = 5) -> list:
    """User ke sawal ke embedding se ChromaDB mein similarity search karta hai."""
    if _collection.count() == 0:
        return []

    query_embedding = get_embedding(question, task_type="RETRIEVAL_QUERY")

    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, _collection.count()),
    )

    chunks = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    for doc, meta in zip(documents, metadatas):
        chunks.append({"text": doc, "metadata": meta})

    return chunks


# ---------------------------------------------------------------------------
# STEP 6: Grounded answer generate karna
# ---------------------------------------------------------------------------
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
    """
    Retrieved chunks ko context bana kar Gemini se grounded answer generate
    karta hai. Agar koi chunk retrieve hi nahi hua (documents upload nahi
    hue), to seedha bata deta hai.
    """
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
        return {
            "answer": "GEMINI_API_KEY set nahi hai. .env file check karo.",
            "sources": [],
        }

    context = "\n\n---\n\n".join(c["text"] for c in retrieved_chunks)
    sources = sorted({c["metadata"]["source"] for c in retrieved_chunks})

    prompt = (
        f"CONTEXT (uploaded scheme documents se liya gaya):\n{context}\n\n"
        f"USER QUESTION:\n{question}\n\n"
        f"ANSWER:"
    )

    response = _client.models.generate_content(
        model=GENERATION_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION),
    )

    return {"answer": response.text, "sources": sources}


def list_uploaded_documents() -> list:
    """ChromaDB mein stored saare unique document (filename) return karta hai."""
    if _collection.count() == 0:
        return []
    all_metadata = _collection.get(include=["metadatas"])["metadatas"]
    return sorted({m["source"] for m in all_metadata})


def get_document_count() -> int:
    """Kitne chunks total store hain (debug/status ke liye)."""
    return _collection.count()
