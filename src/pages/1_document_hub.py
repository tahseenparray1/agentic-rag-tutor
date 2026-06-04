import streamlit as st
import os
import sys
import io
import json
import contextlib
import chromadb
from pypdf import PdfReader

src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from graph_builder import build_advanced_knowledge_graph

from utils import check_active_workspace

PROJECT_NAME = check_active_workspace(
    page_title="📂 Document Hub",
    welcome_message="To get started, please **create a new workspace** using the menu on the left sidebar. Once you create a project workspace, you will unlock full access to the document uploader, the local GPU vector processing pipelines, and your learning graph trees."
)
DATA_DIR = st.session_state.get("data_dir", "")
DB_DIR = st.session_state.get("db_dir", "")

st.title(f"📂 Document Hub: {PROJECT_NAME.replace('_', ' ')}")
st.caption(f"Managing resources for workspace: {DATA_DIR}")

# --- Ollama health check ---
try:
    import ollama as _ollama
    _ollama.list()
    _ollama_ok = True
except Exception:
    _ollama_ok = False

if not _ollama_ok:
    st.warning(
        "⚠️ **Ollama is not reachable.** "
        "The graph compilation pipeline requires a local Ollama instance for concept extraction.\n\n"
        "**Fix:** Run `ollama serve` in a terminal, then pull the model with "
        "`ollama pull qwen3:4b-instruct`.",
        icon="🤖"
    )

st.markdown("""
    <style>
    .stButton>button {
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        color: white;
        border: none;
        padding: 10px 24px;
        font-weight: bold;
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
    }
    .document-card {
        background-color: #1e293b;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 8px;
        border: 1px solid #334155;
    }
    </style>
""", unsafe_allow_html=True)

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("📤 Upload Textbooks")
    st.write("Add your syllabus or textbook PDF files to feed the tutor knowledge base.")
    
    uploaded_files = st.file_uploader(
        "Upload PDF files", 
        type=["pdf"], 
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    
    if uploaded_files:
        saved_any = False
        for uploaded_file in uploaded_files:
            os.makedirs(DATA_DIR, exist_ok=True)
            dest_path = os.path.join(DATA_DIR, uploaded_file.name)
            if not os.path.exists(dest_path) or os.path.getsize(dest_path) != uploaded_file.size:
                with open(dest_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                saved_any = True
        
        if saved_any:
            st.success("🎉 New textbooks successfully uploaded!")
            st.rerun()

with col_right:
    st.subheader("📚 Managed Documents")
    
    if os.path.exists(DATA_DIR):
        pdf_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.pdf')]
    else:
        pdf_files = []
        
    if pdf_files:
        for idx, pdf in enumerate(pdf_files):
            file_path = os.path.join(DATA_DIR, pdf)
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            
            with st.container():
                c_name, c_del = st.columns([0.8, 0.2])
                c_name.markdown(f"📄 **{pdf}**  \n`Size: {file_size_mb:.2f} MB`", unsafe_allow_html=True)
                if c_del.button("🗑️", key=f"del_{idx}_{pdf}"):
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except OSError as e:
                        st.warning(f"Could not delete file '{file_path}': {e}")
                        
                    try:
                        import chromadb
                        chroma_client = chromadb.PersistentClient(path=DB_DIR)
                        collection = chroma_client.get_collection("course_material")
                        collection.delete(where={"source_file": pdf})
                    except Exception as e:
                        st.warning(f"Could not purge vector chunks for '{pdf}': {e}")
                        
                    checkpoint_path = os.path.join(DB_DIR, "extracted_concepts_checkpoint.json")
                    if os.path.exists(checkpoint_path):
                        try:
                            with open(checkpoint_path, "r") as f:
                                checkpoint = json.load(f)
                            if isinstance(checkpoint, dict) and "completed_files" in checkpoint:
                                if pdf in checkpoint["completed_files"]:
                                    del checkpoint["completed_files"][pdf]
                                    with open(checkpoint_path, "w") as f:
                                        json.dump(checkpoint, f, indent=4)
                        except (json.JSONDecodeError, OSError) as e:
                            st.warning(f"Could not update checkpoint file: {e}")
                            
                    tree_output_path = os.path.join(DB_DIR, "prereq_tree.json")
                    if os.path.exists(tree_output_path):
                        try:
                            os.remove(tree_output_path)
                        except OSError as e:
                            st.warning(f"Could not remove prerequisite tree: {e}")
                            
                    st.success(f"Removed {pdf} and synchronized database cleanly.")
                    st.rerun()
    else:
        st.info("No documents uploaded to this workspace yet. Use the uploader on the left to add materials.")

st.divider()

st.subheader("⚙️ Graph Compilation Pipeline")
st.write("Run the offline ingestion model pipeline to parse textbook structures, extract logical concepts, and compile the Prerequisite Syllabus Tree.")

graph_path = os.path.join(DB_DIR, "prereq_tree.json")
graph_exists = os.path.exists(graph_path)

col_info, col_action = st.columns([0.7, 0.3])

with col_info:
    if graph_exists:
        st.success("✅ A Prerequisite Syllabus Tree has been generated for this workspace.")
    else:
        st.warning("⚠️ No active Syllabus Tree exists. Please run the compilation pipeline below.")

# Custom terminal redirect class to show logs in real-time
class StreamlitConsoleRedirect:
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.buffer = []

    def write(self, text):
        if text:
            # We strip trailing newlines to keep output clean, but keep standard indentation
            self.buffer.append(text)
            # Keep only last 100 entries to prevent rendering slowdowns
            if len(self.buffer) > 100:
                self.buffer = self.buffer[-100:]
            self.placeholder.code("".join(self.buffer))
            
    def flush(self):
        pass

if col_action.button("🚀 Compile Syllabus Graph", use_container_width=True):
    if not pdf_files:
        st.error("Abort: No PDF documents available inside this workspace.")
    else:
        status_box = st.status("Initializing Ingestion Engines...", expanded=True)
        console_placeholder = st.empty()
        
        old_stdout = sys.stdout
        sys.stdout = StreamlitConsoleRedirect(console_placeholder)
        
        try:
            status_box.update(label="🚀 Indexing & Parsing documents...", state="running")
            
            build_advanced_knowledge_graph(data_dir=DATA_DIR, db_dir=DB_DIR)
            
            status_box.update(label="✅ Graph Compilation Complete!", state="complete", expanded=False)
            st.success("🎉 Syllabus hierarchy, vector embeddings, and concept relationships successfully compiled!")
            st.balloons()
            st.rerun()
        except Exception as e:
            status_box.update(label="❌ Pipeline Failed!", state="error")
            st.error(f"Ingestion failed with error: {e}")
        finally:
            sys.stdout = old_stdout