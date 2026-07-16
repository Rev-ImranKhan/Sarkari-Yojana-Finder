import os
import sys
import rag_core

DATA_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def main():
    if not os.getenv("GEMINI_API_KEY") and not rag_core.GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY set nahi hai. Pehle .env file banao (.env.example dekho).")
        sys.exit(1)

    pdf_files = [f for f in os.listdir(DATA_FOLDER) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print(f"'{DATA_FOLDER}' mein koi PDF nahi mili. Kuch scheme PDFs daal ke phir se chalao.")
        return

    print(f"{len(pdf_files)} PDF(s) mili. Processing shuru...\n")

    already_added = set(rag_core.list_uploaded_documents())

    for filename in pdf_files:
        if filename in already_added:
            print(f"  [SKIP] '{filename}' already database mein hai.")
            continue

        file_path = os.path.join(DATA_FOLDER, filename)
        print(f"  [PROCESSING] '{filename}' ...")
        try:
            chunk_count = rag_core.add_document(file_path, filename)
            print(f"  [DONE] '{filename}' -> {chunk_count} chunks add hue.\n")
        except Exception as exc:
            print(f"  [ERROR] '{filename}' process nahi hui: {exc}\n")

    total = rag_core.get_document_count()
    print(f"Sab ho gaya. ChromaDB mein total {total} chunks stored hain.")


if __name__ == "__main__":
    main()
