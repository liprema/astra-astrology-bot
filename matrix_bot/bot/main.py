"""
Main Telegram Bot Entrypoint for MATRIX ("Матрица") Numerology Bot + Built-in 24/7 Cloud Health Server.

Features:
1. Instant Wake-Word Trigger: Responds immediately whenever anyone writes "Матрица" / "Matrix"
   in any case, language, or grammatical form.
2. Full Conversation & Profile Memory: Remembers the user's birth date, full name, partner date,
   and full dialog history in SQLite so the user NEVER has to repeat the same information!
3. High-Resolution Numerological Image Generation & Delivery (Pythagorean Square 3×3 +
   22-Arcana Matrix of Destiny Octagram + Multi-School Summary Table).
4. Rich Telegram HTML Formatting.
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
from typing import Dict, List, Optional, Tuple

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from bot.config import (
    BOOKS_DIR,
    CHARTS_DIR,
    DB_PATH,
    TELEGRAM_BOT_TOKEN,
    contains_matrix_wake_word,
)
from bot.formatter import markdown_to_telegram_html, split_html_telegram_message, strip_html_tags
from bot.knowledge_base import download_from_yandex_disk, extract_text_from_file, knowledge_base
from bot.llm_numerology import (
    analyze_matrix_dialog_completeness,
    generate_matrix_chat_response,
    generate_numerology_interpretation,
)
from bot.matrix_renderer import render_numerology_image
from bot.numerology_engine import ARCANA_22_NAMES, calculate_full_numerology, format_numerology_for_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("matrix_bot")


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
        "🔢 **Привет! Я — Матрикс (Матрица), профессиональный нумеролог-аналитик и взломщица числовых кодов.**\n\n"
        "Я рассчитываю полную нумерологическую архитектуру личности сразу по 6 школам: Квадрат Пифагора (Психоматрица), 22 Аркана Матрицы Судьбы, классическая западная нумерология и Финансовый код, Халдейская нумерология имени и Ведическая Санкхья-шастра.\n\n"
        "Я откликаюсь на имя **«Матрикс»** или **«Матрица»**, **помню твои расчёты** и после разбора всегда готова докрутить любой вопрос или поболтать об инсайтах сессии.\n\n"
        "• Напиши дату рождения (`ДД.ММ.ГГГГ`), имя и свой запрос — я сразу построю твою Матрицу и сделаю полный разбор.\n"
        "• `/reset` — обнулить сессию для расчёта нового человека."
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
            "🔢 Бабах! Матрица обнулена, калькулятор дымится от нетерпения! Чью дату рождения взламываем теперь?"
        ),
        parse_mode=ParseMode.HTML,
    )


@dp.message(Command("books"))
async def cmd_books(message: Message) -> None:
    summary = knowledge_base.load_or_build_index()
    lines = [
        "📚 **БАЗА КНИГ ПО НУМЕРОЛОГИИ (МАТРИКС)**",
        f"• Проиндексировано книг пользователя: **{summary['indexed_books_count']}**",
        f"• Всего смысловых фрагментов (включая канонический свод школ Нумерологии): **{summary['total_chunks']}**",
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
        markdown_to_telegram_html(f"📥 Загружаю и изучаю книгу по нумерологии `{doc.file_name}`..."),
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
                    f"✅ Книга `{doc.file_name}` успешно изучена и добавлена в базу знаний Матрикса!\n"
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

    has_wake_word = contains_matrix_wake_word(text)
    mentions_other_bot = bool(
        re.search(r"(?:астр[аеуойы]|astra|аркан[аеуойы]|arcana|arkana)", text, re.I)
    )
    is_reply_to_this_bot = bool(
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == bot.id
    )
    saved_profile = store.get_profile(chat_id, user_id)
    awaiting_date_in_group = (
        not is_private
        and store.is_recently_active(chat_id, user_id, ttl_seconds=900)
        and not saved_profile.get("date_str")
        and bool(
            re.search(
                r"(\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b|\b(?:19|20)\d{2}[./-]\d{1,2}[./-]\d{1,2}\b|\b\d{1,2}\s+(?:январ|феврал|март|апрел|ма[яй]|июн|июл|август|сентябр|октябр|ноябр|декабр))",
                text,
                re.I,
            )
        )
    )

    if mentions_other_bot and not has_wake_word and not is_reply_to_this_bot:
        return

    if is_private:
        should_respond = True
    else:
        should_respond = has_wake_word or is_reply_to_this_bot or awaiting_date_in_group

    if not should_respond:
        return

    store.mark_active(chat_id, user_id)
    reply_ctx = ""
    if message.reply_to_message:
        r_txt = (message.reply_to_message.text or message.reply_to_message.caption or "").strip()
        if r_txt:
            reply_ctx = f"[В ответ на сообщение: «{r_txt[:350]}»]\n"
    user_name_lbl = (message.from_user.first_name if message.from_user and message.from_user.first_name else "").strip()
    store.add_message(chat_id, user_id, "user", f"{reply_ctx}{text}")

    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    history = store.get_history(chat_id, user_id, limit=30)

    analysis = await analyze_matrix_dialog_completeness(history, saved_profile=saved_profile)

    store.update_profile(
        chat_id,
        user_id,
        {
            "subject_label": analysis.get("subject_label"),
            "full_name": analysis.get("full_name") or user_name_lbl or saved_profile.get("full_name"),
            "date_str": analysis.get("date_str"),
            "partner_date_str": analysis.get("partner_date_str"),
        },
    )

    updated_profile = store.get_profile(chat_id, user_id)

    if not analysis.get("has_all_required_data") or analysis.get("intent") == "casual_chat":
        chat_reply = await generate_matrix_chat_response(
            user_message=f"{reply_ctx}{text}",
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

    date_str = updated_profile.get("date_str") or analysis.get("date_str")
    partner_date_str = updated_profile.get("partner_date_str") or analysis.get("partner_date_str")
    full_name = updated_profile.get("full_name") or analysis.get("full_name") or ""
    subject_label = updated_profile.get("subject_label") or analysis.get("subject_label") or full_name or "Нумерологическая Матрица"
    send_photo = bool(analysis.get("send_new_matrix_photo", not updated_profile.get("has_rendered_matrix")))

    try:
        d_parts = [int(x) for x in re.split(r"[./-]", date_str)]
        day, month, year = d_parts[0], d_parts[1], d_parts[2]
    except Exception:
        ask_date_again = "🔢 Стой-стой-стой, у меня цифры разбежались! Напиши дату рождения в формате `ДД.ММ.ГГГГ` (например: `15.05.1995`), чтобы я взломала твой код!"
        store.add_message(chat_id, user_id, "assistant", ask_date_again)
        await message.reply(markdown_to_telegram_html(ask_date_again), parse_mode=ParseMode.HTML)
        return

    partner_tuple: Optional[Tuple[int, int, int]] = None
    if partner_date_str:
        try:
            p_parts = [int(x) for x in re.split(r"[./-]", partner_date_str)]
            partner_tuple = (p_parts[0], p_parts[1], p_parts[2])
        except Exception:
            partner_tuple = None

    ack_text = (
        "🔢 *Держите меня семеро — взламываю твой Квадрат Пифагора и Октаграмму Матрицы Судьбы!..*"
        if send_photo
        else "🔮 *Заглядываю в твою числовую Матрицу...*"
    )
    ack_msg = await message.reply(markdown_to_telegram_html(ack_text), parse_mode=ParseMode.HTML)

    try:
        num_data = await asyncio.to_thread(
            calculate_full_numerology,
            day=day,
            month=month,
            year=year,
            full_name=full_name,
            subject_label=subject_label,
            partner_date=partner_tuple,
        )
        store.update_profile(
            chat_id,
            user_id,
            {
                "has_rendered_matrix": True,
                "matrix_summary": format_numerology_for_llm(num_data),
            },
        )

        if send_photo:
            try:
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
                img_filename = f"matrix_{chat_id}_{int(time.time())}.png"
                img_path = CHARTS_DIR / img_filename
                await asyncio.to_thread(render_numerology_image, num_data, img_path)

                dm = num_data["destiny_matrix_22"]
                w = num_data["western"]
                v = num_data["vedic"]
                photo_caption = (
                    f"🔢 **Нумерологическая Матрица: {subject_label} ({num_data['date_str']})**\n"
                    f"🌟 **ЧЖП:** {w['life_path']} • **Финансовый код:** `{w['financial_code']}`\n"
                    f"💎 **Центр Матрицы Судьбы:** {ARCANA_22_NAMES[dm['center_comfort_zone']]}\n"
                    f"🧬 **Кармический хвост:** `{dm['karmic_tail']}` • **Денежный канал:** `{dm['money_channel']}`\n"
                    f"🕉 **Ведическая Санкхья:** Душа {v['soul_number']} ({v['soul_planet']}), Судьба {v['destiny_number']} ({v['destiny_planet']})"
                )
                await message.reply_photo(
                    photo=FSInputFile(img_path),
                    caption=markdown_to_telegram_html(photo_caption)[:1000],
                    parse_mode=ParseMode.HTML,
                )
                store.update_profile(chat_id, user_id, {"has_rendered_matrix": True})
            except Exception as photo_err:
                logger.error("Matrix photo send error: %s", photo_err)

        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        user_q = analysis.get("user_question") or text
        search_query = f"{user_q} Квадрат Пифагора Матрица Судьбы Санкхья Халдейская"
        rag_passages = await asyncio.to_thread(knowledge_base.search, search_query, 5)

        reading = await generate_numerology_interpretation(
            data=num_data,
            user_question=user_q,
            rag_passages=rag_passages,
            history_messages=history,
            is_followup=(not send_photo),
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
        logger.exception("Error while processing Numerology Matrix: %s", exc)
        err_text = "🔢 Цифры так разогнались, что калькулятор заискрил — повтори своё последнее сообщение ещё раз!"
        try:
            await ack_msg.edit_text(markdown_to_telegram_html(err_text), parse_mode=ParseMode.HTML)
        except Exception:
            await message.reply(err_text)


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({
        "status": "ok",
        "bot": "Matrix (Матрица) Multi-Tradition Numerology Bot",
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
    port = int(os.getenv("PORT", "8082"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Matrix health web server listening on port %d", port)
    return runner


async def main() -> None:
    runner = await start_background_web_server()
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("MATRIX_BOT_TOKEN is not set yet!")
        while True:
            await asyncio.sleep(3600)

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    logger.info("Starting Matrix Numerology Telegram Bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
