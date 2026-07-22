from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT_DIR / "docs"
IPC_PDF_PATH = DOCS_DIR / "IPC-Codes.pdf"
BNS_PDF_PATH = DOCS_DIR / "BNS-Codes.pdf"

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY") or None
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "lexrag_sections")

# bge-small is ~130MB and runs fine on a free-tier CPU box; bump to
# BAAI/bge-large-en-v1.5 for better retrieval quality once you have a real
# server to run it on (see README).
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

TOP_K = int(os.environ.get("RETRIEVAL_TOP_K", "6"))
