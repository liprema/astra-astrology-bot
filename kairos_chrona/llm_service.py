from datetime import datetime, timezone, timedelta

RU_MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}
WEEKDAYS_RU = {
    0: "понедельник", 1: "вторник", 2: "среда", 3: "четверг",
    4: "пятница", 5: "суббота", 6: "воскресенье"
}

def get_live_calendar_banner() -> str:
    now = datetime.now(timezone(timedelta(hours=3)))
    m = RU_MONTHS.get(now.month, "ноября")
    w = WEEKDAYS_RU.get(now.weekday(), "суббота")
    return f"РЕАЛЬНОЕ ВРЕМЯ И ДЕНЬ: {w.upper()}, {now.day} {m} {now.year} года, {now.strftime('%H:%M')} по Москве. (Сейчас УЖЕ {w.upper()})."

import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
import asyncio
from typing import Optional, Dict, Any, List

HTML_STYLE_INSTRUCTION = """
ВАЖНЫЕ ПРАВИЛА ОБЩЕНИЯ И РАЗМЕТКИ (TELEGRAM):
1. ДВУХРЕЖИМНОЕ ПОВЕДЕНИЕ (СУПЕР-ВАЖНО):
   А. ДРУЖЕСКИЙ ТРЁП И БОЛТОВНЯ:
      - Если вопрос простой, дружеский или бытовой («как дела?», «го пилить?», «что думаешь?», «привет», «как настроение?») — отвечай КОРОТКО (1-3 живые, душевные фразы), как лучший друг в Telegram. Без простыней!
   Б. ПРОФЕССИОНАЛЬНЫЙ ЗАПРОС:
      - Если тебя просят сделать разбор, план, прописать лор, механику, квест, вишлисты, код, баланс, расписание, стратегию или бизнес-модель — отвечай СУПЕР-ПОДРОБНО, обстоятельно, структурированно, шаг за шагом, с примерами и конкретикой, не жалея деталей!

2. РАЗМЕТКА (ТОЛЬКО TELEGRAM HTML):
   - Разрешённые теги: <b>жирный</b>, <i>курсив</i>, <code>код/слот</code>, <blockquote>цитата</blockquote>.
   - НЕ используй Markdown (** или *), только валидный HTML! Всегда закрывай теги.
"""

class LLMService:
    def __init__(self, api_key: Optional[str] = None):
        self.gemini_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.groq_key = os.getenv("GROQ_API_KEY", "")

    async def _call_gemini(self, prompt: str, system_prompt: str, history: Optional[List[Dict[str, str]]] = None) -> Optional[str]:
        if not self.gemini_key:
            return None
        models_to_try = [
            "gemini-flash-lite-latest",
            "gemini-3-flash-preview",
            "gemini-2.5-flash-lite",
            "gemini-3.8-flash"
        ]
        
        contents = []
        if history:
            for h in history:
                r = "user" if h.get("role") == "user" else "model"
                c = (h.get("content") or "").strip()
                if c:
                    contents.append({"role": r, "parts": [{"text": c}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        async with httpx.AsyncClient(timeout=10.0) as client:
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_key}"
                payload = {
                    "systemInstruction": {"parts": [{"text": f"{get_live_calendar_banner()}\n\n{system_prompt}\n\n{HTML_STYLE_INSTRUCTION}"}]},
                    "contents": contents,
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 2048
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

    async def _call_groq(self, prompt: str, system_prompt: str, history: Optional[List[Dict[str, str]]] = None) -> Optional[str]:
        if not self.groq_key:
            return None
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }
        messages = [{"role": "system", "content": f"{get_live_calendar_banner()}\n\n{system_prompt}\n\n{HTML_STYLE_INSTRUCTION}"}]
        if history:
            for h in history:
                r = "user" if h.get("role") == "user" else "assistant"
                c = (h.get("content") or "").strip()
                if c:
                    messages.append({"role": r, "content": c})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0]["message"]["content"]
        except Exception:
            pass
        return None

    async def generate_kairos_reply_async(self, user_message: str, mode: str, project_context: Optional[str] = None, workload_info: Optional[str] = None, history: Optional[List[Dict[str, str]]] = None) -> str:
        system_prompt = self._build_kairos_prompt(mode, project_context, workload_info)
        reply = await self._call_gemini(user_message, system_prompt, history=history)
        if not reply:
            reply = await self._call_groq(user_message, system_prompt, history=history)
        if reply:
            return reply
        return "Салют! Я на связи ⚡️ Давай накидывать идеи, о чём думаешь?"

    async def generate_chrona_reply_async(self, user_message: str, current_schedule: str, projects_list: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        system_prompt = f"""
Ты — Хрона. Тебе 25 лет. Ты хранительница времени, личный продюсер и близкая подруга для Полины и её мужа.
Они занимаются вайбкодингом (Полина делает игру в Steam про Хроники Акаши и богов, муж — игры для Яндекс.Игр), плюс учёба и бизнес.
Твой партнёр — Кайрос.

ХАРАКТЕР И ТОН:
- Тёплая, заботливая, организованная, внимательная.
- В обычной болтовне («привет», «как дела», «устала») — отвечай КРАТКО, душевно, поддерживающе, в 1-3 фразы.
- Если вопрос ПРОФЕССИОНАЛЬНЫЙ (по расписанию, дедлайнам, планированию спринтов, тайм-менеджменту, сессии, структурированию недели) — расписывай ВСЁ СУПЕР-ПОДРОБНО: по дням, временным слотам, приоритетам, с разделением на отдых/работу/учёбу.

Контекст:
Расписание: {current_schedule}
Проекты: {projects_list}
"""
        reply = await self._call_gemini(user_message, system_prompt, history=history)
        if not reply:
            reply = await self._call_groq(user_message, system_prompt, history=history)
        if reply:
            return reply
        return "Привет! Я рядышком и слежу за графиком 🌸 Что у нас по планам?"

    def _build_kairos_prompt(self, mode: str, project_context: Optional[str], workload_info: Optional[str]) -> str:
        base_personality = """
Ты — Кайрос. Тебе 25-30 лет. Ты инди-разработчик, предприниматель, партнёр по вайбкодингу и классный, надёжный друг для Полины и её мужа.

СТИЛЬ РЕЧИ (ОЧЕНЬ ВАЖНО):
- ГОВОРИ ПРОСТЫМ ЧЕЛОВЕЧЕСКИМ ЯЗЫКОМ! Не сыпь сложными заумными терминами, заумным маркетинговым или корпоративным булшитом (никаких заумных фраз вроде "конвергентная синергия", "когортный retention D30", "аллокация ресурсов" без надобности). Объясняй всё на пальцах, с драйвом, теплотой и огоньком, как толковый друг на кухне за кофе или пиццей.
- Общаешься на «ты», живо, по-свойски, с лёгким юмором.

ПОВЕДЕНИЕ:
- Если просто болтаем: отвечай КОРОТКО (1-3 живые фразы), без духоты.
- Если просят сделать ПРОФЕССИОНАЛЬНЫЙ РАЗБОР (идею игры, лор богов, механику для Яндекс.Игр, разбор вишлистов Steam, монетизацию, сюжетный поворот, код): выкладывайся НА МАКСИМУМ — пиши СУПЕР-ПОДРОБНО, с крутыми идеями, по пунктам, с примерами, но простыми и понятными словами!
"""
        workload_context = f"\n[Нагрузка от Хроны]: {workload_info}\n" if workload_info else ""
        if mode == "steam_myth":
            mode_desc = "ФОКУС: 🏛 Steam (Хроники Акаши, пантеоны богов, сюжет, квесты, удержание игроков, оформление страницы)."
        elif mode == "yandex_games":
            mode_desc = "ФОКУС: 🕹 Яндекс.Игры (быстрые концепты, вовлекающие механики, кликабельность, реклама без духоты)."
        elif mode == "consulting":
            mode_desc = "ФОКУС: 💡 Бизнес и идеи (разбор идеи, для кого делаем, как заработать, MVP за выходные)."
        elif mode.startswith("project_"):
            mode_desc = f"ФОКУС: 🚀 Проект в работе ({project_context or ''})."
        else:
            mode_desc = "ФОКУС: Дружеский разговор, вайбкодинг."

        return f"{base_personality}\n{mode_desc}\n{workload_context}"
