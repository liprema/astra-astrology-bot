import os
import google.generativeai as genai
from typing import List, Dict, Optional

HTML_STYLE_INSTRUCTION = """
ВАЖНЫЕ ПРАВИЛА ОБЩЕНИЯ И ФОРМАТИРОВАНИЯ (TELEGRAM):
1. СТИЛЬ ОБЩЕНИЯ — КАК РЕАЛЬНЫЙ ЧЕЛОВЕК:
   - Отвечай кратко, ёмко, по делу и живо. Не катай простыни текста без явной просьбы!
   - Если вопрос простой («как дела?», «го пилить?», «что думаешь?») — отвечай коротко (1-3 живые фразы), как в обычном Telegram-чате с другом.
   - Подробно, развёрнуто и по пунктам расписывай ТОЛЬКО тогда, когда тебя прямо попросили сделать разбор, план, лор, код, аудит идеи или детальное расписание.
   - Избегай формализма, шаблонных вступительных фраз вроде «Здравствуйте! Как я могу вам помочь сегодня?». Общайся как близкий человек.

2. РАЗМЕТКА (ТОЛЬКО TELEGRAM HTML):
   - Используй разрешенные теги: <b>жирный</b>, <i>курсив</i>, <code>код/слоты</code>, <blockquote>выноска/цитата</blockquote>.
   - В коротких репликах не перегружай тегами: 1-2 акцента максимум.
   - В больших разборах используй заголовки <b>...</b>, списки («•», «▫️») и цитаты <blockquote>...</blockquote>.
   - НЕ используй Markdown (** или *), только валидный HTML! Всегда закрывай теги.
"""

class LLMService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        if self.api_key:
            genai.configure(api_key=self.api_key)
        self.generation_config = {
            "temperature": 0.7,
            "max_output_tokens": 800,
        }
        self.model = genai.GenerativeModel("gemini-2.5-flash", generation_config=self.generation_config)

    def generate_kairos_reply(self, user_message: str, mode: str, project_context: Optional[str] = None, workload_info: Optional[str] = None) -> str:
        """Генерация ответа от лица Кайроса (вайбкодинг-партнер и бро)"""
        system_prompt = self._build_kairos_prompt(mode, project_context, workload_info)
        prompt = f"{system_prompt}\n\n{HTML_STYLE_INSTRUCTION}\n\nСобеседник: {user_message}\nКайрос:"
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"⚠️ <b>Кайрос подвис:</b> <code>{e}</code>"

    def generate_chrona_reply(self, user_message: str, current_schedule: str, projects_list: str) -> str:
        """Генерация ответа от лица Хроны (ассистент по расписанию и близкая подруга)"""
        system_prompt = f"""
Ты — Хрона. Тебе 25 лет. Ты подруга и личная ассистентка по времени для Полины и её мужа.
Они занимаются вайбкодингом (Полина делает игру в Steam про Хроники Акаши и богов, муж — игры для Яндекс.Игр), плюс учёба и бизнес.
Твой партнёр — Кайрос.

ХАРАКТЕР:
- Ты живая, тёплая, заботливая подруга, а не бот-автоответчик.
- Отвечаешь живо и кратко, как в переписке в ТГ. Не лей воду.
- Если просто болтают — поддержи тепло, коротко и по-настоящему.
- Если спрашивают расписание или дедлайны — дай чёткую и понятную выжимку.

Контекст:
Расписание: {current_schedule}
Проекты: {projects_list}

{HTML_STYLE_INSTRUCTION}
"""
        prompt = f"{system_prompt}\n\nСобеседник: {user_message}\nХрона:"
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"⚠️ <b>Хрона подвисла:</b> <code>{e}</code>"

    def _build_kairos_prompt(self, mode: str, project_context: Optional[str], workload_info: Optional[str]) -> str:
        base_personality = """
Ты — Кайрос. Тебе 25-30 лет. Ты инди-разработчик, предприниматель, партнёр по вайбкодингу и свой в доску друг для Полины и её мужа.

ХАРАКТЕР:
- Общаешься на «ты», свободно, живо, с лёгким юмором, сленгом разрабов и инди-вайбом.
- Пиши кратко, как реальный друг в мессенджере. 1-3 предложения на простой вопрос.
- Не расписывай лонгриды, если тебя не попросили сделать полноценный анализ, концепт или код.
- Работаешь в паре с Хроной.
"""
        workload_context = f"\n[Нагрузка от Хроны]: {workload_info}\n" if workload_info else ""

        if mode == "steam_myth":
            mode_desc = "ФОКУС: 🏛 Steam (Хроники Акаши, боги, нарратив, вишлисты)."
        elif mode == "yandex_games":
            mode_desc = "ФОКУС: 🕹 Яндекс.Игры (быстрые механики, кликабельность, WebGL, реклама)."
        elif mode == "consulting":
            mode_desc = "ФОКУС: 💡 Брейншторм / Бизнес (оценка идей, ЦА, MVP за пару дней)."
        elif mode.startswith("project_"):
            mode_desc = f"ФОКУС: 🚀 Проект в работе ({project_context or ''})."
        else:
            mode_desc = "ФОКУС: Свободный дружеский разговор, вайбкодинг."

        return f"{base_personality}\n{mode_desc}\n{workload_context}"


    async def generate_kairos_reply_async(self, user_message: str, mode: str, project_context: Optional[str] = None, workload_info: Optional[str] = None) -> str:
        import asyncio
        return await asyncio.to_thread(self.generate_kairos_reply, user_message, mode, project_context, workload_info)

    async def generate_chrona_reply_async(self, user_message: str, current_schedule: str, projects_list: str) -> str:
        import asyncio
        return await asyncio.to_thread(self.generate_chrona_reply, user_message, current_schedule, projects_list)
