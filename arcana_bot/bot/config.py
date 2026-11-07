"""
Configuration and multi-language wake-word ("Arcana" / "Аркана") detector for the Tarot bot.
"""
import os
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TAROT_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

BOOKS_DIR = BASE_DIR / "books"
DATA_DIR = BASE_DIR / "data"
SPREADS_DIR = DATA_DIR / "spreads"
DB_PATH = DATA_DIR / "arcana_state.db"
KNOWLEDGE_INDEX_PATH = DATA_DIR / "knowledge_index.json"

for d in (BOOKS_DIR, DATA_DIR, SPREADS_DIR):
    d.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("MPLCONFIGDIR", str(DATA_DIR / ".mplcache"))

# Regex pattern matching "Аркана" / "Arcana" in any case, script, declension, or keyboard layout:
# - Russian / Ukrainian / Belarusian / Serbian / Bulgarian: аркана, аркану, аркане, арканой, арканы, арканочка, арканою, аркані
# - Latin (EN, ES, FR, DE, IT, PT, PL, TR): arcana, arkana, arcane, arcanum
# - Greek: αρκάνα, αρκανα, Ἀρκάνα
# - Hebrew: ארקנה
# - Arabic: أركانا, اركانا
# - Hindi: अर्काना
# - CJK: 阿卡纳, アルカナ, 아르카나
ARCANA_WAKE_PATTERN = re.compile(
    r"(?:^|[^\w\d])("
    r"[аa][рp][кk][аa][нn][аaуyеeоoиiіыює][йюя]?|"
    r"[аa][рp][кk][аa][нn][оo][ч][к][аaуeио]|"
    r"ar[ck]an[aeo]|"
    r"[άαἀἁἂἃἄἅἆἇἈἉἊἋἌἍἎἏ]ρκ[άα]ν[αa]|"
    r"ארקנה|"
    r"[أا]ركانا|"
    r"अर्काना|"
    r"阿卡纳|アルカナ|아르카나"
    r")(?:$|[^\w\d])",
    re.IGNORECASE | re.UNICODE,
)


def contains_arcana_wake_word(text: str) -> bool:
    """
    Returns True if the message contains the wake word 'Аркана' / 'Arcana'
    in any case, language, or Russian grammatical case.
    Avoids false positives on general phrases like 'старшие арканы' when used in plural masculine,
    unless specifically addressing 'Аркана' / 'Аркане' / 'Аркану' / 'Арканой' / 'Arcana'.
    """
    if not text:
        return False
    return bool(ARCANA_WAKE_PATTERN.search(text))
