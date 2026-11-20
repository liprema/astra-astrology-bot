import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bot.formatter import markdown_to_telegram_html, split_html_telegram_message, strip_html_tags
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from database import EcosystemDB
from llm_service import LLMService
from shared_bridge import BridgeService, should_bot_handle_message

load_dotenv()

KAIROS_TOKEN = os.getenv("KAIROS_BOT_TOKEN")
CHRONA_TOKEN = os.getenv("CHRONA_BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "data/ecosystem.db")

db = EcosystemDB(DB_PATH)
llm = LLMService()
bridge = BridgeService(db, chrona_token=CHRONA_TOKEN, kairos_token=KAIROS_TOKEN)

dp = Dispatcher()

def get_main_keyboard(user_id: int):
    active_projects = db.get_active_projects()
    kb = [
        [KeyboardButton(text="🏛 Steam: Мифология"), KeyboardButton(text="🕹 Яндекс.Игры")],
        [KeyboardButton(text="💡 Брейншторм / Бизнес"), KeyboardButton(text="🚀 Проекты в работе")],
        [KeyboardButton(text="⏳ Запрос к Хроне (Тайминги)")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    db.set_user_mode(user_id, "steam_myth")
    greeting = (
        "Салют! Я <b>Кайрос</b> — твой партнёр по вайбкодингу и бизнес-эдвайзер. ⚡️\n\n"
        "Мы работаем в связке с <b>Хроной</b> (она рулит расписанием и не даёт выгореть).\n\n"
        "В чём я могу помочь прямо сейчас:\n"
        "• 🏛 <b>Steam & Мифы</b> — лор Хроник Акаши, пантеоны богов, механики, вишлисты и страница игры.\n"
        "• 🕹 <b>Яндекс.Игры</b> — быстрые концепты, удержание, монетизация и WebGL.\n"
        "• 💡 <b>Бизнес-консалтинг</b> — разбор любых сторонних идей, MVP за выходные.\n"
        "• 🚀 <b>Взять в работу</b> — превратим любую идею в отдельный рабочий режим и сразу поставим слот в расписание Хроне!\n\n"
        "Выбирай режим внизу или просто пиши, что на уме!"
    )
    await message.answer(greeting, reply_markup=get_main_keyboard(user_id), parse_mode="HTML")

@dp.message(F.text == "🏛 Steam: Мифология")
async def mode_steam(message: types.Message):
    db.set_user_mode(message.from_user.id, "steam_myth")
    await message.answer("Включил режим <b>🏛 Steam: Мифология & Путешествия души</b>.\nПогружаемся в Хроники Акаши, пантеоны богов и нарратив. О какой главе или механике думаем?", parse_mode="HTML")

@dp.message(F.text == "🕹 Яндекс.Игры")
async def mode_yandex(message: types.Message):
    db.set_user_mode(message.from_user.id, "yandex_games")
    await message.answer("Переключил на режим <b>🕹 Яндекс.Игры</b>.\nФокус на быстрых циклах, высоком ретеншне и кликабельных механиках. Какую игру пилим или тестируем?", parse_mode="HTML")

@dp.message(F.text == "💡 Брейншторм / Бизнес")
async def mode_consulting(message: types.Message):
    db.set_user_mode(message.from_user.id, "consulting")
    await message.answer("Режим <b>💡 Бизнес-консалтинг</b> активен!\nНакидывай любые стартап-идеи или бизнес-гипотезы. Разберём ЦА, монетизацию, подводные камни. Если идея зайдёт — сразу возьмём в работу!", parse_mode="HTML")

@dp.message(F.text == "⏳ Запрос к Хроне (Тайминги)")
async def check_timings(message: types.Message):
    workload = bridge.get_workload_status_for_kairos("polina")
    await message.answer(f"🕒 <b>Сводка от Хроны по твоему расписанию:</b>\n\n{workload}\n\nЯ учитываю это при планировании наших спринтов!", parse_mode="HTML")

@dp.message(F.text == "🚀 Проекты в работе")
@dp.message(Command("projects"))
async def list_projects(message: types.Message):
    projects = db.get_active_projects()
    if not projects:
        await message.answer("Пока нет активных кастомных проектов в работе. Обсудим идею в режиме 💡 Брейншторм и запустим?")
        return

    text = "📁 <b>Твои активные проекты в работе:</b>\n\n"
    inline_kb = []
    for p in projects:
        text += f"• <b>{p['title']}</b> (Дедлайн: {p['deadline'] or 'не задан'})\n  Статус: <code>{p['status']}</code>\n\n"
        inline_kb.append([InlineKeyboardButton(text=f"🎯 Фокус: {p['title']}", callback_data=f"select_proj_{p['id']}")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb), parse_mode="HTML")

@dp.callback_query(F.data.startswith("select_proj_"))
async def on_project_selected(callback: types.CallbackQuery):
    proj_id = int(callback.data.split("_")[2])
    project = db.get_project_by_id(proj_id)
    if not project:
        await callback.answer("Проект не найден")
        return

    db.set_user_mode(callback.from_user.id, f"project_{proj_id}", active_project_id=proj_id)
    await callback.message.answer(
        f"🎯 Переключил рабочий контекст на проект: <b>«{project['title']}»</b>!\n"
        f"Все обсуждения и генерации теперь привязаны к нему.",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "take_in_work_current")
@dp.callback_query(F.data.startswith("take_in_work_"))
async def on_take_in_work(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    code = f"proj_{int(callback.message.date.timestamp())}"
    title = "Новая бизнес-инициатива"
    
    project_id = db.add_project(
        code=code,
        title=title,
        description="Проект создан по результатам брейншторма",
        category="custom_business",
        owner="polina"
    )
    db.set_user_mode(callback.from_user.id, f"project_{project_id}", active_project_id=project_id)
    await bridge.notify_chrona_about_new_project(project_id, user_chat_id=callback.from_user.id)
    
    await callback.message.answer(
        f"🚀 <b>Отлично, идея взята в работу!</b>\n\n"
        f"Создан проект ID #{project_id}.\n"
        f"Хрона уже получила уведомление и запланировала майлстоуны в твоем расписании!\n"
        f"Переименовать проект можно командой: <code>/rename &lt;новое_имя&gt;</code>.",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(Command("take"))
async def cmd_take_project(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Укажи название проекта, например:\n<code>/take Сервис открыток со славянскими богами</code>", parse_mode="HTML")
        return
        
    title = args[1].strip()
    code = f"proj_{int(message.date.timestamp())}"
    
    project_id = db.add_project(
        code=code,
        title=title,
        description="Запущен через прямое добавление",
        category="custom_business",
        owner="polina"
    )
    db.set_user_mode(message.from_user.id, f"project_{project_id}", active_project_id=project_id)
    await bridge.notify_chrona_about_new_project(project_id, user_chat_id=message.from_user.id)
    
    await message.answer(
        f"🚀 Проект <b>«{title}»</b> успешно запущен и взят в работу!\n"
        f"Режим переключен. Хрона добавила контрольные точки в твой календарь.",
        parse_mode="HTML"
    )

@dp.message()
async def on_user_message(message: types.Message, bot: Bot):
    if not message.text:
        return

    # В групповых чатах проверяем координацию с Хроной
    if message.chat.type in ("group", "supergroup"):
        bot_info = await bot.get_me()
        if not should_bot_handle_message(message.text, bot_name="kairos", bot_username=bot_info.username):
            return

    user_id = message.from_user.id
    state = db.get_user_mode(user_id)
    mode = state.get("active_mode", "steam_myth")
    
    project_context = None
    if mode.startswith("project_") and state.get("active_project_id"):
        proj = db.get_project_by_id(state["active_project_id"])
        if proj:
            project_context = f"Название: {proj['title']}\nОписание: {proj['description']}\nДедлайн: {proj['deadline']}"

    try:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    except Exception:
        pass

    workload = bridge.get_workload_status_for_kairos("polina")
    reply = await llm.generate_kairos_reply_async(
        user_message=message.text,
        mode=mode,
        project_context=project_context,
        workload_info=workload
    )
    
    inline_kb = None
    if mode == "consulting":
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Взять эту идею в работу!", callback_data="take_in_work_current")]
        ])
    
    try:
        formatted = markdown_to_telegram_html(reply)
        await message.answer(formatted, reply_markup=inline_kb, parse_mode="HTML")
    except Exception:
        try:
            await message.answer(strip_html_tags(reply), reply_markup=inline_kb)
        except Exception:
            await message.answer(reply, reply_markup=inline_kb)

async def main():
    if not KAIROS_TOKEN:
        print("❌ KAIROS_BOT_TOKEN не задан в .env!")
        return
    bot = Bot(token=KAIROS_TOKEN)
    print("⚡️ Кайрос (Вайбкодинг-партнёр) запущен и готов к работе...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
