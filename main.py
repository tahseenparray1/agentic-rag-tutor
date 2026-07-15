import subprocess
import sys
import os

def main():
    """Entry point to launch the Agentic RAG Tutor Streamlit interface."""
    app_path = os.path.join(os.path.dirname(__file__), "src", "app.py")
    cmd = [sys.executable, "-m", "streamlit", "run", app_path]
    print(f"🚀 Launching Agentic RAG Tutor on Streamlit...")
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n👋 App stopped by user.")

if __name__ == "__main__":
    main()
