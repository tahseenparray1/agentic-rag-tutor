import os
import time
import ollama
from pypdf import PdfReader
from pydantic import BaseModel, Field
from typing import List

class ConceptList(BaseModel):
    concepts: List[str] = Field(description="List of core academic topics found in this text block.")

def profile_book_extraction(pdf_filename: str, sample_size: int = 15):
    pdf_path = os.path.join("data", pdf_filename)
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"❌ Could not find book at: {pdf_path}. Please drop it into your 'data/' directory.")

    print(f"📖 Reading layout pages from {pdf_filename}...")
    reader = PdfReader(pdf_path)
    full_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"
            
    chunk_size = 2500
    overlap = 400
    chunks = []
    for i in range(0, len(full_text), chunk_size - overlap):
        chunks.append(full_text[i:i + chunk_size])
        
    total_chunks = len(chunks)
    print(f"🧩 Book parsing complete. Slicing generated {total_chunks} total text blocks.")
    print(f"⏱️ Running performance baseline profile across the first {sample_size} chunks...\n")

    durations = []
    total_concepts_found = 0
    
    MODEL_NAME = "qwen3:4b-instruct" 

    for idx in range(min(sample_size, total_chunks)):
        chunk = chunks[idx]
        print(f"   [Processing Chunk {idx + 1}/{sample_size}] ...", end="", flush=True)
        
        start_time = time.time()
        try:
            response = ollama.chat(
                model=MODEL_NAME,
                messages=[
                    {
                        'role': 'system', 
                        'content': 'Extract 1 to 3 core academic concepts from the text. Each concept should a few words not full sentences. Return only valid JSON matching the schema.'
                    },
                    {
                        'role': 'user', 
                        'content': chunk
                    }
                ],
                format=ConceptList.model_json_schema()
            )
            
            elapsed = time.time() - start_time
            durations.append(elapsed)
            
            parsed = ConceptList.model_validate_json(response['message']['content'])
            total_concepts_found += len(parsed.concepts)

            print(f" Done in {elapsed:.2f}s")
            print("      Concepts:")
            for concept in parsed.concepts:
                print(f"        • {concept}")
            
            print(f" Done in {elapsed:.2f}s (Extracted {len(parsed.concepts)} items)")
            
        except Exception as e:
            print(f" ❌ Error processing chunk: {e}")

    if not durations:
        print("❌ Data profiling failed. Check local backend connection parameters.")
        return

    avg_time = sum(durations) / len(durations)
    estimated_total_seconds = avg_time * total_chunks
    estimated_total_minutes = estimated_total_seconds / 60

    print("\n==================================================")
    print("📊 GPU TELEMETRY METRICS SUMMARY REPORT")
    print("==================================================")
    print(f" 📦 Active Local Model       : {MODEL_NAME}")
    print(f" 🧩 Total Chunks In Book    : {total_chunks}")
    print(f" ⚡ Fastest Chunk Ingest     : {min(durations):.2f} seconds")
    print(f" 🐌 Slowest Chunk Ingest     : {max(durations):.2f} seconds")
    print(f" ⏱️  Average Speed Per Chunk  : {avg_time:.2f} seconds")
    print("--------------------------------------------------")
    print(f" 🔮 PROJECTED FULL RUNTIME   : {estimated_total_minutes:.2f} minutes")
    print("==================================================")
    print("💡 Analysis Recommendation:")
    if estimated_total_minutes < 15:
        print("🟢 Secure pipeline speeds detected. You are fully clear to run the full ingestion pipeline loop script.")
    else:
        print("🟡 Large batch job timeline. Running ingestion completely offline will take a while—grab a coffee when you execute the master script!")

if __name__ == "__main__":
    TARGET_BOOK = "deep_math.pdf" 
    
    profile_book_extraction(TARGET_BOOK, sample_size=15)