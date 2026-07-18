import chromadb
import pickle
import os
from rag_core import CHROMA_DB_PATH, COLLECTION_NAME

print("🔄 ChromaDB se data load ho raha hai...")

# 🔥 YEH IMPORTANT HAI: Rag_core ke EXACT settings match karo
client = chromadb.PersistentClient(
    path=CHROMA_DB_PATH,
    settings=chromadb.Settings(anonymized_telemetry=False)
)

collection = client.get_collection(COLLECTION_NAME)

print("📦 Data pickle mein convert ho raha hai...")
data = collection.get(include=["embeddings", "documents", "metadatas"])

with open("chroma_backup.pkl", "wb") as f:
    pickle.dump(data, f)

size = os.path.getsize("chroma_backup.pkl") / (1024*1024)
print(f"✅ Pickle ban gayi! Size: {size:.2f} MB")
print(f"📍 Location: {os.path.abspath('chroma_backup.pkl')}")