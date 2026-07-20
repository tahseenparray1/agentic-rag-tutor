# 🎓 Agentic RAG Tutor

An intelligent, AI-powered adaptive tutoring system that transforms any textbook PDF into a personalized, structured learning experience using multi-agent RAG (Retrieval-Augmented Generation).

## ✨ Features

- **📂 Document Hub** — Upload textbook PDFs, run the ingestion pipeline, and compile an auto-generated curriculum prerequisite graph
- **💬 Live Classroom** — Interactive AI tutoring with context-aware lessons, quizzes, and auto-grading powered by RAG retrieval
- **🌳 Syllabus Graph** — Visual interactive DAG showing concept dependencies, mastery status, and learning path progression
- **📊 Student Analytics** — Track mastery progress, quiz scores, grading critiques, and remediation history

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                     │
│   Document Hub │ Live Classroom │ Graph │ Analytics       │
├──────────────────────────────────────────────────────────┤
│                    Tutor Engine (LCEL)                    │
│         Tutor Agent (teach)  │  Grader Agent (grade)     │
├──────────────────────────────────────────────────────────┤
│  Local Ollama (Qwen3 4B)    │  Google Gemini 2.5 Flash   │
│  Concept Extraction          │  Teaching & Grading        │
├──────────────────────────────────────────────────────────┤
│  ChromaDB (Vector Store)    │  HuggingFace BGE Embeddings│
│  RAG Retrieval               │  Semantic Search           │
└──────────────────────────────────────────────────────────┘
```

### Hybrid Local + Cloud AI

| Component | Model | Purpose |
|---|---|---|
| Concept Extraction | Ollama `qwen3:4b-instruct` (local) | Cost-free PDF parsing and topic mining |
| Tutoring & Grading | Google Gemini 2.5 Flash (cloud) | High-quality structured lesson delivery and quiz evaluation |
| Embeddings | HuggingFace `BAAI/bge-base-en-v1.5` (local) | Semantic vector embeddings for RAG retrieval |

## 🚀 Getting Started

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) (package manager)
- [Ollama](https://ollama.com/) (local LLM runtime)
- A [Google Gemini API key](https://aistudio.google.com/apikey)

### Installation

```bash
# Clone the repository
git clone https://github.com/tahseenparray1/agentic-rag-tutor.git
cd agentic-rag-tutor

# Install dependencies
uv sync

# Pull the local extraction model
ollama pull qwen3:4b-instruct

# Configure your API key
echo "GEMINI_API_KEY=your_key_here" > .env
```

### Running the App

```bash
# Start Ollama in the background
ollama serve &

# Launch the Streamlit app
uv run python main.py
```

Then open `http://localhost:8501` in your browser.

## 📁 Project Structure

```
agentic-rag-tutor/
├── main.py                          # App entry point (launches Streamlit)
├── pyproject.toml                   # Dependencies and project config
├── .gitignore
├── src/
│   ├── app.py                       # Streamlit app with workspace manager
│   ├── tutor_engine.py              # Core tutoring & grading LCEL chains
│   ├── graph_builder.py             # PDF ingestion, concept extraction, DAG compilation
│   ├── utils.py                     # Shared utility functions
│   ├── pages/
│   │   ├── 1_document_hub.py        # PDF upload and graph compilation UI
│   │   ├── 2_live_classroom.py      # Chat-based tutoring interface
│   │   ├── 3_syllabus_graph.py      # Interactive prerequisite graph visualization
│   │   └── 4_student_analytics.py   # Mastery tracking and quiz logs
│   └── scripts/
│       └── benchmark_ollama.py      # Local model performance profiling
└── workspaces/                      # Per-project isolated data (gitignored)
```

## 🔧 How It Works

1. **Upload** textbook PDFs through the Document Hub
2. **Ingestion Pipeline** chunks the text, embeds it into ChromaDB, and uses Ollama to extract academic concepts
3. **Graph Compilation** sends extracted concepts to Gemini to build a prerequisite DAG, with DFS cycle-breaking
4. **Live Classroom** uses RAG to retrieve relevant textbook segments and Gemini to deliver structured lessons with quizzes
5. **Grading Agent** evaluates student answers, tracks mastery, and enforces prerequisite progression
6. **Analytics Dashboard** provides full visibility into learning progress and quiz performance

## 🛠️ Tech Stack

- **Frontend**: Streamlit, streamlit-agraph
- **LLM Orchestration**: LangChain (LCEL chains), Pydantic (structured outputs)
- **Cloud AI**: Google Gemini 2.5 Flash via `langchain-google-genai`
- **Local AI**: Ollama (Qwen3 4B Instruct)
- **Vector DB**: ChromaDB with HuggingFace BGE embeddings
- **PDF Processing**: PyPDF

## 📄 License

This project is for educational purposes.
