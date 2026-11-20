import os
import httpx
import asyncio
from typing import Optional, Dict, Any

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

    async def _call_gemini_rest(self, prompt: str, system_prompt: str) -> Optional[str]:
        if not self.api_key:
            return None
        models_to_try = [
            "gemini-2.5-flash",
            "gemini-3.8-flash",
            "gemini-3-flash-preview",
            "gemini-2.0-flash",
            "gemini-flash-lite-latest"
        ]
        async with httpx.AsyncClient(timeout=20.0) as client:
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
                payload = {
                    "systemInstruction": {"parts": [{"text": f"{system_prompt}\n\n{HTML_STYLE_INSTRUCTION}"}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 800
                    }
                }
                try:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            text_parts = [p["text"] for p in parts if "text" in p and not p.get("thought")]
                            if not text_parts:
                                text_parts = [p["text"] for p in parts if "text" in p]
                            if text_parts:
                                return "\n".join(text_parts)
                except Exception:
                    continue
        return None

    async def generate_kairos_reply_async(self, user_message: str, mode: str, project_context: Optional[str] = None, workload_info: Optional[str] = None) -> str:
        system_prompt = self._build_kairos_prompt(mode, project_context, workload_info)
        reply = await self._call_gemini_rest(user_message, system_prompt)
        if reply:
            return reply
        return "Салют! Я на связи ⚡️ Слышу тебя отлично, давай накидывать идеи!"

    async def generate_chrona_reply_async(self, user_message: str, current_schedule: str, projects_list: str) -> str:
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
"""
        reply = await self._call_gemini_rest(user_message, system_prompt)
        if reply:
            return reply
        return "Привет! Я тут и слежу за расписанием 🌸 Что у нас по планам?"

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
