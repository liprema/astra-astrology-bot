"""
Configuration and multi-language wake-word ("Astra" / "Астра") detector.
"""
import os
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

BOOKS_DIR = BASE_DIR / "books"
DATA_DIR = BASE_DIR / "data"
CHARTS_DIR = DATA_DIR / "charts"
DB_PATH = DATA_DIR / "astra_state.db"
KNOWLEDGE_INDEX_PATH = DATA_DIR / "knowledge_index.json"

for d in (BOOKS_DIR, DATA_DIR, CHARTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("MPLCONFIGDIR", str(DATA_DIR / ".mplcache"))

# Regex pattern matching "Astra" in any case, script, declension, or keyboard layout:
# - Russian / Ukrainian / Belarusian / Bulgarian / Serbian: астра, астру, астре, астрой, астрочка, астры, астрою, астрі
# - Latin (EN, ES, FR, DE, IT, PT, PL, TR): astra, astre, astrae, astram
# - Greek (monotonic & polytonic): άστρα, αστρα, Ἄστρα
# - Hebrew: אסטרה
# - Arabic: أسترا, استرا
# - Hindi: अस्त्रा
# - CJK: 阿斯特拉, アストラ, 아스트라
# - Mixed Cyrillic/Latin homoglyphs (e.g. a/а, c/с, t/т, p/р)
ASTRA_WAKE_PATTERN = re.compile(
    r"(?:^|[^\w\d])("
    r"[аa][сc][тt][рp][аaуyеeоoиiіыює][йюя]?|"
    r"[аa][сc][тt][рp][оo][ч][к][аaуeио]|"
    r"astra[em]?|"
    r"[άαἀἁἂἃἄἅἆἇἈἉἊἋἌἍἎἏ]στρ[αa]|"
    r"אסטרה|"
    r"[أا]سترا|"
    r"अस्त्रा|"
    r"阿斯特拉|アストラ|아스트라"
    r")(?:$|[^\w\d])",
    re.IGNORECASE | re.UNICODE,
)


def contains_astra_wake_word(text: str) -> bool:
    """
    Returns True if the message contains the wake word 'Астра' / 'Astra'
    in any case, language, or Russian grammatical case.
    Avoids false positives on words like 'астрал' or 'астрология' by checking word boundaries.
    """
    if not text:
        return False
    return bool(ASTRA_WAKE_PATTERN.search(text))
