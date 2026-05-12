import streamlit as st
import os

st.set_page_config(
    page_title="Agentic RAG Tutor",
    page_icon="🎓",
    layout="wide"
)

if "active_project" not in st.session_state:
    st.session_state.active_project = None
if "data_dir" not in st.session_state:
    st.session_state.data_dir = ""
if "db_dir" not in st.session_state:
    st.session_state.db_dir = ""

WORKSPACES_DIR = "workspaces"
os.makedirs(WORKSPACES_DIR, exist_ok=True)

with st.sidebar:
    st.header("🗂️ Workspaces")
    
    existing_projects = [f.name for f in os.scandir(WORKSPACES_DIR) if f.is_dir()]
    
    with st.expander("➕ Create New Project", expanded=not existing_projects):
        new_project_name = st.text_input("Project Name (e.g., 'C++ Masterclass')")
        if st.button("Create", use_container_width=True) and new_project_name:
            safe_name = new_project_name.replace(" ", "_")
            os.makedirs(os.path.join(WORKSPACES_DIR, safe_name, "data"), exist_ok=True)
            os.makedirs(os.path.join(WORKSPACES_DIR, safe_name, "db"), exist_ok=True)
            st.session_state.active_project = safe_name
            st.rerun()

    st.divider()

    if existing_projects:
        default_index = 0
        if st.session_state.active_project in existing_projects:
            default_index = existing_projects.index(st.session_state.active_project)

        active_project = st.selectbox(
            "Active Workspace", 
            options=existing_projects,
            index=default_index
        )
        
        st.session_state.active_project = active_project
        st.session_state.data_dir = os.path.join(WORKSPACES_DIR, active_project, "data")
        st.session_state.db_dir = os.path.join(WORKSPACES_DIR, active_project, "db")
    else:
        st.session_state.active_project = None
        st.warning("Create a workspace to begin.")

ingestion_page = st.Page("pages/1_document_hub.py", title="1. Document Hub", icon="📂")
chat_page = st.Page("pages/2_live_classroom.py", title="2. Live Classroom", icon="💬")
graph_page = st.Page("pages/3_syllabus_graph.py", title="3. Syllabus Graph", icon="🌳")
dashboard_page = st.Page("pages/4_student_analytics.py", title="4. Student Analytics", icon="📊")

pg = st.navigation([ingestion_page, chat_page, graph_page, dashboard_page])
pg.run()