"""
Configuration and multi-language wake-word ("Matrix" / "Матрикс" / "Матрица") detector for the Numerology bot.
"""
import os
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("MATRIX_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

BOOKS_DIR = BASE_DIR / "books"
DATA_DIR = BASE_DIR / "data"
CHARTS_DIR = DATA_DIR / "matrices"
DB_PATH = DATA_DIR / "matrix_state.db"
KNOWLEDGE_INDEX_PATH = DATA_DIR / "knowledge_index.json"

for d in (BOOKS_DIR, DATA_DIR, CHARTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("MPLCONFIGDIR", str(DATA_DIR / ".mplcache"))

# Regex pattern matching "Матрикс" / "Matrix" / "Матрица" in any case, script, declension, or keyboard layout:
# - Russian / Slavic: матрикс, матрикса, матриксу, матриксом, матриксе, матрица, матрицу, матрице, матрицей, матрицы
# - Latin: matrix, matriks, matrice, matriz
# - Greek: μάτριξ, ματριξ
# - Hebrew: מטריקס
# - Arabic: ماتريكس
# - Hindi: मैट्रिक्स
# - CJK: 矩阵, マトリックス, 매트릭스
MATRIX_WAKE_PATTERN = re.compile(
    r"(?:^|[^\w\d])("
    r"[мm][аa][тt][рp][иiі][кk][сc](?:[аaуyеeоoмm][мmхx]?)?|"
    r"[мm][аa][тt][рp][иiі][цc][аaуyеeыiіоo][йюя]?|"
    r"matri(?:x|ks|ce|z)|"
    r"[μΜ][άα]τριξ|"
    r"מטריקס|"
    r"ماتريكس|"
    r"मैट्रिक्स|"
    r"矩阵|マトリックス|매트릭스"
    r")(?:$|[^\w\d])",
    re.IGNORECASE | re.UNICODE,
)


def contains_matrix_wake_word(text: str) -> bool:
    """
    Returns True if the message contains the wake word 'Матрикс' / 'Matrix' / 'Матрица'
    in any case, language, or Russian grammatical case.
    """
    if not text:
        return False
    return bool(MATRIX_WAKE_PATTERN.search(text))
