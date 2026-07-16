import os
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename

import rag_core

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "data")
ALLOWED_EXTENSIONS = {"pdf"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max per PDF

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    """PDF file leta hai, disk pe save karta hai, aur RAG pipeline se chunk+embed+store karta hai."""
    if "file" not in request.files:
        return jsonify({"error": "Koi file nahi mili."}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Filename khaali hai."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Sirf PDF files allowed hain."}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)

    try:
        chunk_count = rag_core.add_document(file_path, filename)
    except Exception as exc:
        return jsonify({"error": f"Processing fail hui: {str(exc)}"}), 500

    if chunk_count == 0:
        return jsonify({"error": "PDF se koi text nahi nikal paya (scanned image PDF ho sakta hai)."}), 400

    return jsonify({
        "message": f"'{filename}' successfully add ho gaya ({chunk_count} chunks).",
        "filename": filename,
        "chunks_added": chunk_count,
    })


@app.route("/chat", methods=["POST"])
def chat():
    """User ka sawal leta hai, relevant chunks retrieve karta hai, aur grounded answer deta hai."""
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()

    if not question:
        return jsonify({"error": "Sawal khaali hai."}), 400

    try:
        retrieved_chunks = rag_core.retrieve_relevant_chunks(question, n_results=5)
        result = rag_core.generate_answer(question, retrieved_chunks)
    except Exception as exc:
        return jsonify({"error": f"Answer generate karne mein error: {str(exc)}"}), 500

    return jsonify(result)


@app.route("/documents", methods=["GET"])
def documents():
    """Ab tak upload hue saare documents ki list deta hai."""
    docs = rag_core.list_uploaded_documents()
    return jsonify({"documents": docs, "total_chunks": rag_core.get_document_count()})


if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        print("WARNING: GEMINI_API_KEY .env file mein set nahi hai. .env.example ko copy karke .env banao.")
    app.run(debug=True, port=5000)
