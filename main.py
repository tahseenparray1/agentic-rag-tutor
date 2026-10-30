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
    
"""
Python Process Launcher — Concepts Learned

This script demonstrates several important Python concepts:

1. __name__
   - A special Python variable containing the name of the current module.
   - When a file is executed directly, __name__ is "__main__".
   - This allows us to use:
         if __name__ == "__main__":
             main()
     so that main() runs only when the file is executed directly.

2. __file__
   - A special variable containing the path used to load the current Python file.
   - It can be used to locate files relative to the current script.

3. os.path.dirname()
   - Extracts the directory portion of a file path.
   - Example:
         os.path.dirname(__file__)

4. os.path.join()
   - Combines multiple path components using the appropriate path
     separator for the operating system.
   - Example:
         os.path.join(base_dir, "src", "app.py")

5. sys.executable
   - Contains the path to the Python interpreter currently running
     the script.
   - Using it ensures that a subprocess uses the same Python
     environment/virtual environment as the current script.

6. subprocess
   - Provides a way for Python to create and run external processes.
   - subprocess.run() starts a process and waits for it to finish.
   - Conceptually, on Unix-like systems, this is similar to the
     fork() + exec() + wait() process model in C.

7. subprocess.run()
   - Executes a command synchronously.
   - The current Python thread waits until the child process exits.

8. subprocess.Popen()
   - Starts a subprocess without automatically waiting for it to finish.
   - This allows the parent Python program to continue executing.

In the Streamlit launcher, these concepts work together to locate
src/app.py and launch it using the same Python environment:

    sys.executable -m streamlit run src/app.py
"""
