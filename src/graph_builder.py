import os
import json
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from pypdf import PdfReader
import ollama
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("❌ CRITICAL: GEMINI_API_KEY not found in your local .env file!")


class ConceptList(BaseModel):
    concepts: List[str] = Field(
        description=(
            "A list of core academic concept titles found in the text block. "
            "Each item should be a keyword or a short phrase  "
            "STRICTLY FORBIDDEN: Do not output full sentences, code snippets, or definitions."
        )
    )

class ConceptNode(BaseModel):
    concept_name: str = Field(description="The unique concise  title of the topic.")
    description: str = Field(description="A clear 1-sentence summary defining this topic.")

class PrerequisiteEdge(BaseModel):
    prerequisite: str = Field(description="The topic that must be learned first.")
    target: str = Field(description="The topic unlocked by the prerequisite.")

class PrerequisiteTree(BaseModel):
    nodes: List[ConceptNode]
    edges: List[PrerequisiteEdge]


def sanitize_and_break_cycles(nodes: list, edges: list) -> list:
    """
    Traverses the generated graph using a Depth-First Search (DFS).
    If it detects an edge looping back onto the active recursion stack,
    it removes that edge to guarantee a strict Directed Acyclic Graph (DAG).
    """
    adj = {n["concept_name"]: [] for n in nodes}
    for edge in edges:
        p, t = edge["prerequisite"], edge["target"]
        if p in adj and t in adj:
            adj[p].append(t)

    visited = set()
    rec_stack = set()
    bad_edges = set()

    def dfs(node):
        visited.add(node)
        rec_stack.add(node)

        for neighbor in adj.get(node, []):
            if neighbor in rec_stack:
                # Cycle detected
                print(f"✂️ Breaking cyclic deadlock: [{node}] ──x──> [{neighbor}]")
                bad_edges.add((node, neighbor))
            elif neighbor not in visited:
                dfs(neighbor)

        rec_stack.remove(node)

    # Run DFS from every unvisited root node
    for node in adj:
        if node not in visited:
            dfs(node)

    # Filter out the broken loops and orphaned edges (where source or target doesn't exist in nodes)
    cleaned_edges = [
        e for e in edges 
        if e["prerequisite"] in adj and e["target"] in adj and (e["prerequisite"], e["target"]) not in bad_edges
    ]
    
    print(f"🛡️ Graph Sanitize Complete: Removed {len(bad_edges)} cyclic links.")
    return cleaned_edges
def build_advanced_knowledge_graph(data_dir="data", db_dir="./db"):
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"📁 Created empty '{data_dir}/' folder. Place your textbook PDFs inside it and rerun.")
        return

    pdf_files = [f for f in os.listdir(data_dir) if f.endswith('.pdf')]
    if not pdf_files:
        print(f"❌ Aborted: No PDF files detected inside your '{data_dir}/' directory.")
        return

    os.makedirs(db_dir, exist_ok=True)
    checkpoint_path = os.path.join(db_dir, "extracted_concepts_checkpoint.json")
    
    checkpoint = {"completed_files": {}}
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, "r") as f:
                raw_data = json.load(f)
            if "completed_files" in raw_data:
                checkpoint = raw_data
        except Exception as e:
            print(f"⚠️ Checkpoint file corrupted or unreadable ({e}). Re-initializing.")
            
    print(f"📦 Connecting to persistent ChromaDB at '{db_dir}'...")
    chroma_client = chromadb.PersistentClient(path=db_dir)
    
    local_ef = SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-base-en-v1.5")
    collection = chroma_client.get_or_create_collection("course_material", embedding_function=local_ef)

    try:
        db_results = collection.get(include=["metadatas"])
        if db_results and db_results.get("metadatas"):
            db_files = set(m["source_file"] for m in db_results["metadatas"] if m and "source_file" in m)
            pdf_files_set = set(pdf_files)
            orphaned_db_files = db_files - pdf_files_set
            for orphaned in orphaned_db_files:
                print(f"🗑️ Clean-up: Purging orphaned database chunks for deleted book: {orphaned}")
                collection.delete(where={"source_file": orphaned})
    except Exception as e:
        print(f"⚠️ Warning: Could not complete database sync scan ({e})")

    checkpoint_completed_files = list(checkpoint["completed_files"].keys())
    for file_key in checkpoint_completed_files:
        if file_key not in pdf_files:
            print(f"🧹 Clean-up: Removing deleted book from checkpoint index: {file_key}")
            del checkpoint["completed_files"][file_key]
            
    with open(checkpoint_path, "w") as f:
        json.dump(checkpoint, f, indent=4)

    for active_pdf in pdf_files:
        if active_pdf not in checkpoint["completed_files"]:
            print(f"🧹 Clean-up: Clearing partial chunks from interrupted session for: {active_pdf}")
            try:
                collection.delete(where={"source_file": active_pdf})
            except Exception as e:
                pass

    unique_concepts = set()
    LOCAL_LLM = "qwen3:4b-instruct" 
    CHUNK_SIZE = 2500
    OVERLAP = 400
    
    print(f"🚀 Starting Map-Reduce conceptual parsing over {len(pdf_files)} textbooks...")

    for pdf_file in pdf_files:
        if pdf_file in checkpoint["completed_files"]:
            print(f"⏭️ File '{pdf_file}' already processed. Restoring {len(checkpoint['completed_files'][pdf_file])} concepts.")
            for concept in checkpoint["completed_files"][pdf_file]:
                unique_concepts.add(concept)
            continue
            
        pdf_path = os.path.join(data_dir, pdf_file)
        print(f"\n📖 Slicing data streams from: {pdf_file}...")
        
        try:
            reader = PdfReader(pdf_path)
            book_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    book_text += text + "\n"
        except Exception as e:
            print(f"❌ Failed to read or parse PDF {pdf_file}: {e}")
            continue

        file_concepts = set()
        chunks = []
        for i in range(0, len(book_text), CHUNK_SIZE - OVERLAP):
            chunks.append(book_text[i:i + CHUNK_SIZE])
            
        print(f"   ↳ Extracted {len(chunks)} text blocks. Processing...")

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{pdf_file}_chunk_{idx}"
            
            collection.add(
                documents=[chunk],
                metadatas=[{"source_file": pdf_file}],
                ids=[chunk_id]
            )
            
            try:
                response = ollama.chat(
                    model=LOCAL_LLM,
                    messages=[
                        {
                            'role': 'system',
                            'content': (
                                'You are an advanced automated topic/concept extractor. Your sole job is to read '
                                'the user text block and isolate 1 to 4 baseline academic topics taught within it. '
                                'Each topic MUST be a standalone, concise phrase or keyword. '
                                'Do not include structural descriptions, full sentences, or punctuation tags. '
                                'Good Examples: "Memory Management in C++", "Pointers", "Nested Arrays". '
                                'Bad Examples: "Explaining pointer configurations using operators."'
                            )
                         },
                         {'role': 'user', 'content': f"Extract topics from this text:\n\n{chunk}"}
                    ],
                    format=ConceptList.model_json_schema()
                )
                
                validated_data = ConceptList.model_validate_json(response['message']['content'])
                for topic in validated_data.concepts:
                    clean_topic = topic.strip().title()
                    if clean_topic:
                        file_concepts.add(clean_topic)
                        unique_concepts.add(clean_topic)
                        
            except Exception as e:
                pass
                
            if (idx + 1) % 10 == 0 or (idx + 1) == len(chunks):
                print(f"   ↳ Processed {idx + 1}/{len(chunks)} chunks... Logged {len(file_concepts)} unique concepts so far.")

        checkpoint["completed_files"][pdf_file] = list(file_concepts)
        with open(checkpoint_path, "w") as f:
            json.dump(checkpoint, f, indent=4)
        print(f"💾 Checkpoint saved: '{pdf_file}' complete.")

    if not unique_concepts:
        print("❌ Pipeline failed: No baseline concept assets were extracted from the documents.")
        return

    print(f"\n🌳 Reducing {len(unique_concepts)} unique tags into a structural Prerequisite Tree...")
    master_concept_string = ", ".join(list(unique_concepts))
    
    gemini_client = genai.Client()
    
    architect_prompt = f"""
    You are an elite curriculum designer mapping a syllabus compiled across reference materials.
    I have extracted a comprehensive list of all raw localized keywords found in the database.
    
    Your mission is to compile these keywords into a high-quality, professional, and readable curriculum roadmap (a Directed Acyclic Graph).
    
    CRITICAL STRUCTURE & VISUAL GUIDELINES FOR THE ROADMAP:
    1. CONSOLIDATION: The raw keyword catalog has many duplicates, minor variations, and noise. Consolidate them! Group related keywords into broader, high-level, clear concept nodes.
       
    2. ROADMAP PROGRESSION: Define a clear progressive learning path with distinct levels:
       - Level 0 (Fundamentals): The absolute prerequisites. Ensure there are only 1 to 4 base starting nodes that have no prerequisites.
       - Level 1+ (Progressive topics): Every other concept node must have at least one prerequisite pointing to it, so that there are no floating, disconnected topics.
       - Edges should follow difficulty: foundational topics must lead to intermediate topics, which lead to advanced topics.
    
    3. NO REDUNDANT EDGES: Do not include transitive edges that clutter the visualization.
       - If "Concept A" -> "Concept B", and "Concept B" -> "Concept C", do NOT create an edge "Concept A" -> "Concept C". The dependency is already implied.
       
    4. NO CYCLES: Under no circumstances should Concept A require Concept B while Concept B directly or indirectly requires Concept A.
    
    Master Keyword Catalog:
    {master_concept_string}
    """
    
    import time
    
    retries = 6
    delay = 10
    tree_response = None
    
    for attempt in range(retries):
        try:
            tree_response = gemini_client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=architect_prompt,
                config=types.GenerateContentConfig(
                    system_instruction="Build structural dependency trees from flat raw data definitions.",
                    response_mime_type="application/json",
                    response_schema=PrerequisiteTree,
                )
            )
            break
        except Exception as e:
            if attempt < retries - 1:
                print(f"⚠️ Cloud Generation attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2
            else:
                print(f"\n❌ Cloud Generation Failed after {retries} attempts: {e}")
                print(f"🔒 DON'T WORRY! Your {len(unique_concepts)} extracted concepts are SAFELY saved on disk.")
                print("👉 You can run compilation again later once your API limits reset.")
                return

    try:
        graph_data = tree_response.parsed.model_dump()
        
        graph_data["edges"] = sanitize_and_break_cycles(
            nodes=graph_data["nodes"],
            edges=graph_data["edges"]
        )
        
        tree_output_path = os.path.join(db_dir, "prereq_tree.json")
        with open(tree_output_path, "w") as f:
            json.dump(graph_data, f, indent=4)
            
        print(f"✅ Success! Loop-free Knowledge Graph saved to '{tree_output_path}'.")

    except Exception as e:
        print(f"❌ Error processing or saving prerequisite tree data: {e}")


if __name__ == "__main__":
    TEST_WORKSPACE = "workspaces/Terminal_Test_Project"
    
    test_data = os.path.join(TEST_WORKSPACE, "data")
    test_db = os.path.join(TEST_WORKSPACE, "db")
    
    build_advanced_knowledge_graph(data_dir=test_data, db_dir=test_db)