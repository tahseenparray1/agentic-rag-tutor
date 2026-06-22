import streamlit as st
import os
import sys

src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from utils import check_active_workspace

PROJECT_NAME = check_active_workspace(
    page_title="💬 Live Classroom",
    welcome_message="To get started, please **create a new workspace** using the menu on the left sidebar. Once you create a project workspace, you will unlock full access to the live classroom."
)
DATA_DIR = st.session_state.get("data_dir", "")
DB_DIR = st.session_state.get("db_dir", "")

st.title(f"💬 Live Classroom: {PROJECT_NAME.replace('_', ' ')}")
st.caption(f"Interactive AI tutor session for workspace: {PROJECT_NAME}")

graph_path = os.path.join(DB_DIR, "prereq_tree.json")
if not os.path.exists(graph_path):
    st.warning("⚠️ No active knowledge base found for this workspace.")
    st.write("Please go to **1. Ingestion Hub** to upload textbooks and compile your syllabus graph first.")
    st.stop()

st.markdown("""
    <style>
    .chat-bubble {
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 10px;
    }
    .quiz-box {
        background-color: rgba(99, 102, 241, 0.1);
        border-left: 4px solid #6366f1;
        padding: 15px;
        border-radius: 6px;
        margin-top: 10px;
    }
    </style>
""", unsafe_allow_html=True)

from tutor_engine import teach, grade, load_student_profile, save_chat_history, load_chat_history, clear_chat_history, save_quiz_state, load_quiz_state

chat_key = f"chat_messages_{PROJECT_NAME}"
quiz_key = f"active_quiz_{PROJECT_NAME}"
citation_key = f"last_citations_{PROJECT_NAME}"

# Load history and quiz state from disk the first time this session sees this workspace
if chat_key not in st.session_state:
    st.session_state[chat_key] = load_chat_history(DB_DIR)
if quiz_key not in st.session_state:
    st.session_state[quiz_key] = load_quiz_state(DB_DIR)  # None if no pending quiz
if citation_key not in st.session_state:
    st.session_state[citation_key] = ""

from utils import get_concepts_list
concepts_list = get_concepts_list(DB_DIR)

st.sidebar.subheader("📚 Context Control")

preset_concept = st.session_state.get("classroom_active_concept", "None")
selected_idx = 0
if preset_concept in concepts_list:
    selected_idx = concepts_list.index(preset_concept)

active_concept = st.sidebar.selectbox(
    "Active Target Concept",
    options=concepts_list,
    index=selected_idx
)
st.session_state["classroom_active_concept"] = active_concept

st.sidebar.divider()
if st.sidebar.button("🗑️ Clear Conversation", use_container_width=True):
    st.session_state[chat_key] = []
    st.session_state[quiz_key] = None
    st.session_state[citation_key] = ""
    clear_chat_history(DB_DIR)
    save_quiz_state(DB_DIR, None)  # also clear persisted quiz
    st.rerun()

msg_count = len(st.session_state[chat_key])
if msg_count > 0:
    st.sidebar.caption(f"💬 {msg_count} messages in session")

st.sidebar.subheader("📖 Source Citations")
citations = st.session_state.get(citation_key, "")
if citations:
    with st.sidebar.expander("Show Textbook Segments", expanded=True):
        st.caption("ChromaDB matching snippets used for current explanation:")
        st.write(citations)
else:
    st.sidebar.info("No citations retrieved yet.")

for msg in st.session_state[chat_key]:
    with st.chat_message(msg["role"]):
        if msg.get("content"):
            st.write(msg["content"])
        
        if "lesson" in msg:
            lesson = msg["lesson"]
            st.markdown(f"### 🎓 {lesson['topic_heading']}")
            st.write(lesson['lesson_content'])
            
            questions = lesson.get("quiz_questions") or []
            questions = [q for q in questions if q.strip()]
            questions_html = "".join([f"<li>{q}</li>" for q in questions])
            st.markdown(
                f'<div class="quiz-box">❓ <b>Check Your Understanding:</b><ul>{questions_html}</ul></div>',
                unsafe_allow_html=True
            )
            
        if "evaluation" in msg:
            eval_data = msg["evaluation"]
            score = eval_data.get("score", 0)
            is_pass = eval_data.get("is_pass", False)
            critique = eval_data.get("critique", "")
            remediation = eval_data.get("remediation_advice", "")
            
            if is_pass:
                st.success(f"🎉 **Graded Pass! Score: {score}%**\n\n{critique}")
            else:
                st.error(f"❌ **Graded Fail. Score: {score}%**\n\n**Critique:** {critique}\n\n**Remediation:** {remediation}")

submit_mode = "Ask Tutor a Question"
active_quiz = st.session_state[quiz_key]

if active_quiz:
    active_qs = active_quiz.get("questions") or [active_quiz.get("question", "")]
    active_qs = [q for q in active_qs if q.strip()]
    
    if len(active_qs) > 1:
        qs_formatted = "\n".join([f"{i+1}. {q}" for i, q in enumerate(active_qs)])
    else:
        qs_formatted = active_qs[0] if active_qs else ""
        
    st.info(f"📝 **Active Quiz Mode:** You have a pending check for **{active_quiz['topic']}**.\n\n*Questions:*\n{qs_formatted}")
    submit_mode = st.radio(
        "Response Action Mode:",
        options=["Answer Active Quiz", "Ask Tutor a Question instead"],
        horizontal=True
    )
    if submit_mode == "Ask Tutor a Question instead":
        st.caption("⚠️ Note: Switching mode leaves this concept in-progress until successfully answered.")

# auto_trigger is only used for lesson mode ("Teach Me This" from syllabus page).
# Diagnostic mode no longer auto-submits — the student types their own answer.
auto_trigger = st.session_state.pop("classroom_auto_trigger", None)
prompt_to_process = None

if auto_trigger and not auto_trigger.startswith("Diagnostic test"):
    prompt_to_process = auto_trigger

if not prompt_to_process:
    prompt_to_process = st.chat_input("Type your response or lesson question here...")

if prompt_to_process:
    with st.chat_message("user"):
        st.write(prompt_to_process)
    st.session_state[chat_key].append({"role": "user", "content": prompt_to_process})
    
    with st.chat_message("assistant"):
        with st.spinner("Tutor thinking..."):
            try:
                mode = "quiz" if (submit_mode == "Answer Active Quiz" and active_quiz) else "lesson"
                concept = active_concept if active_concept != "None" else ""

                if mode == "quiz" and active_quiz:
                    final_state = grade(
                        query=prompt_to_process,
                        db_dir=DB_DIR,
                        active_concept=concept,
                        quiz_data=active_quiz,
                    )
                else:
                    final_state = teach(
                        query=prompt_to_process,
                        db_dir=DB_DIR,
                        active_concept=concept,
                        chat_history=st.session_state[chat_key],  # full history — budget windowing in tutor_engine.py
                    )

                # Sync concept if prereq-redirect changed it
                returned_concept = final_state.get("active_concept") or ""
                if returned_concept and returned_concept != concept:
                    st.session_state["classroom_active_concept"] = returned_concept
                
                if mode == "quiz":
                    eval_data = final_state  # grade() returns the flat GradingResponse dict
                    score = eval_data.get("score", 0)
                    is_pass = eval_data.get("is_pass", False)
                    critique = eval_data.get("critique", "")
                    remediation = eval_data.get("remediation_advice", "")
                    
                    if is_pass:
                        st.success(f"🎉 **Graded Pass! Score: {score}%**\n\n{critique}")
                        st.session_state[quiz_key] = None
                        save_quiz_state(DB_DIR, None)  # clear persisted quiz on pass
                    else:
                        st.error(f"❌ **Graded Fail. Score: {score}%**\n\n**Critique:** {critique}\n\n**Remediation:** {remediation}")
                    
                    st.session_state[chat_key].append({
                        "role": "assistant",
                        "content": "",
                        "evaluation": eval_data
                    })
                else:
                    heading  = final_state.get("topic_heading", "Concept Lesson")
                    content  = final_state.get("lesson_content", "")
                    quiz_qs  = [q for q in final_state.get("quiz_questions", []) if q.strip()]

                    st.markdown(f"### 🎓 {heading}")
                    st.write(content)

                    questions_html = "".join([f"<li>{q}</li>" for q in quiz_qs])
                    st.markdown(
                        f'<div class="quiz-box">❓ <b>Check Your Understanding:</b><ul>{questions_html}</ul></div>',
                        unsafe_allow_html=True
                    )

                    st.session_state[citation_key] = final_state.get("retrieved_context", "")

                    st.session_state[quiz_key] = {
                        "questions": quiz_qs,
                        "question": "; ".join(quiz_qs),
                        "topic": heading,
                    }
                    save_quiz_state(DB_DIR, st.session_state[quiz_key])  # persist quiz

                    st.session_state[chat_key].append({
                        "role": "assistant",
                        "content": "",
                        "lesson": {
                            "topic_heading": heading,
                            "lesson_content": content,
                            "quiz_questions": quiz_qs,
                        }
                    })
                
                # Persist conversation to disk so it survives page refreshes
                save_chat_history(DB_DIR, st.session_state[chat_key])
                st.rerun()
                
            except Exception as e:
                st.error(f"Execution Error: {e}")
