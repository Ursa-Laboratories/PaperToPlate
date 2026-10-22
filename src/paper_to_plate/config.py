import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)
DATA = Path(os.getenv("PAPER_TO_PLATE_DATA", str(ROOT / "data")))
MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:120b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "https://ollama.com").rstrip("/").removesuffix("/api/chat")
CUBOS_PYTHON = os.getenv("CUBOS_VALIDATOR_PYTHON", "")
CUBOS_URL = os.getenv("CUBOS_API_URL", "http://localhost:8742").rstrip("/")
PORT = int(os.getenv("PAPER_TO_PLATE_PORT", "8785"))
