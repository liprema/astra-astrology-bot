"""
Main Telegram Bot Entrypoint for ARCANA ("Аркана") Tarot Bot + Built-in 24/7 Cloud Health Server.

Features:
1. Instant Wake-Word Trigger: Responds immediately whenever anyone writes "Аркана" / "Arcana"
   in any case, language, or grammatical form (in both private chats and group chats).
2. Strict Pre-Answer Verification: Always verifies WHO/WHAT the question is about,
   the context/timeframe, and whether Arcana should draw the cards or interpret user-drawn cards.
3. High-Resolution Tarot Spread Photo Generation & Delivery (with Upright/Reversed,
   Bottom of the Deck, Quintessence, and Elemental Dignities).
4. Multi-Tradition Synthesis (Rider-Waite-Smith, Crowley Thoth, Marseille/French, Golden Dawn, Jungian)
   with explicit school attribution & alternative school comparisons.
5. Book Library Management (`/books` + direct file or Yandex.Disk upload in chat).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Dict, List

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from bot.config import (
    BOOKS_DIR,
    DB_PATH,
    SPREADS_DIR,
    TELEGRAM_BOT_TOKEN,
    contains_arcana_wake_word,
)
from bot.knowledge_base import download_from_yandex_disk, extract_text_from_file, knowledge_base
from bot.llm_tarot import analyze_tarot_dialog_completeness, generate_tarot_interpretation
from bot.spread_renderer import render_spread_image
from bot.tarot_engine import draw_tarot_spread

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("arcana_bot")


class DialogStore:
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
        "🃏 **Приветствую! Я — Аркана (Arcana), ваш автономный таролог-эксперт всех школ Таро.**\n\n"
        "Я мгновенно откликаюсь, как только вы напишете моё имя **«Аркана»** / **«Arcana»** "
        "(в любом регистре, падеже и на любом языке).\n\n"
        "🔮 **В каких традициях и системах я работаю:**\n"
        "• **Английская классическая школа (Уэйт RWS и Орден Золотой Зари)**.\n"
        "• **Таро Тота Алистера Кроули** (каббалистические сефирот, астрологические деканы, телемитская система).\n"
        "• **Марсельское и Французское Таро** (Папюс, Элифас Леви, Ходоровски).\n"
        "• **Прямые и перевёрнутые карты**, расчёт **Дна колоды** (скрытого мотива), **Квинтэссенции** (итогового совета по сумме арканов) и **Элементальных достоинств** (баланса стихий).\n\n"
        "📐 **Как я работаю:**\n"
        "1. Перед раскладом я всегда уточняю **о ком или о чём идёт речь**, суть вопроса и режим работы (вытянуть ли карты мне самой или разобрать расклад, который вы выложили вживую).\n"
        "2. Строю и присылаю **красивую фотографию расклада** со всеми выпавшими картами, Дном колоды и Квинтэссенцией.\n"
        "3. В разборе **всегда указываю, на какую школу опираюсь**, а при разногласиях школ привожу **альтернативное мнение**.\n\n"
        "📚 Команда `/books` — посмотреть загруженные книги по Таро.\n"
        "🔄 Команда `/reset` — начать новый вопрос или новый расклад с чистого листа.\n\n"
        "*Напишите свой вопрос или просто позовите меня: «Аркана»!*"
    )
    await message.reply(welcome, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    store.clear_session(chat_id, user_id)
    store.mark_active(chat_id, user_id)
    await message.reply(
        "🔄 Колода перетасована, контекст очищен! Напишите, **о ком или о чём** ваш новый вопрос "
        "и какой расклад сделать.",
        parse_mode=ParseMode.MARKDOWN,
    )


@dp.message(Command("books"))
async def cmd_books(message: Message) -> None:
    summary = knowledge_base.load_or_build_index()
    lines = [
        "📚 **БАЗА КНИГ ПО ТАРО (АРКАНА)**",
        f"• Проиндексировано книг пользователя: **{summary['indexed_books_count']}**",
        f"• Всего смысловых фрагментов (включая канонический свод школ Таро): **{summary['total_chunks']}**",
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
    doc = message.document
    if not doc or not doc.file_name:
        return
    target_path = BOOKS_DIR / doc.file_name
    status_msg = await message.reply(f"📥 Загружаю и изучаю книгу по Таро `{doc.file_name}`...", parse_mode=ParseMode.MARKDOWN)
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
                f"✅ Книга `{doc.file_name}` успешно изучена и добавлена в базу знаний Арканы!\n"
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

    ydisk_match = re.search(r"https?://(?:disk\.yandex\.[a-z]+|yadi\.sk)/\S+", text, re.I)
    if ydisk_match:
        url = ydisk_match.group(0)
        wait_msg = await message.reply("☁️ Обнаружена ссылка на Яндекс.Диск! Скачиваю и проверяю книги...", parse_mode=ParseMode.MARKDOWN)
        downloaded, dl_errors = await asyncio.to_thread(download_from_yandex_disk, url, BOOKS_DIR)
        summary = await asyncio.to_thread(knowledge_base.load_or_build_index)
        report = [
            "📚 **Отчёт по загрузке книг с Яндекс.Диска:**",
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

    has_wake_word = contains_arcana_wake_word(text)
    is_reply_to_bot = bool(
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.is_bot
    )
    in_active_session = store.is_recently_active(chat_id, user_id)

    if not (has_wake_word or is_private or is_reply_to_bot or in_active_session):
        return

    store.mark_active(chat_id, user_id)
    store.add_message(chat_id, user_id, "user", text)

    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    stripped_without_wake = re.sub(
        r"(?:привет|здравствуй(?:те)?|добрый\s+день|добрый\s+вечер|алло|эй|слушай|аркана|аркану|аркане|арканой|arcana|arkana|αρκάνα|ארקנה|أركانا|अर्काना|[!?,.\s])+",
        "",
        text,
        flags=re.I,
    )
    history = store.get_history(chat_id, user_id, limit=10)

    if len(stripped_without_wake) < 3 and len(history) <= 2:
        instant_greeting = (
            "🃏 **Я здесь! Аркана на связи и готова к работе с колодой.**\n\n"
            "Перед тем как я вытяну карты или разберу ваш расклад, расскажите мне:\n"
            "1. **О ком или о чём ваш вопрос?** (назовите имена или роли участников, сферу — отношения, карьера, финансы, выбор — и загаданный срок).\n"
            "2. **Как делаем расклад?**\n"
            "   • Я сама вытягиваю карты и присылаю фото расклада (*Триплет 3 карты*, *На отношения 7 карт*, *Выбор 5 карт*, *Кельтский крест 10 карт* или *1 карта + Дно колоды*);\n"
            "   • Или вы сами выложили карты вживую и напишете мне, какие арканы выпали!\n\n"
            "Как только уточните детали — я сразу пришлю фотографию расклада и сделаю глубокий разбор по всем школам Таро!"
        )
        store.add_message(chat_id, user_id, "assistant", instant_greeting)
        await message.reply(instant_greeting, parse_mode=ParseMode.MARKDOWN)
        return

    analysis = await analyze_tarot_dialog_completeness(history)

    if not analysis.get("has_all_required_data"):
        clarification = analysis.get("missing_info_question_ru") or (
            "🃏 **Я на связи!** Чтобы расклад был максимально точным, уточните, пожалуйста:\n"
            "• **О ком или о чём именно вопрос** (имена/роли, сфера, срок)?\n"
            "• Вытянуть ли карты мне самой или вы напишете свои выпавшие карты?"
        )
        store.add_message(chat_id, user_id, "assistant", clarification)
        await message.reply(clarification, parse_mode=ParseMode.MARKDOWN)
        return

    ack_msg = await message.reply(
        "🕯 **Запрос принят!** Настраиваюсь на вопрос, тасую колоду, выкладываю арканы, "
        "фиксирую Дно колоды, рассчитываю Квинтэссенцию и готовлю фотографию расклада...",
        parse_mode=ParseMode.MARKDOWN,
    )

    spread_type = analysis.get("spread_type") or "triplet"
    subject_name = analysis.get("subject_name") or "Запрос Кверента"
    user_q = analysis.get("user_question") or text
    custom_cards = analysis.get("custom_cards")
    if isinstance(custom_cards, list) and len(custom_cards) == 0:
        custom_cards = None

    spread = await asyncio.to_thread(
        draw_tarot_spread,
        spread_type=spread_type,
        question=user_q,
        subject_name=subject_name,
        allow_reversed=True,
        custom_cards_query=custom_cards,
    )

    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
    img_filename = f"spread_{chat_id}_{int(time.time())}.png"
    img_path = SPREADS_DIR / img_filename
    await asyncio.to_thread(render_spread_image, spread, img_path)

    cards_brief = " | ".join(
        f"{c['position_index']}. {c['name_ru']} ({'⟲' if c['is_reversed'] else '↑'})"
        for c in spread["cards"][:5]
    )
    bot_card = spread["bottom_of_deck"]
    q_card = spread["quintessence"]["card"]

    photo_caption = (
        f"🃏 **{spread['spread_title']}**\n"
        f"🎯 *О ком/чём:* {subject_name}\n"
        f"🎴 *Карты:* {cards_brief}\n"
        f"🌊 *Дно колоды (скрытый мотив):* **[{bot_card['roman']}] {bot_card['name_ru']}** ({bot_card['orientation_ru']})\n"
        f"✨ *Квинтэссенция (Совет):* **[{q_card['roman']}] {q_card['name_ru']}**"
    )
    await message.reply_photo(
        photo=FSInputFile(img_path),
        caption=photo_caption[:1000],
        parse_mode=ParseMode.MARKDOWN,
    )

    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    search_query = " ".join(c["name_ru"] for c in spread["cards"]) + " " + user_q
    rag_passages = await asyncio.to_thread(knowledge_base.search, search_query, 5)

    reading = await generate_tarot_interpretation(
        spread=spread,
        user_question=user_q,
        rag_passages=rag_passages,
    )
    store.add_message(chat_id, user_id, "assistant", reading)

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
    return web.json_response({
        "status": "ok",
        "bot": "Arcana (Аркана) Multi-Tradition Tarot Bot",
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
    port = int(os.getenv("PORT", "8081"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Arcana health web server listening on port %d", port)
    return runner


async def main() -> None:
    runner = await start_background_web_server()
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TAROT_BOT_TOKEN is not set yet!")
        while True:
            await asyncio.sleep(3600)

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    logger.info("Starting Arcana Tarot Telegram Bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
