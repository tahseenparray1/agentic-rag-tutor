import streamlit as st
import os
import json

def check_active_workspace(page_title: str, welcome_message: str) -> str:
    project_name = st.session_state.get("active_project", "")
    if not project_name:
        st.title(page_title)
        st.caption("Workspace Manager Gateway")
        st.info(f"### 🛠️ Welcome to the {page_title.split(':')[-1].strip() if ':' in page_title else page_title}!")
        st.write(welcome_message)
        st.stop()
    return project_name

def load_prereq_tree(db_dir: str) -> dict:
    graph_path = os.path.join(db_dir, "prereq_tree.json")
    if not os.path.exists(graph_path):
        st.warning("⚠️ No compiled syllabus tree found for this workspace.")
        st.write("Please go to **1. Ingestion Hub** to run the compilation pipeline and build your tree.")
        st.stop()
    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        st.error(f"Failed to load syllabus graph: {e}")
        st.stop()

def get_concepts_list(db_dir: str) -> list:
    graph_path = os.path.join(db_dir, "prereq_tree.json")
    if not os.path.exists(graph_path):
        return ["None"]
    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            graph = json.load(f)
            return ["None"] + [n["concept_name"] for n in graph.get("nodes", [])]
    except (json.JSONDecodeError, OSError):
        return ["None"]
