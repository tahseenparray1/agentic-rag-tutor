import streamlit as st
import os
import sys
from collections import defaultdict

src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from utils import check_active_workspace

PROJECT_NAME = check_active_workspace(
    page_title="📊 Student Analytics",
    welcome_message="To get started, please **create a new workspace** using the menu on the left sidebar. Once you create a project workspace, you will unlock full access to study analytics."
)
DATA_DIR = st.session_state.get("data_dir", "")
DB_DIR = st.session_state.get("db_dir", "")

st.title(f"📊 Student Analytics & Dashboard")
st.caption(f"Progress and performance logs for workspace: {PROJECT_NAME.replace('_', ' ')}")

from tutor_engine import load_student_profile
profile = load_student_profile(DB_DIR)

from utils import load_prereq_tree
graph = load_prereq_tree(DB_DIR)

nodes = graph.get("nodes", [])
total_concepts = len(nodes)

if total_concepts == 0:
    st.info("No concepts found in your syllabus tree yet. Complete document ingestion first!")
    st.stop()

mastered = set(profile.get("mastered_concepts", []))
in_progress = set(profile.get("in_progress_concepts", []))

incoming_prereqs = defaultdict(list)
for edge in graph.get("edges", []):
    incoming_prereqs[edge["target"]].append(edge["prerequisite"])

locked = set()
unlocked = set()

for node in nodes:
    name = node["concept_name"]
    if name in mastered:
        continue
    unmet = [p for p in incoming_prereqs[name] if p not in mastered]
    if unmet:
        locked.add(name)
    else:
        unlocked.add(name)

mastered_count = len(mastered)
in_progress_count = len(in_progress)
locked_count = len(locked)
unlocked_count = len(unlocked)

progress_percent = int((mastered_count / total_concepts) * 100)

st.subheader("📈 Overall Syllabus Progress")

col1, col2, col3 = st.columns(3)
col1.metric("Overall Mastery", f"{progress_percent}%", f"{mastered_count} of {total_concepts} Concepts")
col2.metric("In Progress", f"{in_progress_count}", "Active Concepts")
col3.metric("Locked Topics", f"{locked_count}", f"Requires Prerequisites")

st.progress(mastered_count / total_concepts)

st.subheader("📚 Mastery Ledger")

with st.expander("🟢 Mastered Concepts", expanded=True):
    if mastered:
        for m in sorted(list(mastered)):
            st.markdown(f"✅ **{m}**")
    else:
        st.write("No concepts mastered yet. Start study sessions in the classroom or take practice diagnostics!")

with st.expander("🔵 Concepts in Progress", expanded=True):
    active_study = in_progress.union(unlocked).difference(mastered)
    if active_study:
        for ip in sorted(list(active_study)):
            status_tag = "⚡ Study Started" if ip in in_progress else "🔓 Unlocked & Ready"
            st.markdown(f"- **{ip}** *({status_tag})*")
    else:
        st.write("No active topics. Select a topic on the syllabus graph to start studying!")

with st.expander("🔒 Locked Concepts", expanded=False):
    if locked:
        for l in sorted(list(locked)):
            reqs = incoming_prereqs[l]
            unmet_reqs = [r for r in reqs if r not in mastered]
            st.markdown(f"- 🔒 **{l}** *(Requires: {', '.join(unmet_reqs)})*")
    else:
        st.write("No locked concepts! All topics are unlocked and available for study.")

st.subheader("📝 Grading Agent Performance Logs")

attempts = []
for concept_name, attempts_list in profile.get("quiz_attempts", {}).items():
    for attempt in attempts_list:
        attempts.append(attempt)

attempts = sorted(attempts, key=lambda x: x.get("timestamp", ""), reverse=True)

if attempts:
    import pandas as pd
    
    table_data = []
    for att in attempts:
        table_data.append({
            "Timestamp": att.get("timestamp"),
            "Concept": att.get("concept_name", "Unknown"),
            "Score": f"{att.get('score')}%",
            "Result": "🟢 Pass" if att.get("is_pass") else "❌ Fail",
            "Student Answer": att.get("student_answer", "")
        })
    
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True)
    
    st.subheader("🔍 Detailed Quiz Feedback")
    for idx, att in enumerate(attempts[:5]):
        result_color = "green" if att.get("is_pass") else "red"
        result_str = "PASS" if att.get("is_pass") else "FAIL"
        
        with st.expander(f"{att.get('timestamp')} - {att.get('concept_name')} ({result_str} - {att.get('score')}%)"):
            st.markdown(f"**Quiz Question:** *{att.get('quiz_question')}*")
            st.markdown(f"**Your Answer:** *{att.get('student_answer')}*")
            st.markdown(f"**Grading Critique:** {att.get('critique')}")
            if att.get("remediation_advice"):
                st.info(f"💡 **Remediation Advice:** {att.get('remediation_advice')}")
else:
    st.info("No quiz attempts recorded yet. Submit quiz answers in the classroom to log grading critiques.")
