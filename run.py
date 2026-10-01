"""
SciForge One-Click Launcher
Starts the local-first scientific compiler server and opens the GUI in browser.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn
import webbrowser
import threading
import time

def open_browser():
    time.sleep(1.2)
    print("\n[SciForge] Launching local GUI: http://localhost:8000 ...")
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    print("=" * 65)
    print("  🚀 SciForge — Scientific Teaching & Publishing Compiler")
    print("  Paper → Understanding → Simulation → 10-Min Video")
    print("=" * 65)
    print("[*] Starting FastAPI server on http://localhost:8000")
    
    # Launch browser in separate thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False)
