# 🏛️ Sarkari Yojana Finder — AI-Powered Government Scheme Discovery

> A RAG-powered chatbot helping Indian citizens discover relevant government welfare schemes through natural language search.

## 🎯 Overview

India has hundreds of government welfare schemes across central and state levels, but 
citizens often don't know which ones they're eligible for or how to find them. Sarkari 
Yojana Finder solves this using a **Retrieval-Augmented Generation (RAG)** pipeline — 
users can ask questions in natural language (e.g. "schemes for farmers" or "education 
loans for students") and get accurate, grounded answers retrieved from a curated scheme database.

## 🧠 Why This Project Matters

This project demonstrates practical **RAG engineering** skills:
- **Semantic search** — vector-based retrieval finds relevant schemes even with varied phrasing
- **Grounded generation** — answers are based on retrieved scheme data, not LLM guesswork
- **Real-world civic tech** — applying AI to improve access to public welfare information

## ✨ Key Features

| Feature | Description |
|---|---|
| 🔍 Semantic Scheme Search | Natural language queries matched to relevant schemes via vector similarity |
| 🤖 AI-Generated Answers | Gemini synthesizes clear, grounded responses from retrieved scheme data |
| 📚 Curated Scheme Database | ChromaDB-backed vector store of Indian government welfare schemes |
| 💬 Conversational Interface | Simple chat-based UX for easy scheme discovery |

## 🧠 AI/RAG Architecture

| Component | Role |
|---|---|
| **ChromaDB** | Vector database storing embedded scheme data for semantic retrieval |
| **Google Gemini** | Generates natural language answers grounded in retrieved context |
| **google-genai SDK** | Modern Google GenAI SDK for embeddings and generation |
| **rag_core.py** | Core retrieval + generation pipeline orchestration |

## 🛠️ Tech Stack

**Backend:** Python, Flask  
**AI:** Google Gemini, ChromaDB (vector search)  
**SDK:** google-genai  
**Frontend:** HTML, CSS, JavaScript

## 📂 Project Structure
sarkari-yojana-finder/
├── app.py                 # Main Flask application
├── rag_core.py              # RAG pipeline: retrieval + generation
├── add_data.py               # Script to populate the vector database
├── data/                     # Source scheme data
├── chroma_db/                # Vector database (generated, not tracked)
├── templates/                # Chat interface templates
└── static/                    # CSS, JS

## 🚀 Getting Started

### 1. Install Dependencies
```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

**Note:** ChromaDB on Python 3.13 requires:
```bash
pip install chromadb --only-binary :all:
```

### 2. Configure Environment
Create a `.env` file in the root directory with:
GEMINI_API_KEY=your_gemini_key_here

### 3. Populate the Database
```bash
python add_data.py
```

### 4. Run the App
```bash
python app.py
```
Visit: http://localhost:5000

## 📌 Roadmap / Future Improvements

- [ ] Eligibility-based filtering (age, income, occupation)
- [ ] Multilingual support for regional language users
- [ ] Direct application links for each scheme

## 👤 About the Developer

Built by **Imran Khan** — BCA final-year student specializing in **Applied AI Engineering** 
and **RAG systems**, focused on building AI tools that improve access to public services 
and information for underserved communities.

📫 Open to **AI Solution Developer** / **Applied AI Engineer** roles.  
🔗 [GitHub](https://github.com/Rev-ImranKhan)