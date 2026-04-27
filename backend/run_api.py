"""
run_api.py
Starts the PawPal+ FastAPI server.

Usage (from the project root):
    python backend/run_api.py
"""

import sys
from pathlib import Path

# Allow direct execution: python backend/run_api.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
