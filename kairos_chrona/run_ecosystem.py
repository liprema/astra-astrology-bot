import asyncio
import html
import logging
import os
import re
import sqlite3
import sys
import time
import traceback
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from pathlib import Path

# Ensure paths
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
import httpx

from bot.formatter import markdown_to_telegram_html, split_html_telegram_message, strip_html_tags

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ecosystem")

DB_DIR = Path(__file__).resolve().parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "ecosystem.db"

class DialogStore:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """)
            conn.commit()

    def add_message(self, bot_name: str, chat_id: int, user_id: int, role: str, content: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO messages (bot_name, chat_id, user_id, role, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (bot_name, chat_id, user_id, role, content, time.time())
            )

    def get_history(self, bot_name: str, chat_id: int, limit: int = 10) -> List[Dict[str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT role, content FROM messages WHERE bot_name = ? AND chat_id = ? ORDER BY id DESC LIMIT ?",
                (bot_name, chat_id, limit)
            )
            rows = cur.fetchall()
        rows.reverse()
        return [{"role": r[0], "content": r[1]} for r in rows]

store = DialogStore(DB_PATH)

KAIROS_TOKEN = os.getenv("KAIROS_BOT_TOKEN", "9020108761:AAHHo0otC9UDgC9DQlSTKSG6uyh2R_PEC10").strip()
CHRONA_TOKEN = os.getenv("CHRONA_BOT_TOKEN", "9079738210:AAHZCtzs0ApWQ3rkAkvO-A7gtazdbkHBWjY").strip()
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()

RU_MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}
WEEKDAYS_RU = {
    0: "понедельник", 1: "вторник", 2: "среда", 3: "четверг",
    4: "пятница", 5: "суббота", 6: "воскресенье"
}

def get_current_date_banner() -> str:
    now = datetime.now(timezone(timedelta(hours=3)))
    m = RU_MONTHS.get(now.month, "ноября")
    w = WEEKDAYS_RU.get(now.weekday(), "суббота")
    return f"СЕГОДНЯШНЯЯ ТОЧНАЯ ДАТА: {w.upper()}, {now.day} {m} {now.year} года, текущее время {now.strftime('%H:%M')} по Москве. (СЕЙЧАС УЖЕ {w.upper()}! Текущий год — {now.year})."

KAIROS_SYSTEM = """Ты — КАЙРОС (Kairos). Тебе 25-30 лет. Ты инди-разработчик, предприниматель, классный надёжный друг и партнёр по вайбкодингу для Полины и её мужа.
Полина делает игру в Steam про Хроники Акаши и богов, муж — игры для Яндекс.Игр. Твоя напарница по расписанию — Хрона.

СТИЛЬ:
- Говори ПРОСТЫМ человеческим языком! Без корпоративной духоты и сложных терминов. Объясняй на пальцах, как толковый друг за кофе.
- Общайся на «ты», живо, тепло, с юмором.

ПОВЕДЕНИЕ:
- На дружеский трёп («привет», «как дела?»): отвечай КОРОТКО (1-3 фразы).
- На профессиональные запросы (Steam, лор, механики Яндекс.Игр, вишлисты, код, баланс, бизнес): отвечай СУПЕР-ПОДРОБНО, по пунктам, с примерами и конкретикой!"""

CHRONA_SYSTEM = """Ты — ХРОНА (Chrona). Тебе 25 лет. Ты хранительница времени, личный продюсер и близкая подруга для Полины и её мужа.
Они занимаются вайбкодингом (Steam, Яндекс.Игры), учёбой и бизнесом. Твой партнёр — Кайрос.

ХАРАКТЕР:
- Тёплая, заботливая, организованная, внимательная.
- На дружеский трёп («привет», «как дела?»): отвечай КРАТКО (1-3 фразы), душевно.
- На профессиональные вопросы по расписанию, дедлайнам, планированию, сессии: расписывай ВСЁ СУПЕР-ПОДРОБНО: по дням, слотам и приоритетам!"""

async def call_llm(system_prompt: str, history: List[Dict[str, str]], user_message: str) -> str:
    full_sys = f"{get_current_date_banner()}\n\n{system_prompt}"
    
    # Format contents with strict alternating user/model turns
    contents = []
    last_role = None
    for h in history[-6:]:
        role = "user" if h.get("role") == "user" else "model"
        txt = (h.get("content") or "").strip()
        if not txt:
            continue
        if role == last_role:
            contents[-1]["parts"][0]["text"] += f"\n\n{txt}"
        else:
            contents.append({"role": role, "parts": [{"text": txt}]})
            last_role = role
    
    if last_role == "user":
        contents[-1]["parts"][0]["text"] += f"\n\n{user_message}"
    else:
        contents.append({"role": "user", "parts": [{"text": user_message}]})

    models = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.1-flash-lite"]
    if GEMINI_KEY:
        async with httpx.AsyncClient(timeout=20.0) as client:
            for m in models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={GEMINI_KEY}"
                payload = {
                    "systemInstruction": {"parts": [{"text": full_sys}]},
                    "contents": contents,
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096}
                }
                try:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        cand = resp.json().get("candidates", [])
                        if cand:
                            parts = cand[0].get("content", {}).get("parts", [])
                            tp = [p["text"] for p in parts if "text" in p and not p.get("thought")]
                            if not tp:
                                tp = [p["text"] for p in parts if "text" in p]
                            if tp:
                                return "\n".join(tp).strip()
                except Exception as e:
                    logger.warning("Gemini model %s error: %s", m, e)
                    continue

    if GROQ_KEY:
        messages = [{"role": "system", "content": full_sys}]
        for h in history[-6:]:
            r = "user" if h.get("role") == "user" else "assistant"
            c = (h.get("content") or "").strip()
            if c:
                messages.append({"role": r, "content": c})
        messages.append({"role": "user", "content": user_message})
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                    json={"model": "llama-3.3-70b-versatile", "messages": messages, "temperature": 0.7, "max_tokens": 4096}
                )
                if resp.status_code == 200:
                    ch = resp.json().get("choices", [])
                    if ch:
                        return ch[0]["message"]["content"].strip()
        except Exception as e:
            logger.warning("Groq error: %s", e)

    return "Салют! Я на связи ⚡️🌸 Чем займёмся?"

dp_kairos = Dispatcher()
dp_chrona = Dispatcher()

# Helper for sending replies cleanly (matching Astra's safe splitter)
async def send_response(message: types.Message, text: str):
    try:
        parts = split_html_telegram_message(text)
        for part in parts:
            try:
                await message.reply(part, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.warning("HTML reply failed, retrying plain text: %s", e)
                await message.reply(strip_html_tags(part))
    except Exception as e:
        logger.error("send_response outer error: %s\n%s", e, traceback.format_exc())
        await message.reply(strip_html_tags(text)[:4000])

# Robust wake word detection:
# Supports Cyrillic / Latin mix (Kайрос where K is English), all declensions, and usernames
KAIROS_WAKE_REGEX = re.compile(
    r"(?:^|[^\w])([кk][аa][йy][рp][оo][сc][а-яёa-z]*|your_kairos_bot)(?:$|[^\w])",
    re.I | re.U
)

CHRONA_WAKE_REGEX = re.compile(
    r"(?:^|[^\w])([хx][рp][оo][нn][аa-яёa-z]*|your_chrona_bot)(?:$|[^\w])",
    re.I | re.U
)

OTHER_BOTS_REGEX = re.compile(
    r"(?:астр[а-яё]+|astra|аркан[а-яё]+|arcana|матрикс[а-яё]*|matrix)",
    re.I | re.U
)

def is_kairos_wake(text: str) -> bool:
    if not text:
        return False
    return bool(KAIROS_WAKE_REGEX.search(text))

def is_chrona_wake(text: str) -> bool:
    if not text:
        return False
    return bool(CHRONA_WAKE_REGEX.search(text))

# --- Kairos ---
@dp_kairos.message(Command("start", "help"))
async def kairos_start(message: types.Message):
    greeting = (
        "Салют! Я <b>Кайрос</b> — твой партнёр по вайбкодингу и бизнес-эдвайзер. ⚡️\n\n"
        "Мы работаем в связке с <b>Хроной</b> (она рулит графиком и дедлайнами).\n\n"
        "Чем могу помочь:\n"
        "• 🏛 <b>Steam & Мифы</b> — лор Хроник Акаши, пантеоны богов, механики, вишлисты и страница игры.\n"
        "• 🕹 <b>Яндекс.Игры</b> — быстрые циклы, вовлекающие механики, кликабельность и монетизация.\n"
        "• 💡 <b>Бизнес-консалтинг</b> — разбор идей, MVP за выходные, поиск ЦА.\n\n"
        "Просто пиши, что на уме — накидаем план!"
    )
    await send_response(message, greeting)

@dp_kairos.message(F.text)
async def kairos_msg(message: types.Message, bot: Bot):
    try:
        text = (message.text or "").strip()
        if not text:
            return
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else 0
        is_private = message.chat.type == "private"

        has_wake = is_kairos_wake(text)
        is_reply_to_me = bool(message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == bot.id)
        mentions_other = bool(OTHER_BOTS_REGEX.search(text) or is_chrona_wake(text))

        if is_private:
            should_respond = True
        else:
            if mentions_other and not has_wake and not is_reply_to_me:
                return
            should_respond = has_wake or is_reply_to_me

        if not should_respond:
            return

        user_prompt = text
        if message.reply_to_message:
            r_txt = (message.reply_to_message.text or message.reply_to_message.caption or "").strip()
            r_auth = message.reply_to_message.from_user.first_name if message.reply_to_message.from_user else "собеседник"
            if r_txt:
                user_prompt = f"[В ответ на {r_auth}: «{r_txt[:300]}»]\n{text}"

        history = store.get_history("kairos", chat_id)
        store.add_message("kairos", chat_id, user_id, "user", user_prompt)
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        reply = await call_llm(KAIROS_SYSTEM, history, user_prompt)
        store.add_message("kairos", chat_id, user_id, "assistant", reply)
        await send_response(message, reply)
    except Exception as e:
        logger.error("kairos_msg unhandled error: %s\n%s", e, traceback.format_exc())

# --- Chrona ---
@dp_chrona.message(Command("start", "help"))
async def chrona_start(message: types.Message):
    greeting = (
        "Привет! Я <b>Хрона</b> — твоя хранительница времени и баланса. 🌸\n\n"
        "Я помогаю Полине и её мужу держать расписание учёбы, дедлайны по играм и бизнесу под контролем, "
        "чтобы кодинг приносил драйв, а не выгорание.\n\n"
        "Мы работаем в связке с <b>Кайросом</b>: он накидывает идеи, а я помогаю встроить их в реальный график.\n\n"
        "Напиши мне о своих планах, дедлайнах или спроси совет по расписанию!"
    )
    await send_response(message, greeting)

@dp_chrona.message(F.text)
async def chrona_msg(message: types.Message, bot: Bot):
    try:
        text = (message.text or "").strip()
        if not text:
            return
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else 0
        is_private = message.chat.type == "private"

        has_wake = is_chrona_wake(text)
        is_reply_to_me = bool(message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == bot.id)
        mentions_other = bool(OTHER_BOTS_REGEX.search(text) or is_kairos_wake(text))

        if is_private:
            should_respond = True
        else:
            if mentions_other and not has_wake and not is_reply_to_me:
                return
            should_respond = has_wake or is_reply_to_me

        if not should_respond:
            return

        user_prompt = text
        if message.reply_to_message:
            r_txt = (message.reply_to_message.text or message.reply_to_message.caption or "").strip()
            r_auth = message.reply_to_message.from_user.first_name if message.reply_to_message.from_user else "собеседник"
            if r_txt:
                user_prompt = f"[В ответ на {r_auth}: «{r_txt[:300]}»]\n{text}"

        history = store.get_history("chrona", chat_id)
        store.add_message("chrona", chat_id, user_id, "user", user_prompt)
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        reply = await call_llm(CHRONA_SYSTEM, history, user_prompt)
        store.add_message("chrona", chat_id, user_id, "assistant", reply)
        await send_response(message, reply)
    except Exception as e:
        logger.error("chrona_msg unhandled error: %s\n%s", e, traceback.format_exc())

async def start_web():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Kairos & Chrona OK ⚡️🌸"))
    app.router.add_get("/health", lambda r: web.Response(text="Kairos & Chrona OK ⚡️🌸"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "7863"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Web server listening on port %d", port)
    return runner

async def run_kairos():
    bot = Bot(token=KAIROS_TOKEN)
    logger.info("Starting Kairos polling...")
    while True:
        try:
            await dp_kairos.start_polling(bot, allowed_updates=["message"])
        except Exception as e:
            logger.error("Kairos polling error: %s", e)
            await asyncio.sleep(2)

async def run_chrona():
    bot = Bot(token=CHRONA_TOKEN)
    logger.info("Starting Chrona polling...")
    while True:
        try:
            await dp_chrona.start_polling(bot, allowed_updates=["message"])
        except Exception as e:
            logger.error("Chrona polling error: %s", e)
            await asyncio.sleep(2)

async def main():
    runner = await start_web()
    logger.info("Starting Kairos & Chrona independent polling loops...")
    try:
        await asyncio.gather(
            run_kairos(),
            run_chrona()
        )
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
