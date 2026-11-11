"""
Main Telegram Bot Entrypoint for ARCANA ("Аркана") Tarot Bot + Built-in 24/7 Cloud Health Server.

Features:
1. Instant Wake-Word Trigger: Responds immediately whenever anyone writes "Аркана" / "Arcana"
   in any case, language, or grammatical form.
2. Full Conversation & Spread Memory: Remembers the user's subject/context, previous spreads,
   and full dialog history in SQLite so the user NEVER has to repeat the same information!
3. Smart Follow-Up Mode: When the user asks follow-up questions about an already drawn spread
   ("А что значит 2 карта?", "А почему на дне Отшельник?"), Arcana answers immediately from memory
   without forcing the user to repeat their question or reshuffling cards unless a new spread is requested.
4. Rich Telegram HTML Formatting: Clean bold headers, blockquotes, dividers, and typographic bullets.
"""
from __future__ import annotations

import asyncio
import json
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
from bot.formatter import markdown_to_telegram_html, split_html_telegram_message, strip_html_tags
from bot.knowledge_base import download_from_yandex_disk, extract_text_from_file, knowledge_base
from bot.llm_tarot import (
    analyze_tarot_dialog_completeness,
    generate_arcana_chat_response,
    generate_tarot_interpretation,
)
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    profile_json TEXT NOT NULL,
                    updated_at REAL NOT NULL,
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

    def is_recently_active(self, chat_id: int, user_id: int, ttl_seconds: int = 86400) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT last_active FROM active_sessions WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return False
            return (time.time() - float(row[0])) <= ttl_seconds

    def get_profile(self, chat_id: int, user_id: int) -> Dict:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT profile_json FROM user_profiles WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return {}
            try:
                return json.loads(row[0])
            except Exception:
                return {}

    def update_profile(self, chat_id: int, user_id: int, updates: Dict) -> Dict:
        current = self.get_profile(chat_id, user_id)
        for k, v in updates.items():
            if v is not None and v != "":
                current[k] = v
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO user_profiles (chat_id, user_id, profile_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    profile_json = excluded.profile_json,
                    updated_at = excluded.updated_at
                """,
                (chat_id, user_id, json.dumps(current, ensure_ascii=False), time.time()),
            )
        return current

    def clear_session(self, chat_id: int, user_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM messages WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            conn.execute("DELETE FROM active_sessions WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            conn.execute("DELETE FROM user_profiles WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))

    def add_message(self, chat_id: int, user_id: int, role: str, content: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO messages (chat_id, user_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (chat_id, user_id, role, content, time.time()),
            )

    def get_history(self, chat_id: int, user_id: int, limit: int = 30) -> List[Dict[str, str]]:
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


@dp.message(Command("start", "help"))
async def cmd_start(message: Message) -> None:
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    store.mark_active(chat_id, user_id)

    welcome = (
        "🃏 **Привет! Я — Аркана, профессиональный таролог.**\n\n"
        "Розовые очки снимаю быстро, расклады читаю глубоко и без воды — сразу через системы Уэйта, Таро Тота Алистера Кроули, Марсельский канон и соответствия Ордена Золотой Зари.\n\n"
        "Я откликаюсь на имя **«Аркана»**, **помню выложенный расклад** и после сессии с удовольствием обсужу с тобой все детали, отвечу на дополнительные вопросы или просто перемою косточки ситуации.\n\n"
        "• Опиши свою ситуацию или вопрос (любовь, карьера, финансы, сложный выбор) — я сразу выложу карты и сделаю разбор.\n"
        "• `/reset` — перетасовать колоду и начать новую сессию."
    )
    await message.reply(markdown_to_telegram_html(welcome), parse_mode=ParseMode.HTML)


@dp.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    store.clear_session(chat_id, user_id)
    store.mark_active(chat_id, user_id)
    await message.reply(
        markdown_to_telegram_html(
            "🃏 Колода перетасована, прошлые грехи забыты! Ну давай, выкладывай — кого или что разбираем на этот раз?"
        ),
        parse_mode=ParseMode.HTML,
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

    await message.reply(markdown_to_telegram_html("\n".join(lines)), parse_mode=ParseMode.HTML)


@dp.message(F.document)
async def handle_book_document(message: Message, bot: Bot) -> None:
    doc = message.document
    if not doc or not doc.file_name:
        return
    target_path = BOOKS_DIR / doc.file_name
    status_msg = await message.reply(
        markdown_to_telegram_html(f"📥 Загружаю и изучаю книгу по Таро `{doc.file_name}`..."),
        parse_mode=ParseMode.HTML,
    )
    try:
        file_info = await bot.get_file(doc.file_id)
        await bot.download_file(file_info.file_path, destination=target_path)
        text, err = extract_text_from_file(target_path)
        summary = knowledge_base.load_or_build_index()
        if err:
            await status_msg.edit_text(
                markdown_to_telegram_html(
                    f"⚠️ Я сохранила файл `{doc.file_name}`, но **не смогла его прочитать**:\n"
                    f"Причина: *{err}*\n\nПожалуйста, пришлите текстовую версию (PDF с текстом, DOCX, FB2, EPUB или TXT)."
                ),
                parse_mode=ParseMode.HTML,
            )
        else:
            await status_msg.edit_text(
                markdown_to_telegram_html(
                    f"✅ Книга `{doc.file_name}` успешно изучена и добавлена в базу знаний Арканы!\n"
                    f"Всего фрагментов в базе: **{summary['total_chunks']}**."
                ),
                parse_mode=ParseMode.HTML,
            )
    except Exception as exc:
        await status_msg.edit_text(f"❌ Ошибка при загрузке файла {doc.file_name}: {exc}")


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
        wait_msg = await message.reply(
            markdown_to_telegram_html("☁️ Обнаружена ссылка на Яндекс.Диск! Скачиваю и проверяю книги..."),
            parse_mode=ParseMode.HTML,
        )
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
        await wait_msg.edit_text(markdown_to_telegram_html("\n".join(report)), parse_mode=ParseMode.HTML)
        return

    has_wake_word = contains_arcana_wake_word(text)
    mentions_other_bot = bool(
        re.search(r"(?:астр[аеуойы]|astra|матрикс[ауеом]?|матриц[аеуейы]|matrix)", text, re.I)
    )
    is_reply_to_this_bot = bool(
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == bot.id
    )
    saved_profile = store.get_profile(chat_id, user_id)
    awaiting_topic_in_group = (
        not is_private
        and store.is_recently_active(chat_id, user_id, ttl_seconds=600)
        and not saved_profile.get("last_spread")
    )

    if mentions_other_bot and not has_wake_word and not is_reply_to_this_bot:
        return

    if is_private:
        should_respond = True
    else:
        should_respond = has_wake_word or is_reply_to_this_bot or awaiting_topic_in_group

    if not should_respond:
        return

    store.mark_active(chat_id, user_id)
    store.add_message(chat_id, user_id, "user", text)

    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    history = store.get_history(chat_id, user_id, limit=26)

    analysis = await analyze_tarot_dialog_completeness(history, saved_profile=saved_profile)

    store.update_profile(
        chat_id,
        user_id,
        {
            "subject_name": analysis.get("subject_name"),
            "spread_type": analysis.get("spread_type"),
        },
    )

    updated_profile = store.get_profile(chat_id, user_id)

    if not analysis.get("has_all_required_data") or analysis.get("intent") == "casual_chat":
        chat_reply = await generate_arcana_chat_response(
            user_message=text,
            history_messages=history,
            saved_profile=updated_profile,
            missing_info_hint=analysis.get("missing_info_question_ru") or "",
        )
        store.add_message(chat_id, user_id, "assistant", chat_reply)
        for part in split_html_telegram_message(chat_reply):
            try:
                await message.reply(part, parse_mode=ParseMode.HTML)
            except Exception:
                await message.reply(strip_html_tags(part))
        return

    spread_type = analysis.get("spread_type") or updated_profile.get("spread_type") or "triplet"
    subject_name = analysis.get("subject_name") or updated_profile.get("subject_name") or "Запрос Кверента"
    user_q = analysis.get("user_question") or text
    custom_cards = analysis.get("custom_cards")
    if isinstance(custom_cards, list) and len(custom_cards) == 0:
        custom_cards = None

    draw_new = bool(analysis.get("draw_new_spread", True)) or not updated_profile.get("last_spread")

    ack_text = (
        "🕯 *Тасую колоду, дорогая... Сейчас посмотрим, что там на самом деле на дне и в раскладе.*"
        if draw_new
        else "🃏 *Смотрю в твой расклад...*"
    )
    ack_msg = await message.reply(markdown_to_telegram_html(ack_text), parse_mode=ParseMode.HTML)

    try:
        if draw_new:
            spread = await asyncio.to_thread(
                draw_tarot_spread,
                spread_type=spread_type,
                question=user_q,
                subject_name=subject_name,
                allow_reversed=True,
                custom_cards_query=custom_cards,
            )
            store.update_profile(chat_id, user_id, {"last_spread": spread})

            try:
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
                img_filename = f"spread_{chat_id}_{int(time.time())}.png"
                img_path = SPREADS_DIR / img_filename
                await asyncio.to_thread(render_spread_image, spread, img_path)

                cards_brief = " • ".join(
                    f"{c['position_index']}. {c['name_ru']} ({'⟲' if c['is_reversed'] else '↑'})"
                    for c in spread["cards"][:5]
                )
                bot_card = spread["bottom_of_deck"]
                q_card = spread["quintessence"]["card"]

                photo_caption = (
                    f"🃏 **{spread['spread_title']}**\n"
                    f"🎯 *Запрос:* {subject_name}\n"
                    f"🎴 *Выпавшие карты:* {cards_brief}\n"
                    f"🌊 *Дно колоды (скрытый мотив):* **[{bot_card['roman']}] {bot_card['name_ru']}** ({bot_card['orientation_ru']})\n"
                    f"✨ *Квинтэссенция (Совет):* **[{q_card['roman']}] {q_card['name_ru']}**"
                )
                await message.reply_photo(
                    photo=FSInputFile(img_path),
                    caption=markdown_to_telegram_html(photo_caption)[:1000],
                    parse_mode=ParseMode.HTML,
                )
            except Exception as photo_err:
                logger.error("Spread photo send error: %s", photo_err)
        else:
            spread = updated_profile["last_spread"]

        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        search_query = " ".join(c["name_ru"] for c in spread["cards"]) + " " + user_q
        rag_passages = await asyncio.to_thread(knowledge_base.search, search_query, 5)

        reading = await generate_tarot_interpretation(
            spread=spread,
            user_question=user_q,
            rag_passages=rag_passages,
            history_messages=history,
            is_followup=(not draw_new),
        )
        store.add_message(chat_id, user_id, "assistant", reading)

        try:
            await ack_msg.delete()
        except Exception:
            pass

        for part in split_html_telegram_message(reading):
            try:
                await message.reply(part, parse_mode=ParseMode.HTML)
            except Exception:
                await message.reply(strip_html_tags(part))
    except Exception as exc:
        logger.exception("Error while processing Tarot spread: %s", exc)
        err_text = "🃏 Карты чуть заискрили в колоде — повтори свой вопрос ещё раз, дорогая!"
        try:
            await ack_msg.edit_text(markdown_to_telegram_html(err_text), parse_mode=ParseMode.HTML)
        except Exception:
            await message.reply(err_text)


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
