import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from database import EcosystemDB
from llm_service import LLMService
from shared_bridge import should_bot_handle_message

load_dotenv()

CHRONA_TOKEN = os.getenv("CHRONA_BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "data/ecosystem.db")

db = EcosystemDB(DB_PATH)
llm = LLMService()
dp = Dispatcher()

def get_chrona_keyboard():
    kb = [
        [KeyboardButton(text="📅 Мой план на сегодня"), KeyboardButton(text="🗓 План на завтра")],
        [KeyboardButton(text="🎓 Академические дедлайны"), KeyboardButton(text="💼 Бизнес-слоты & Игры")],
        [KeyboardButton(text="📊 Семейный баланс (Я + Муж)")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    greeting = (
        "Привет! Я **Хрона** — твоя личная хранительница времени и баланса. 🌸\n\n"
        "Я слежу за вашим с мужем академическим и бизнес-расписанием, чтобы дедлайны соблюдались, "
        "а вайбкодинг не превращался в перегруз и бессонные ночи.\n\n"
        "Мы синхронизированы с **Кайросом**: когда вы берете новый проект в работу, "
        "он передает мне информацию, и я бронирую под него спринты.\n\n"
        "Что умею:\n"
        "• Вести раздельные графики: Учёба / Игры / Проекты\n"
        "• Следить за дедлайнами мужа по Яндекс.Играм и твоими по Steam\n"
        "• Добавлять дела на естественном языке (просто напиши мне дату и задачу)!\n\n"
        "Посмотрим расписание на сегодня?"
    )
    await message.answer(greeting, reply_markup=get_chrona_keyboard(), parse_mode="Markdown")

@dp.message(F.text == "📅 Мой план на сегодня")
async def plan_today(message: types.Message):
    today = datetime.now().strftime("%Y-%m-%d")
    items = db.get_schedule_for_date(today, user_role="polina")
    
    if not items:
        await message.answer("🌿 На сегодня в расписании пока нет зафиксированных слотов. Идеальный день для творческого потока или отдыха!")
        return

    text = f"📋 **Расписание на сегодня ({today}):**\n\n"
    for it in items:
        cat_icon = "🎓" if it["category"] == "academic" else "💼"
        text += f"{cat_icon} **{it['title']}**\n   Слот: {it['time_slot'] or 'В течение дня'}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🗓 План на завтра")
async def plan_tomorrow(message: types.Message):
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    items = db.get_schedule_for_date(tomorrow, user_role="polina")
    
    if not items:
        await message.answer("🌿 На завтра слотов пока нет. Напиши мне, если нужно что-то запланировать!")
        return

    text = f"📋 **Расписание на завтра ({tomorrow}):**\n\n"
    for it in items:
        cat_icon = "🎓" if it["category"] == "academic" else "💼"
        text += f"{cat_icon} **{it['title']}**\n   Слот: {it['time_slot'] or 'В течение дня'}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🎓 Академические дедлайны")
async def view_academic(message: types.Message):
    today = datetime.now().strftime("%Y-%m-%d")
    next_30 = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM schedule_items WHERE category = 'academic' AND scheduled_date >= ? ORDER BY scheduled_date ASC LIMIT 10", (today,))
        items = [dict(r) for r in cursor.fetchall()]

    if not items:
        await message.answer("🎓 Ближайших учебных дедлайнов не зафиксировано. Чтобы добавить, напиши, например:\n`/add_academic 2026-11-25 14:00 Зачет по философии`", parse_mode="Markdown")
        return

    text = "🎓 **Твои академические задачи и дедлайны:**\n\n"
    for it in items:
        text += f"• **{it['scheduled_date']}**: {it['title']} ({it['time_slot'] or 'Весь день'})\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "💼 Бизнес-слоты & Игры")
async def view_business(message: types.Message):
    active_projects = db.get_active_projects()
    text = "💼 **Проекты в работе и игровые спринты:**\n\n"
    if not active_projects:
        text += "Пока нет активных проектов.\n"
    else:
        for p in active_projects:
            text += f"• **{p['title']}** (Дедлайн: {p['deadline'] or 'в процессе'})\n"
            
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "📊 Семейный баланс (Я + Муж)")
async def view_family_balance(message: types.Message):
    today = datetime.now().strftime("%Y-%m-%d")
    next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    p_summary = db.get_user_workload_summary("polina", today, next_week)
    h_summary = db.get_user_workload_summary("husband", today, next_week)
    
    text = (
        "⚖️ **Семейный баланс на ближайшие 7 дней:**\n\n"
        f"🌸 **Полина:**\n"
        f"• Академические задачи: {p_summary.get('academic', 0)}\n"
        f"• Бизнес и геймдев (Steam): {p_summary.get('business', 0)}\n\n"
        f"⚡️ **Муж:**\n"
        f"• Игры (Яндекс.Игры) & Бизнес: {h_summary.get('business', 0)}\n"
        f"• Учёба / Академ: {h_summary.get('academic', 0)}\n\n"
        "💡 *Совет от Хроны: планируйте хотя бы один совместный вечер без кодинга и дедлайнов!*"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("add"))
async def cmd_add_task(message: types.Message):
    """Быстрое добавление задачи: /add <academic|business> <YYYY-MM-DD> <Описание>"""
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        await message.answer("Формат команды:\n`/add academic 2026-11-25 Сдать зачёт`\nили\n`/add business 2026-11-28 Релиз билда`", parse_mode="Markdown")
        return
        
    category = parts[1].lower()
    date_str = parts[2]
    title = parts[3]
    
    db.add_schedule_item(
        user_role="polina",
        title=title,
        category=category,
        scheduled_date=date_str,
        user_id=message.from_user.id
    )
    await message.answer(f"✅ Зафиксировала: **{title}** на `{date_str}` в категорию `{category}`!", parse_mode="Markdown")

@dp.message()
async def on_user_message(message: types.Message, bot: Bot):
    if not message.text:
        return

    # В групповых чатах проверяем координацию с Кайросом, чтобы не дублировать ответы
    if message.chat.type in ("group", "supergroup"):
        bot_info = await bot.get_me()
        if not should_bot_handle_message(message.text, bot_name="chrona", bot_username=bot_info.username):
            return
        
        # Атомарный захват сообщения в БД: если Кайрос уже ответил/отвечает, Хрона молчит
        # claim disabled
            return

    today = datetime.now().strftime("%Y-%m-%d")
    today_items = db.get_schedule_for_date(today)
    sched_summary = f"Событий на сегодня: {len(today_items)}"
    projects = db.get_active_projects()
    proj_summary = ", ".join([p["title"] for p in projects]) or "Нет активных проектов"
    
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    reply = await llm.generate_chrona_reply_async(
        user_message=message.text,
        current_schedule=sched_summary,
        projects_list=proj_summary
    )
    await message.answer(reply)

async def main():
    if not CHRONA_TOKEN:
        print("❌ CHRONA_BOT_TOKEN не задан в .env!")
        return
    bot = Bot(token=CHRONA_TOKEN)
    print("🌸 Хрона (Хранительница времени) запущена и готова к работе...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
