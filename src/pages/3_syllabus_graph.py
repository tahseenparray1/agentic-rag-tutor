import streamlit as st
import os
import json
import sys
from collections import defaultdict, deque
from streamlit_agraph import agraph, Node, Edge, Config

src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from utils import check_active_workspace

PROJECT_NAME = check_active_workspace(
    page_title="🌳 Syllabus Graph",
    welcome_message="To get started, please **create a new workspace** using the menu on the left sidebar. Once you create a project workspace, you will unlock full access to your curriculum tree."
)
DATA_DIR = st.session_state.get("data_dir", "")
DB_DIR = st.session_state.get("db_dir", "")

st.title(f"🌳 Syllabus Graph: {PROJECT_NAME.replace('_', ' ')}")
st.caption(f"Visualizing concepts and prerequisites for: {PROJECT_NAME}")

from utils import load_prereq_tree
graph = load_prereq_tree(DB_DIR)

if not graph.get("nodes"):
    st.info("No concept nodes found in the syllabus tree. Try re-running the ingestion pipeline with valid textbook contents.")
    st.stop()

adj = defaultdict(list)
indegree = defaultdict(int)

for node in graph.get("nodes", []):
    name = node.get("concept_name")
    if name:
        indegree[name] = 0

for edge in graph.get("edges", []):
    u = edge.get("prerequisite")
    v = edge.get("target")
    if u and v:
        adj[u].append(v)
        indegree[v] += 1

# Kahn's Algorithm + Level Assignment
queue = deque()
levels = {}

for node in indegree:
    if indegree[node] == 0:
        queue.append(node)
        levels[node] = 0

while queue:
    u = queue.popleft()
    for v in adj[u]:
        levels[v] = max(levels.get(v, 0), levels[u] + 1)
        indegree[v] -= 1
        if indegree[v] == 0:
            queue.append(v)

st.markdown("### 🗺️ Curriculum Learning Roadmap")
st.write("Click any node on the graph below to inspect its descriptions, prerequisite dependencies, and subsequent unlocking lessons in the sidebar.")

from tutor_engine import load_student_profile
profile = load_student_profile(DB_DIR)

col1, col2, col3, col4 = st.columns(4)
col1.markdown("<div style='background-color:#10b981; padding:8px 5px; border-radius:6px; text-align:center; color:white; font-size:0.85em; font-weight:bold;'>🟢 Mastered<br><span style='font-size:0.8em; font-weight:normal; opacity:0.9;'>Completed Quiz</span></div>", unsafe_allow_html=True)
col2.markdown("<div style='background-color:#3b82f6; padding:8px 5px; border-radius:6px; text-align:center; color:white; font-size:0.85em; font-weight:bold;'>🔵 In Progress<br><span style='font-size:0.8em; font-weight:normal; opacity:0.9;'>Active Study</span></div>", unsafe_allow_html=True)
col3.markdown("<div style='background-color:#6366f1; padding:8px 5px; border-radius:6px; text-align:center; color:white; font-size:0.85em; font-weight:bold;'>🟣 Unlocked<br><span style='font-size:0.8em; font-weight:normal; opacity:0.9;'>Ready to Learn</span></div>", unsafe_allow_html=True)
col4.markdown("<div style='background-color:#64748b; padding:8px 5px; border-radius:6px; text-align:center; color:white; font-size:0.85em; font-weight:bold;'>🔒 Locked<br><span style='font-size:0.8em; font-weight:normal; opacity:0.9;'>Requires Prerequisites</span></div>", unsafe_allow_html=True)

st.write("")

incoming_prereqs = defaultdict(list)
for edge in graph.get("edges", []):
    p = edge.get("prerequisite")
    t = edge.get("target")
    if p and t:
        incoming_prereqs[t].append(p)

nodes = []
for node in graph.get("nodes", []):
    name = node.get("concept_name", "")
    if not name:
        continue
    desc = node.get("description", "No description available.")
    level = levels.get(name, 0)

    is_mastered = name in profile.get("mastered_concepts", [])
    is_in_progress = name in profile.get("in_progress_concepts", [])
    unmet_prereqs = [p for p in incoming_prereqs[name] if p not in profile.get("mastered_concepts", [])]
    is_locked = len(unmet_prereqs) > 0 and not is_mastered

    if is_mastered:
        bg_color = "#10b981"
        border_color = "#047857"
        display_label = f"🟢 {name}"
        status_text = "Mastered"
    elif is_in_progress:
        bg_color = "#3b82f6"
        border_color = "#1d4ed8"
        display_label = f"🔵 {name}"
        status_text = "In Progress"
    elif is_locked:
        bg_color = "#475569"
        border_color = "#334155"
        display_label = f"🔒 {name}"
        status_text = "Locked"
    else:
        status_text = "Unlocked"
        display_label = name
        if level == 0:
            bg_color = "#6366f1"
            border_color = "#4338ca"
        elif level == 1:
            bg_color = "#8b5cf6"
            border_color = "#6d28d9"
        else:
            bg_color = "#f97316"
            border_color = "#c2410c"

    nodes.append(
        Node(
            id=name,
            label=display_label,
            title=f"Status: {status_text} • Level {level}\n\n{desc}",
            level=level,
            shape="box",
            font={
                "color": "#ffffff",
                "size": 13,
                "face": "Helvetica, Arial, sans-serif",
                "bold": True
            },
            color={
                "background": bg_color,
                "border": border_color,
                "highlight": {
                    "background": bg_color,
                    "border": "#ffffff"
                }
            },
            borderWidth=2,
            margin=12,
        )
    )

edges = []
for edge in graph.get("edges", []):
    source = edge.get("prerequisite")
    target = edge.get("target")
    if source and target:
        edges.append(
            Edge(
                source=source,
                target=target,
                color="#94a3b8",
                smooth={
                    "type": "cubicBezier",
                    "forceDirection": "vertical",
                    "roundness": 0.5
                }
            )
        )

config = Config(
    width="100%",
    height=750,
    directed=True,
    physics=False,
    hierarchical=True,
    levelSeparation=240,
    nodeSpacing=380,
    treeSpacing=380,
    nodeHighlightBehavior=True,
    highlightColor="#ffffff",
)

selected = agraph(
    nodes=nodes,
    edges=edges,
    config=config
)

if selected:
    node = next(
        (n for n in graph.get("nodes", []) if n.get("concept_name") == selected), 
        None
    )
    
    if node:
        level = levels.get(selected, 0)
        
        is_mastered = selected in profile.get("mastered_concepts", [])
        is_in_progress = selected in profile.get("in_progress_concepts", [])
        unmet_prereqs = [p for p in incoming_prereqs[selected] if p not in profile.get("mastered_concepts", [])]
        is_locked = len(unmet_prereqs) > 0 and not is_mastered

        if is_mastered:
            badge_color = "#10b981"
            status_desc = "🟢 Mastered"
        elif is_in_progress:
            badge_color = "#3b82f6"
            status_desc = "🔵 In Progress"
        elif is_locked:
            badge_color = "#475569"
            status_desc = f"🔒 Locked (Requires: {', '.join(unmet_prereqs)})"
        else:
            badge_color = "#6366f1"
            status_desc = "🟣 Unlocked"

        st.sidebar.markdown(f"""
        <div style='background-color:rgba(255,255,255,0.05); padding:15px; border-radius:8px; border-left:5px solid {badge_color}; margin-bottom:15px;'>
            <h3 style='margin:0; font-size:1.25em;'>📚 {selected}</h3>
            <span style='background-color:{badge_color}; color:white; padding:2px 6px; border-radius:4px; font-size:0.75em; font-weight:bold;'>{status_desc}</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.sidebar.info(node.get("description", "No description available."))

        st.sidebar.markdown("### ⚡ Concept Actions")
        
        if st.sidebar.button("📖 Teach Me This Concept", use_container_width=True, disabled=is_locked):
            st.session_state["classroom_active_concept"] = selected
            st.session_state["classroom_auto_trigger"] = f"Please explain the concept of {selected} and provide a lesson."
            st.switch_page("pages/2_live_classroom.py")
        if is_locked:
            st.sidebar.caption("⚠️ Complete prerequisites to unlock study lessons.")

        if st.sidebar.button("📝 Take Practice Diagnostic", use_container_width=True, disabled=is_locked):
            st.session_state["classroom_active_concept"] = selected
            # No auto_trigger — student sees the quiz question and types their own answer
            st.session_state[f"active_quiz_{PROJECT_NAME}"] = {
                "questions": [f"Explain the concept of '{selected}' in your own words: its definition, purpose, and a concrete example."],
                "question": f"Explain '{selected}'.",
                "topic": selected,
            }
            st.switch_page("pages/2_live_classroom.py")

        if st.sidebar.button("🔍 Review Prerequisite Foundations", use_container_width=True):
            st.sidebar.markdown("#### 🧱 Foundation Prerequisites Check:")
            if incoming_prereqs[selected]:
                for p in incoming_prereqs[selected]:
                    p_status = "🟢 Mastered" if p in profile.get("mastered_concepts", []) else "❌ Unmet"
                    st.sidebar.write(f"- **{p}** ({p_status})")
            else:
                st.sidebar.write("This is a baseline foundational concept with no prerequisites!")

        prereqs = incoming_prereqs[selected]
        next_topics = [
            e.get("target")
            for e in graph.get("edges", [])
            if e.get("prerequisite") == selected and e.get("target")
        ]

        st.sidebar.markdown("### 🔗 Prerequisite Lessons")
        if prereqs:
            for p in prereqs:
                p_emoji = "🟢" if p in profile.get("mastered_concepts", []) else "🔴"
                st.sidebar.markdown(f"- {p_emoji} **{p}**")
        else:
            st.sidebar.markdown("*None (Start here!)*")

        st.sidebar.markdown("### 🚀 Subsequent Unlocks")
        if next_topics:
            for t in next_topics:
                t_emoji = "🔒" if t in incoming_prereqs and any(p not in profile.get("mastered_concepts", []) for p in incoming_prereqs[t]) else "🟣"
                st.sidebar.markdown(f"- {t_emoji} **{t}**")
        else:
            st.sidebar.markdown("*None (Milestone reached!)*")
