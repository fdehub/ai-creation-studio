"""Single-user settings; paths never depend on the launching directory."""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / "runtime.env", override=False)
load_dotenv(BACKEND_DIR / ".env", override=False)
DATA_DIR = Path(os.environ.get("NOVEL_DATA_DIR", str(BACKEND_DIR))).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_ORIGINS = [s.strip() for s in os.environ.get(
    "NOVEL_ALLOWED_ORIGINS", "http://localhost:5273,http://127.0.0.1:5273"
).split(",") if s.strip()]
ALLOWED_HOSTS = [s.strip() for s in os.environ.get(
    "NOVEL_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]"
).split(",") if s.strip()]
