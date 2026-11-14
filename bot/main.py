"""
Main Telegram Bot Entrypoint for ASTRA ("Астра") + Built-in 24/7 Cloud Health Server.

Features:
1. Instant Wake-Word Trigger: Responds immediately whenever anyone writes "Астра" / "Astra"
   in any case, language, or grammatical form.
2. Full Conversation & Profile Memory: Remembers user/subject birth data, city, and full dialog
   history in SQLite so the user NEVER has to repeat the same information!
3. Smart Follow-Up Mode: When the user asks follow-up questions ("А что с финансами?",
   "Расскажи подробнее про 7 дом"), Astra answers immediately using the remembered chart
   without re-asking birth details or re-sending the same photo (unless a new chart is requested).
"""
from __future__ import annotations

import asyncio
import datetime
import json
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

from bot.astro_engine import calculate_full_chart, format_chart_for_llm, resolve_place
from bot.chart_renderer import render_chart_image
from bot.config import (
    BOOKS_DIR,
    CHARTS_DIR,
    DB_PATH,
    TELEGRAM_BOT_TOKEN,
    contains_astra_wake_word,
)
from bot.formatter import markdown_to_telegram_html, split_html_telegram_message, strip_html_tags
from bot.knowledge_base import download_from_yandex_disk, extract_text_from_file, knowledge_base
from bot.llm_astrologer import (
    analyze_dialog_completeness,
    generate_astra_chat_response,
    generate_astrological_interpretation,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("astra_bot")


class DialogStore:
    """SQLite-backed long-term conversation & profile memory."""

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
        """Keep session active for 24 hours so users can naturally continue the conversation."""
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
        "✨ **Приветствую! Я — Астра, твой профессиональный астролог.**\n\n"
        "Я строю натальные и хорарные карты с астрономической точностью (Швейцарские эфемериды) "
        "и провожу глубокий разбор сразу через оптику 5 школ: классической, психологической, эллинистической, уранической и Формулы Души.\n\n"
        "Я откликаюсь на имя **«Астра»**, **помню твои данные рождения** и после разбора всегда готова обсудить детали сессии или просто поговорить по душам.\n\n"
        "• Для построения карты и разбора запроса напиши дату (`ДД.ММ.ГГГГ`), точное время (`ЧЧ:ММ`), город рождения и свой вопрос.\n"
        "• `/reset` — очистить память текущей сессии для расчёта карты другого человека."
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
            "✨ Чистый лист! Я бережно отпустила прошлую карту. О ком поговорим или чьё небо посмотрим теперь?"
        ),
        parse_mode=ParseMode.HTML,
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

    await message.reply(markdown_to_telegram_html("\n".join(lines)), parse_mode=ParseMode.HTML)


@dp.message(F.document)
async def handle_book_document(message: Message, bot: Bot) -> None:
    doc = message.document
    if not doc or not doc.file_name:
        return
    target_path = BOOKS_DIR / doc.file_name
    status_msg = await message.reply(
        markdown_to_telegram_html(f"📥 Загружаю и изучаю книгу `{doc.file_name}`..."),
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
                    f"✅ Книга `{doc.file_name}` успешно изучена и добавлена в базу знаний Астры!\n"
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

    has_wake_word = contains_astra_wake_word(text)
    mentions_other_bot = bool(
        re.search(r"(?:аркан[аеуойы]|arcana|arkana|матрикс[ауеом]?|матриц[аеуейы]|matrix)", text, re.I)
    )
    is_reply_to_this_bot = bool(
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == bot.id
    )
    saved_profile = store.get_profile(chat_id, user_id)
    profile_incomplete = not (
        saved_profile.get("date_str") and saved_profile.get("time_str") and saved_profile.get("place_city")
    )
    # In group chats, auto-continue without wake word if the user is answering a pending data question (within 15 min)
    awaiting_data_in_group = (
        not is_private
        and store.is_recently_active(chat_id, user_id, ttl_seconds=900)
        and profile_incomplete
        and bool(
            re.search(
                r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{1,2}\s+(?:январ|феврал|март|апрел|ма[яй]|июн|июл|август|сентябр|октябр|ноябр|декабр)|\b(?:[01]?\d|2[0-3])[:.\-][0-5]\d\b|час|врем[яени]\s+не\s+знаю|г\.|город|москв|мск|петербург|питер|спб|екатеринбург|екб|казан|новосибирск|краснодар|сочи|самар|нижн|ростов|уф[ае]|красноярск|воронеж|перм|волгоград|саратов|тюмен|тольятти|ижевск|барнаул|ульяновск|иркутск|хабаровск|ярославл|владивосток|томск|оренбург|кемеров|рязан|астрахан|пенз|липецк|киров|тул[ае]|калининград|минск|алмат|астан|киев|ташкент|баку|ереван|тбилис|варшав|берлин|лондон|париж|дуба)",
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
        should_respond = has_wake_word or is_reply_to_this_bot or awaiting_data_in_group

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

    analysis = await analyze_dialog_completeness(history, saved_profile=saved_profile)

    store.update_profile(
        chat_id,
        user_id,
        {
            "subject_name": analysis.get("subject_name") or user_name_lbl or saved_profile.get("subject_name"),
            "chart_type": analysis.get("chart_type"),
            "date_str": analysis.get("date_str"),
            "time_str": analysis.get("time_str"),
            "place_city": analysis.get("place_city"),
        },
    )

    updated_profile = store.get_profile(chat_id, user_id)

    if not analysis.get("has_all_required_data") or analysis.get("intent") == "casual_chat":
        chat_reply = await generate_astra_chat_response(
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

    place_query = updated_profile.get("place_city") or analysis.get("place_city") or "Москва"
    date_str = updated_profile.get("date_str") or analysis.get("date_str") or "NOW"
    time_str = updated_profile.get("time_str") or analysis.get("time_str") or "NOW"
    chart_type = updated_profile.get("chart_type") or analysis.get("chart_type") or "natal"
    subject_name = updated_profile.get("subject_name") or analysis.get("subject_name") or "Карта"
    send_photo = bool(analysis.get("send_new_chart_photo", not updated_profile.get("has_rendered_chart")))

    ack_text = (
        "🔭 *Минутку, моя хорошая — открываю твоё небо и сверяю показатели по астрологическим школам...*"
        if send_photo
        else "✨ *Заглядываю в твою карту...*"
    )
    ack_msg = await message.reply(markdown_to_telegram_html(ack_text), parse_mode=ParseMode.HTML)

    try:
        geo = await asyncio.to_thread(resolve_place, place_query)
        if not geo:
            ask_city_again = (
                f"✨ Солнце моё, не могу найти на карте место **«{place_query}»**.\n"
                "Напиши, пожалуйста, название города чуть точнее (или ближайший крупный город — дату и время я уже бережно сохранила)!"
            )
            store.add_message(chat_id, user_id, "assistant", ask_city_again)
            await ack_msg.edit_text(markdown_to_telegram_html(ask_city_again), parse_mode=ParseMode.HTML)
            return

        try:
            if date_str == "NOW" or time_str == "NOW":
                import pytz
                tz_obj = pytz.timezone(geo.tz_name)
                dt_local = datetime.datetime.now(tz_obj).replace(tzinfo=None)
            else:
                d_parts = [int(x) for x in re.split(r"[./-]", date_str)]
                t_parts = [int(x) for x in re.split(r"[:.\-]", time_str)]
                dt_local = datetime.datetime(d_parts[2], d_parts[1], d_parts[0], t_parts[0], t_parts[1])
        except Exception:
            ask_date_again = (
                "✨ Подскажи, пожалуйста, дату и время в формате `ДД.ММ.ГГГГ ЧЧ:ММ` (например, `15.05.1995 14:30`), чтобы эфемериды посчитали всё до секунды!"
            )
            store.add_message(chat_id, user_id, "assistant", ask_date_again)
            await ack_msg.edit_text(markdown_to_telegram_html(ask_date_again), parse_mode=ParseMode.HTML)
            return

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
        store.update_profile(
            chat_id,
            user_id,
            {
                "has_rendered_chart": True,
                "chart_summary": format_chart_for_llm(chart),
            },
        )

        if send_photo:
            try:
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
                img_filename = f"chart_{chat_id}_{int(time.time())}.png"
                img_path = CHARTS_DIR / img_filename
                await asyncio.to_thread(render_chart_image, chart, img_path)

                photo_caption = (
                    f"✨ **Натальная карта: {subject_name}**\n"
                    f"📅 `{chart['dt_local_str']}` • 📍 {place_query}\n"
                    f"🏛 Дома: {chart['house_system']} + Полнознаковая система | {chart['hellenistic_medieval']['sect']}\n"
                    f"⬆️ **Асцендент (ASC):** {chart['asc']['formatted']} | **MC:** {chart['mc']['formatted']}"
                )
                await message.reply_photo(
                    photo=FSInputFile(img_path),
                    caption=markdown_to_telegram_html(photo_caption),
                    parse_mode=ParseMode.HTML,
                )
                store.update_profile(chat_id, user_id, {"has_rendered_chart": True})
            except Exception as photo_err:
                logger.error("Chart photo send error: %s", photo_err)

        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        user_q = analysis.get("user_question") or text
        search_query = f"{user_q} {chart['asc']['sign']} Солнце {chart['planets'][0]['sign']} Луна {chart['planets'][1]['sign']} {chart_type}"
        rag_passages = await asyncio.to_thread(knowledge_base.search, search_query, 6)

        reading = await generate_astrological_interpretation(
            chart=chart,
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
        logger.exception("Error while processing astrological chart: %s", exc)
        err_text = "✨ Произошла секундная заминка при расчёте эфемерид — повтори, пожалуйста, своё последнее сообщение!"
        try:
            await ack_msg.edit_text(markdown_to_telegram_html(err_text), parse_mode=ParseMode.HTML)
        except Exception:
            await message.reply(err_text)


async def health_handler(request: web.Request) -> web.Response:
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
        logger.warning("TELEGRAM_BOT_TOKEN is not set in .env yet!")
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
