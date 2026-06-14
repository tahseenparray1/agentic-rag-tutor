import os
import json
import time
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
    raise ValueError("❌ GEMINI_API_KEY missing from your .env file!")

# langchain-google-genai reads GOOGLE_API_KEY; copy GEMINI_API_KEY if needed
if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


# ---------------------------------------------------------------------------
# Pydantic output schemas
# ---------------------------------------------------------------------------

class StructuredLesson(BaseModel):
    topic_heading: str = Field(description="The specific academic concept being taught.")
    lesson_content: str = Field(description="A complete, step-by-step lesson. Must end with a full sentence.")
    quiz_questions: List[str] = Field(description="2–3 check-for-understanding questions based only on lesson_content.")

class GradingResponse(BaseModel):
    is_pass: bool = Field(description="True if the student scored >= 80%.")
    score: float = Field(description="Score from 0.0 to 100.0.")
    critique: str = Field(description="Detailed feedback explaining the grade and correcting any mistakes.")
    remediation_advice: Optional[str] = Field(default="", description="Which prerequisite to review if they failed.")


# ---------------------------------------------------------------------------
# LangChain LCEL chains
# ---------------------------------------------------------------------------

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)

tutor_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a patient, expert AI tutor in a structured academic course. "
     "Deliver a complete lesson on the target concept using the provided textbook context. "
     "Write in full sentences. Your quiz questions must only test what you explicitly taught."),
    ("human", "{input}"),
])
tutor_chain = tutor_prompt | llm.with_structured_output(StructuredLesson)

grader_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an expert academic grader. Grade the student's answer for accuracy, "
     "application, and reasoning. If they fail (score < 80%), suggest the specific "
     "prerequisite concept they should review."),
    ("human", "{input}"),
])
grader_chain = grader_prompt | llm.with_structured_output(GradingResponse)


# ---------------------------------------------------------------------------
# Student profile persistence
# ---------------------------------------------------------------------------

def _profile_path(db_dir: str) -> str:
    return os.path.join(db_dir, "student_profile.json")

def load_student_profile(db_dir: str) -> dict:
    path = _profile_path(db_dir)
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
            data.setdefault("mastered_concepts", [])
            data.setdefault("in_progress_concepts", [])
            data.setdefault("quiz_attempts", {})
            data.setdefault("active_concept", "")
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"mastered_concepts": [], "in_progress_concepts": [], "quiz_attempts": {}, "active_concept": ""}

def save_student_profile(db_dir: str, profile: dict):
    os.makedirs(db_dir, exist_ok=True)
    with open(_profile_path(db_dir), "w") as f:
        json.dump(profile, f, indent=4)


# ---------------------------------------------------------------------------
# Chat history persistence
# ---------------------------------------------------------------------------

HISTORY_FILE = "chat_history.json"
HISTORY_CHAR_BUDGET = 4000  # ~1 000 tokens — enough for 8-15 typical messages

def save_chat_history(db_dir: str, messages: list) -> None:
    """Persist the full Streamlit message list to disk."""
    os.makedirs(db_dir, exist_ok=True)
    with open(os.path.join(db_dir, HISTORY_FILE), "w") as f:
        json.dump(messages, f, indent=2)

def load_chat_history(db_dir: str) -> list:
    """Restore saved message list, or return empty list on first run."""
    path = os.path.join(db_dir, HISTORY_FILE)
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

def clear_chat_history(db_dir: str) -> None:
    """Delete the persisted history file."""
    path = os.path.join(db_dir, HISTORY_FILE)
    if os.path.exists(path):
        os.remove(path)

def _build_history_str(messages: list) -> str:
    """
    Build a conversation string from messages while staying within HISTORY_CHAR_BUDGET.
    
    Strategy: extract text from every message (including lesson summaries), then
    walk backwards from the most recent, adding lines until the budget is exhausted.
    This ensures the LLM always sees the most recent context, and older exchanges
    fall off naturally as the conversation grows.
    """
    lines = []
    for msg in messages:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        # For assistant lesson messages, include a concise summary instead of empty string
        if not content and "lesson" in msg:
            lesson = msg["lesson"]
            heading = lesson.get("topic_heading", "")
            snippet = lesson.get("lesson_content", "")[:150].rstrip()
            content = f"[Lesson on '{heading}']: {snippet}..."
        if content:
            lines.append(f"{role}: {content}")

    # Walk newest → oldest, collect until budget exhausted, then reverse
    selected, budget = [], HISTORY_CHAR_BUDGET
    for line in reversed(lines):
        if budget <= 0:
            break
        selected.append(line)
        budget -= len(line)

    return "\n".join(reversed(selected)) or "(No prior conversation)"

QUIZ_FILE = "active_quiz.json"

def save_quiz_state(db_dir: str, quiz: dict | None) -> None:
    """Persist the active quiz dict to disk (or clear it if None)."""
    path = os.path.join(db_dir, QUIZ_FILE)
    os.makedirs(db_dir, exist_ok=True)
    if quiz is None:
        if os.path.exists(path):
            os.remove(path)
    else:
        with open(path, "w") as f:
            json.dump(quiz, f, indent=2)

def load_quiz_state(db_dir: str) -> dict | None:
    """Restore the active quiz from disk, or return None if none pending."""
    path = os.path.join(db_dir, QUIZ_FILE)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Prerequisite tree helpers
# ---------------------------------------------------------------------------

def _load_edges(db_dir: str) -> list:
    path = os.path.join(db_dir, "prereq_tree.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("edges", [])
    except (json.JSONDecodeError, OSError):
        return []

def get_all_prereqs(concept: str, edges: list) -> set:
    """Recursively collect every prerequisite for a concept."""
    prereqs, queue, visited = set(), [concept], set()
    while queue:
        curr = queue.pop(0)
        if curr in visited:
            continue
        visited.add(curr)
        for edge in edges:
            if edge["target"] == curr:
                prereqs.add(edge["prerequisite"])
                queue.append(edge["prerequisite"])
    return prereqs

def _resolve_concept(requested: str, mastered: list, edges: list) -> tuple[str, str]:
    """
    If the requested concept has unmastered prerequisites, return the earliest
    one the student should tackle first, along with a redirect note.
    Returns (concept_to_teach, redirect_note).
    """
    all_prereqs = get_all_prereqs(requested, edges)
    unmastered = [p for p in all_prereqs if p not in mastered]
    if not unmastered:
        return requested, ""

    # Find the earliest prerequisite: one whose own prerequisites are all mastered
    for candidate in unmastered:
        if all(p in mastered for p in get_all_prereqs(candidate, edges)):
            note = (
                f"🔔 **Roadmap Redirect:** Before **{requested}**, "
                f"we need to cover **{candidate}** first.\n\n"
            )
            return candidate, note

    return requested, ""


# ---------------------------------------------------------------------------
# RAG retrieval
# ---------------------------------------------------------------------------

def _retrieve_context(query: str, db_dir: str) -> str:
    try:
        embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en-v1.5")
        vectorstore = Chroma(
            persist_directory=db_dir,
            embedding_function=embeddings,
            collection_name="course_material",
        )
        docs = vectorstore.as_retriever(search_kwargs={"k": 3}).invoke(query)
        return "\n\n--- TEXTBOOK SEGMENT ---\n\n".join(d.page_content for d in docs)
    except Exception as e:
        return f"(No context retrieved: {e})"


# ---------------------------------------------------------------------------
# Public API — called directly from 2_live_classroom.py
# ---------------------------------------------------------------------------

def teach(query: str, db_dir: str, active_concept: str, chat_history: list) -> dict:
    """
    Retrieves RAG context and delivers a structured lesson via tutor_chain.
    Handles prerequisite redirects and updates the student profile.
    Returns the StructuredLesson as a dict plus 'retrieved_context' and 'active_concept'.
    """
    edges = _load_edges(db_dir)
    profile = load_student_profile(db_dir)
    mastered = profile["mastered_concepts"]

    redirect_note = ""
    if active_concept and active_concept != "None":
        active_concept, redirect_note = _resolve_concept(active_concept, mastered, edges)

    rag_context = _retrieve_context(
        f"{active_concept}: {query}" if active_concept else query,
        db_dir,
    )

    # Build conversation context string within character budget
    history_str = _build_history_str(chat_history or [])
    # Build the concept-aware prereq summary
    direct_prereqs = [e["prerequisite"] for e in edges if e["target"] == active_concept]
    mastered_prereqs = [p for p in direct_prereqs if p in mastered]
    pending_prereqs  = [p for p in direct_prereqs if p not in mastered]

    user_input = f"""
--- CURRICULUM STATE ---
Target Concept: {active_concept or 'General Question'}
Mastered Prerequisites: {', '.join(mastered_prereqs) or 'None'}
Pending Prerequisites:  {', '.join(pending_prereqs) or 'None'}
Overall Mastered:       {', '.join(mastered) or 'None'}

--- CONVERSATION HISTORY ---
{history_str}

--- TEXTBOOK CONTEXT ---
{rag_context}

--- STUDENT QUERY ---
{query}
"""

    lesson: StructuredLesson = tutor_chain.invoke({"input": user_input})
    result = lesson.model_dump()

    if redirect_note:
        result["lesson_content"] = redirect_note + result["lesson_content"]

    # Update profile: mark concept as in-progress
    if active_concept:
        profile = load_student_profile(db_dir)
        if active_concept not in profile["mastered_concepts"] and active_concept not in profile["in_progress_concepts"]:
            profile["in_progress_concepts"].append(active_concept)
        profile["active_concept"] = active_concept
        save_student_profile(db_dir, profile)

    result["retrieved_context"] = rag_context
    result["active_concept"] = active_concept
    return result


def grade(query: str, db_dir: str, active_concept: str, quiz_data: dict) -> dict:
    """
    Grades the student's answer via grader_chain and updates mastery in the profile.
    Returns the GradingResponse as a dict.
    """
    edges = _load_edges(db_dir)
    direct_prereqs = [e["prerequisite"] for e in edges if e["target"] == active_concept]
    questions = quiz_data.get("questions") or [quiz_data.get("question", "Explain the concept.")]
    topic = quiz_data.get("topic", active_concept)

    user_input = f"""
Topic: {topic}
Prerequisite Foundations: {', '.join(direct_prereqs) or 'None'}

Quiz Questions Asked:
{chr(10).join(f"{i+1}. {q}" for i, q in enumerate(questions))}

Student's Answer: {query}
"""

    evaluation: GradingResponse = grader_chain.invoke({"input": user_input})
    result = evaluation.model_dump()

    # Persist attempt and update mastery
    if active_concept:
        profile = load_student_profile(db_dir)

        attempt = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "concept_name": active_concept,
            "quiz_question": "; ".join(questions),
            "student_answer": query,
            "score": result["score"],
            "is_pass": result["is_pass"],
            "critique": result["critique"],
            "remediation_advice": result.get("remediation_advice", ""),
        }
        profile["quiz_attempts"].setdefault(active_concept, []).append(attempt)

        if result["is_pass"]:
            if active_concept in profile["in_progress_concepts"]:
                profile["in_progress_concepts"].remove(active_concept)
            if active_concept not in profile["mastered_concepts"]:
                profile["mastered_concepts"].append(active_concept)
            profile["active_concept"] = ""
            result["critique"] += f"\n\n🏆 **Concept Mastered!** '{active_concept}' is now complete!"
        else:
            if active_concept not in profile["in_progress_concepts"] and active_concept not in profile["mastered_concepts"]:
                profile["in_progress_concepts"].append(active_concept)

        save_student_profile(db_dir, profile)

    return result