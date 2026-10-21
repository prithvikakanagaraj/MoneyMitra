"""
config.py - one place for all settings.

If you want to change a category, the currency symbol or a validation limit,
this is the only file you need to edit.
"""
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

# ---- Paths -----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load local .env file securely
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
# The environment variable lets the tests use a temporary database
# without touching your real data.
DB_PATH = Path(os.environ.get("FINANCE_DB_PATH", DATA_DIR / "finance.db"))

# ---- Display ---------------------------------------------------------------
APP_TITLE = "Intelligent Finance Chatbot"
CURRENCY_SYMBOL = "₹"

# ---- Transaction rules -----------------------------------------------------
TRANSACTION_TYPES = ("income", "expense")

EXPENSE_CATEGORIES = (
    "Food",
    "Groceries",
    "Travel",
    "Transport",
    "Shopping",
    "Education",
    "Bills",
    "Entertainment",
    "Healthcare",
    "Other",
)
INCOME_CATEGORIES = (
    "Salary", "Freelance", "Investment", "Gift", "Other",
)
CATEGORIES_BY_TYPE = {
    "expense": EXPENSE_CATEGORIES,
    "income": INCOME_CATEGORIES,
}

# ---- Validation limits -----------------------------------------------------
MAX_DESCRIPTION_LENGTH = 200
MAX_AMOUNT = Decimal("1000000000")   # 100 crore - a sanity limit against typos
MIN_DATE = date(2000, 1, 1)

# ---- Sample data -----------------------------------------------------------
# Every sample row starts with this text so it can never be mistaken for real data.
SAMPLE_PREFIX = "[SAMPLE] "

# ---- Gemini API Configuration ----------------------------------------------
# Read securely from environment (.env). Never hardcoded, never logged.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

