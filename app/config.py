from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]

LOG_DIR = Path(os.getenv("AP_INVOICE_LOG_DIR", PROJECT_ROOT / "logs")).expanduser()
if not LOG_DIR.is_absolute():
    LOG_DIR = (PROJECT_ROOT / LOG_DIR).resolve()
LOG_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = Path(
    os.getenv("AP_INVOICE_DB_PATH", PROJECT_ROOT / "vendor_master.db")
).expanduser()
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = (PROJECT_ROOT / DATABASE_PATH).resolve()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip() or None
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

VENDOR_NORMALIZER_THRESHOLD = float(
    os.getenv("VENDOR_NORMALIZER_THRESHOLD", "90")
)
VENDOR_NORMALIZER_MIN_MARGIN = float(
    os.getenv("VENDOR_NORMALIZER_MIN_MARGIN", "8")
)

DEFAULT_PAYMENT_TERMS = os.getenv("DEFAULT_PAYMENT_TERMS", "Net 30")
DEFAULT_DUPLICATE_VENDOR_THRESHOLD = float(
    os.getenv("DUPLICATE_VENDOR_THRESHOLD", "92")
)
DEFAULT_DUPLICATE_AMOUNT_VARIANCE_PERCENT = float(
    os.getenv("DUPLICATE_AMOUNT_VARIANCE_PERCENT", "2")
)
DEFAULT_DUPLICATE_DATE_WINDOW_DAYS = int(
    os.getenv("DUPLICATE_DATE_WINDOW_DAYS", "7")
)
SQLITE_BUSY_TIMEOUT_MS = int(os.getenv("SQLITE_BUSY_TIMEOUT_MS", "5000"))
INVOICE_URL_TIMEOUT_SECONDS = int(
    os.getenv("INVOICE_URL_TIMEOUT_SECONDS", "20")
)
