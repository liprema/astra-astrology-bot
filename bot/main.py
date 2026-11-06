"""
Main Telegram Bot Entrypoint for ASTRA ("Астра") + Built-in 24/7 Cloud Health Server.

Features:
1. Instant Wake-Word Trigger: Responds immediately whenever anyone writes "Астра" / "Astra"
   in any case, language, or grammatical form (in both private chats and group chats).
2. Active Session Continuity: Once awakened in a chat or replied to, Astra stays attentive
   to collect missing birth/horary details until the chart & reading are delivered.
3. Strict Pre-Answer Verification: Always verifies WHO/WHAT the question is about,
   exact Date, Time (and time source), and City before calculating.
4. High-Resolution Natal/Horary/Synastry/Mundane Chart Photo Generation & Delivery.
5. Multi-Tradition Synthesis with explicit school attribution & alternative school comparisons.
6. Book Library Management: Users/owners can send book files (PDF/EPUB/FB2/DOCX/TXT) or
   Yandex.Disk links directly in Telegram or via `/books` to index new books on the fly
   and get an immediate report on any unreadable files.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from bot.astro_engine import calculate_full_chart, resolve_place
from bot.chart_renderer import render_chart_image
from bot.config import (
    BOOKS_DIR,
    CHARTS_DIR,
    DB_PATH,
    TELEGRAM_BOT_TOKEN,
    contains_astra_wake_word,
)
from bot.knowledge_base import download_from_yandex_disk, extract_text_from_file, knowledge_base
from bot.llm_astrologer import analyze_dialog_completeness, generate_astrological_interpretation

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("astra_bot")


class DialogStore:
    """SQLite-backed conversation memory so Astra remembers context across messages."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS active_sessions (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    last_active REAL NOT NULL,
                    PRIMARY KEY (chat_id, user_id)
                )
                """
            )

    def mark_active(self, chat_id: int, user_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO active_sessions (chat_id, user_id, last_active)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET last_active = excluded.last_active
                """,
                (chat_id, user_id, time.time()),
            )

    def is_recently_active(self, chat_id: int, user_id: int, ttl_seconds: int = 1800) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT last_active FROM active_sessions WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return False
            return (time.time() - float(row[0])) <= ttl_seconds

    def clear_session(self, chat_id: int, user_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM messages WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            conn.execute("DELETE FROM active_sessions WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))

    def add_message(self, chat_id: int, user_id: int, role: str, content: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO messages (chat_id, user_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (chat_id, user_id, role, content, time.time()),
            )

    def get_history(self, chat_id: int, user_id: int, limit: int = 10) -> List[Dict[str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT role, content FROM messages WHERE chat_id = ? AND user_id = ? ORDER BY id DESC LIMIT ?",
                (chat_id, user_id, limit),
            )
            rows = cur.fetchall()
        rows.reverse()
        return [{"role": r[0], "content": r[1]} for r in rows]


store = DialogStore(DB_PATH)
dp = Dispatcher()


def split_long_telegram_message(text: str, max_len: int = 3900) -> List[str]:
    """Split long astrological readings cleanly by paragraphs so Telegram never truncates."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    current = ""
    for para in text.split("\n\n"):
        if len(current) + len(para) + 2 <= max_len:
            current = f"{current}\n\n{para}".strip()
        else:
            if current:
                chunks.append(current)
            if len(para) <= max_len:
                current = para
            else:
                for i in range(0, len(para), max_len):
                    chunks.append(para[i : i + max_len])
                current = ""
    if current:
        chunks.append(current)
    return chunks


@dp.message(Command("start", "help"))
async def cmd_start(message: Message) -> None:
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    store.mark_active(chat_id, user_id)

    welcome = (
        "✨ **Приветствую! Я — Астра (Astra), ваш автономный астролог-эксперт.**\n\n"
        "Я откликаюсь в любой момент, как только вы напишете моё имя **«Астра»** / **«Astra»** "
        "(в любом регистре и на любом языке).\n\n"
        "🔮 **В каких направлениях я работаю:**\n"
        "• **Западная классическая и современная астрология** (натал, транзиты, соляры, прогрессии, синастрия, релокация/астрокартография, мунданная).\n"
        "• **Хорарная и Элективная астрология** (ответы на конкретные вопросы и подбор лучшего времени по У. Лилли и Дж. Фроули, дома Региомонтануса).\n"
        "• **Эллинистическая и Средневековая традиция** (секта карты, полнознаковые дома, Жребии Фортуны и Духа, годовые профекции, фирдары).\n"
        "• **Ураническая (Гамбургская школа), Гелиоцентрическая, Кармическая астрология и Формула Души** (8 транснептунов, мидпойнты, цепочки диспозиторов).\n\n"
        "📐 **Как я работаю:**\n"
        "1. Перед ответом я всегда уточняю **о ком или о чём идёт речь** и проверяю все координаты (дату, точное время, город).\n"
        "2. Строю и присылаю **изображение натальной/хорарной карты фотографией**.\n"
        "3. В разборе **всегда указываю, на какую школу опираюсь**, а при разногласиях школ привожу **альтернативное мнение**.\n\n"
        "📚 Команда `/books` — посмотреть загруженные книги и статус базы знаний.\n"
        "🔄 Команда `/reset` — начать разбор нового человека или нового вопроса с чистого листа.\n\n"
        "*Напишите свой вопрос или просто позовите меня: «Астра»!*"
    )
    await message.reply(welcome, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    store.clear_session(chat_id, user_id)
    store.mark_active(chat_id, user_id)
    await message.reply(
        "🔄 Контекст предыдущего разбора очищен! Напишите, **о ком или о чём** ваш новый вопрос, "
        "и укажите дату, время и город.",
        parse_mode=ParseMode.MARKDOWN,
    )


@dp.message(Command("books"))
async def cmd_books(message: Message) -> None:
    summary = knowledge_base.load_or_build_index()
    lines = [
        "📚 **БАЗА АСТРОЛОГИЧЕСКИХ КНИГ АСТРЫ**",
        f"• Проиндексировано книг пользователя: **{summary['indexed_books_count']}**",
        f"• Всего смысловых фрагментов в базе (включая канонический свод школ): **{summary['total_chunks']}**",
    ]
    if summary["indexed_books"]:
        lines.append("\n✅ **Изученные книги и назначенный авторитет:**")
        for b in summary["indexed_books"][:25]:
            lines.append(f"• `{b['file']}` — Авторитет **{b['authority']}/10** ({b['school']}, фрагментов: {b['chunks_count']})")

    if summary["unreadable_files"]:
        lines.append("\n⚠️ **Файлы, которые не удалось прочитать/изучить (требуют замены или OCR):**")
        for u in summary["unreadable_files"]:
            lines.append(f"• ❌ `{u['file']}` — Причина: *{u['reason']}*")
    else:
        lines.append("\n✅ *Нечитаемых или повреждённых файлов не обнаружено.*")

    lines.append(
        "\n💡 *Вы можете прямо сюда в чат прислать файл книги (PDF, DOCX, EPUB, FB2, TXT) "
        "или публичную ссылку на Яндекс.Диск — я сразу скачаю и изучу её!*"
    )
    await message.reply("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


@dp.message(F.document)
async def handle_book_document(message: Message, bot: Bot) -> None:
    """Allow user to upload astrological books directly in Telegram chat."""
    doc = message.document
    if not doc or not doc.file_name:
        return
    target_path = BOOKS_DIR / doc.file_name
    status_msg = await message.reply(f"📥 Загружаю и изучаю книгу `{doc.file_name}`...", parse_mode=ParseMode.MARKDOWN)
    try:
        file_info = await bot.get_file(doc.file_id)
        await bot.download_file(file_info.file_path, destination=target_path)
        text, err = extract_text_from_file(target_path)
        summary = knowledge_base.load_or_build_index()
        if err:
            await status_msg.edit_text(
                f"⚠️ Я сохранила файл `{doc.file_name}`, но **не смогла его прочитать**:\n"
                f"Причина: *{err}*\n\nПожалуйста, пришлите текстовую версию (PDF с текстом, DOCX, FB2, EPUB или TXT).",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await status_msg.edit_text(
                f"✅ Книга `{doc.file_name}` успешно изучена и добавлена в базу знаний Астры!\n"
                f"Всего фрагментов в базе: **{summary['total_chunks']}**.",
                parse_mode=ParseMode.MARKDOWN,
            )
    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка при загрузке файла `{doc.file_name}`: {exc}")


@dp.message(F.text)
async def handle_text_message(message: Message, bot: Bot) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    is_private = message.chat.type == "private"

    # Check if user sent a Yandex.Disk link to download books
    ydisk_match = re.search(r"https?://(?:disk\.yandex\.[a-z]+|yadi\.sk)/\S+", text, re.I)
    if ydisk_match:
        url = ydisk_match.group(0)
        wait_msg = await message.reply(f"☁️ Обнаружена ссылка на Яндекс.Диск! Скачиваю и проверяю книги...", parse_mode=ParseMode.MARKDOWN)
        downloaded, dl_errors = await asyncio.to_thread(download_from_yandex_disk, url, BOOKS_DIR)
        summary = await asyncio.to_thread(knowledge_base.load_or_build_index)
        report = [
            f"📚 **Отчёт по загрузке книг с Яндекс.Диска:**",
            f"• Скачано файлов: **{len(downloaded)}**",
            f"• Всего изучено книг в базе: **{summary['indexed_books_count']}** (фрагментов: **{summary['total_chunks']}**)",
        ]
        if dl_errors:
            report.append("\n⚠️ **Ошибки скачивания:**\n" + "\n".join(f"• {e}" for e in dl_errors))
        if summary["unreadable_files"]:
            report.append(
                "\n⚠️ **Книги, которые я НЕ смогла прочитать (нужен OCR или другой формат):**\n"
                + "\n".join(f"• ❌ `{u['file']}` — {u['reason']}" for u in summary["unreadable_files"])
            )
        await wait_msg.edit_text("\n".join(report), parse_mode=ParseMode.MARKDOWN)
        return

    # Wake-word detection:
    # 1. If the message contains "Астра" / "Astra" in any case or language -> wake up immediately!
    # 2. If in private chat or replying directly to Astra or within an active dialog session -> respond!
    has_wake_word = contains_astra_wake_word(text)
    is_reply_to_bot = bool(
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.is_bot
    )
    in_active_session = store.is_recently_active(chat_id, user_id)

    if not (has_wake_word or is_private or is_reply_to_bot or in_active_session):
        return

    # Mark session active & store user message
    store.mark_active(chat_id, user_id)
    store.add_message(chat_id, user_id, "user", text)

    # Immediately send typing action so the user sees instant response
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # Check if the user ONLY wrote the wake word (e.g., "Астра", "Astra!", "АСТРА привет") without a question yet
    stripped_without_wake = re.sub(
        r"(?:привет|здравствуй(?:те)?|добрый\s+день|добрый\s+вечер|алло|эй|слушай|астра|astra|άστρα|אסטרה|أسترا|अस्त्रा|[!?,.\s])+",
        "",
        text,
        flags=re.I,
    )
    history = store.get_history(chat_id, user_id, limit=10)

    if len(stripped_without_wake) < 3 and len(history) <= 2:
        instant_greeting = (
            "✨ **Я здесь! Астра на связи и внимательно слушает вас.**\n\n"
            "Расскажите, пожалуйста:\n"
            "1. **О ком или о чём ваш вопрос?** (ваша натальная карта, карта другого человека, совместимость, прогноз, выбор даты или хорарный вопрос «здесь и сейчас»)\n"
            "2. **Дата** (`ДД.ММ.ГГГГ`), **точное время** (`ЧЧ:ММ`, укажите: по бирке, со слов или ректификация) и **город** рождения (или ваш текущий город для хорара).\n\n"
            "Как только вы напишете данные, я сразу построю и пришлю фото карты и сделаю полный разбор по всем астрологическим школам!"
        )
        store.add_message(chat_id, user_id, "assistant", instant_greeting)
        await message.reply(instant_greeting, parse_mode=ParseMode.MARKDOWN)
        return

    # Analyze dialog completeness (WHO/WHAT, Date, Time, City)
    analysis = await analyze_dialog_completeness(history)

    if not analysis.get("has_all_required_data"):
        clarification = analysis.get("missing_info_question_ru") or (
            "✨ **Я на связи!** Чтобы я построила точную карту и ответила без догадок, "
            "пожалуйста, уточните:\n"
            "• **О ком или о чём идёт речь?**\n"
            "• **Дату** (`ДД.ММ.ГГГГ`), **точное время** (`ЧЧ:ММ`) и **город**."
        )
        store.add_message(chat_id, user_id, "assistant", clarification)
        await message.reply(clarification, parse_mode=ParseMode.MARKDOWN)
        return

    # All required data is present! Immediately notify user that calculation & chart rendering started
    ack_msg = await message.reply(
        "🔭 **Все данные приняты!** Проверяю геокоординаты, рассчитываю точные эфемериды, "
        "строю изображение карты и сверяю трактовки по базе астрологических школ...",
        parse_mode=ParseMode.MARKDOWN,
    )

    place_query = analysis.get("place_city") or "Москва"
    geo = await asyncio.to_thread(resolve_place, place_query)
    if not geo:
        ask_city_again = (
            f"⚠️ Мне не удалось найти на карте населённый пункт **«{place_query}»**.\n"
            "Пожалуйста, напишите название города (или ближайшего крупного города и области/страны) чуть точнее!"
        )
        store.add_message(chat_id, user_id, "assistant", ask_city_again)
        await ack_msg.edit_text(ask_city_again, parse_mode=ParseMode.MARKDOWN)
        return

    # Parse date and time
    date_str = analysis.get("date_str") or "NOW"
    time_str = analysis.get("time_str") or "NOW"
    chart_type = analysis.get("chart_type") or "natal"
    subject_name = analysis.get("subject_name") or "Карта"

    try:
        if date_str == "NOW" or time_str == "NOW":
            import pytz
            tz_obj = pytz.timezone(geo.tz_name)
            dt_local = datetime.datetime.now(tz_obj).replace(tzinfo=None)
        else:
            d_parts = [int(x) for x in re.split(r"[./-]", date_str)]
            t_parts = [int(x) for x in re.split(r"[:.]", time_str)]
            dt_local = datetime.datetime(d_parts[2], d_parts[1], d_parts[0], t_parts[0], t_parts[1])
    except Exception:
        ask_date_again = (
            "⚠️ Пожалуйста, проверьте корректность даты и времени и напишите их в формате "
            "`ДД.ММ.ГГГГ ЧЧ:ММ` (например: `15.05.1995 14:30`)."
        )
        store.add_message(chat_id, user_id, "assistant", ask_date_again)
        await ack_msg.edit_text(ask_date_again, parse_mode=ParseMode.MARKDOWN)
        return

    # 1. Calculate multi-tradition chart
    chart = await asyncio.to_thread(
        calculate_full_chart,
        dt_local,
        geo.lat,
        geo.lon,
        geo.tz_name,
        place_label=place_query,
        subject_name=subject_name,
        chart_type=chart_type,
    )

    # 2. Render chart PNG image and send as photo
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
    img_filename = f"chart_{chat_id}_{int(time.time())}.png"
    img_path = CHARTS_DIR / img_filename
    await asyncio.to_thread(render_chart_image, chart, img_path)

    photo_caption = (
        f"🗺 **Карта: {subject_name}**\n"
        f"📅 `{chart['dt_local_str']}` | 📍 {place_query} (`{geo.lat:.2f}°N, {geo.lon:.2f}°E`)\n"
        f"🏛 Дома: {chart['house_system']} (+ сравнение с Полнознаковой) | {chart['hellenistic_medieval']['sect']}\n"
        f"⬆️ **ASC:** {chart['asc']['formatted']} | **MC:** {chart['mc']['formatted']}"
    )
    await message.reply_photo(
        photo=FSInputFile(img_path),
        caption=photo_caption,
        parse_mode=ParseMode.MARKDOWN,
    )

    # 3. Search authoritative book passages and synthesize full multi-tradition reading
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    user_q = analysis.get("user_question") or text
    search_query = f"{user_q} {chart['asc']['sign']} Солнце {chart['planets'][0]['sign']} Луна {chart['planets'][1]['sign']} {chart_type}"
    rag_passages = await asyncio.to_thread(knowledge_base.search, search_query, 6)

    reading = await generate_astrological_interpretation(
        chart=chart,
        user_question=user_q,
        rag_passages=rag_passages,
    )
    store.add_message(chat_id, user_id, "assistant", reading)

    # Delete temporary progress message and send full reading
    try:
        await ack_msg.delete()
    except Exception:
        pass

    for part in split_long_telegram_message(reading):
        try:
            await message.reply(part, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await message.reply(part)


async def health_handler(request: web.Request) -> web.Response:
    """HTTP healthcheck endpoint so free cloud platforms (Render / HuggingFace / Railway) keep the container alive 24/7."""
    return web.json_response({
        "status": "ok",
        "bot": "Astra (Астра) Multi-Tradition Astrology Bot",
        "indexed_books": len(knowledge_base.indexed_books),
        "total_knowledge_chunks": len(knowledge_base.chunks),
        "unreadable_files": knowledge_base.unreadable_files,
    })


async def start_background_web_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health web server listening on port %d", port)
    return runner


async def main() -> None:
    runner = await start_background_web_server()
    if not TELEGRAM_BOT_TOKEN:
        logger.warning(
            "TELEGRAM_BOT_TOKEN is not set in .env yet! "
            "Health server is running. Set TELEGRAM_BOT_TOKEN to start polling Telegram."
        )
        while True:
            await asyncio.sleep(3600)

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    logger.info("Starting Astra Telegram Bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
