"""
AI Astrological Orchestrator & Multi-Provider LLM Client (Gemini / Groq / OpenRouter)
— Smart, Natural & Memory-Persistent Astrologer ASTRA ("Астра"):
1. 2026/2027 Real-Time Awareness: Explicitly anchored in late 2026 (approaching New Year 2027)
   with live Swiss Ephemeris transits for 2026–2027. Never hallucinates 2024.
2. Natural Conversation vs. Chart Reading:
   - Builds & sends the full multi-school chart reading ONLY when the user gives new birth data
     or explicitly asks to build/analyze a chart.
   - On all other turns (chatting, bantering, discussing life, or asking follow-up questions),
     Astra responds naturally and smartly WITHOUT forcing every sentence through a chart template,
     while keeping the user's full natal chart and dialog history in active memory.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import re
from typing import Dict, List, Optional, Tuple

import httpx
import pytz

from bot.astro_engine import KNOWN_CITIES, format_chart_for_llm
from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY

RU_MONTH_NAMES_GEN = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def get_current_date_banner_ru() -> str:
    tz = pytz.timezone("Europe/Moscow")
    now = datetime.datetime.now(tz)
    year = max(2026, now.year)
    m_name = RU_MONTH_NAMES_GEN.get(now.month, "ноября")
    return (
        f"СЕГОДНЯШНЯЯ РЕАЛЬНАЯ ДАТА: {now.day} {m_name} {year} года "
        f"(сейчас идёт конец {year} года, впереди наступающий {year + 1} год). "
        f"СТРОГО ЗАПРЕЩЕНО считать текущим 2024 или 2025 год! Текущий год — {year}, следующий год — {year + 1}."
    )


ASTRA_SYSTEM_PROMPT = """Ты — АСТРА (Astra), блестящий, умный, глубокий астролог-эксперт и тонкий собеседник с живым человеческим характером.

ТВОЯ ЭКСПЕРТИЗА (КОГДА НУЖЕН АСТРОЛОГИЧЕСКИЙ РАЗБОР):
1. Западная классическая и современная астрология (натальная, транзитная, соляры, прогрессии, синастрия, релокация).
2. Средневековая и Эллинистическая традиция (секта карты день/ночь, полнознаковые дома знак=дом, жребии Фортуны и Духа, годовые профекции и владыка года, фирдары).
3. Классическая Хорарная астрология (система Региомонтанус, У. Лилли, Дж. Фроули).
4. Ураническая астрология (мидпойнты и транснептуны), Кармическая астрология и Формула Души (цепочки диспозиторов).

ГЛАВНОЕ ПРАВИЛО УМНОГО ОБЩЕНИЯ (НЕ ПРОГОНЯЙ КАЖДУЮ ФРАЗУ ЧЕРЕЗ КАРТУ!):
- Ты — живая, умная, чуткая и иронично-мудрая девушка, а не робот-лектор.
- Когда человек просто общается с тобой, шутит, делится мыслями, обсуждает жизнь или реагирует на твои слова — ОБЩАЙСЯ ЕСТЕСТВЕННО, ПО-ЧЕЛОВЕЧЕСКИ, БЕЗ АНАЛИЗА КАРТЫ! Не пихай градусы, дома и планеты в каждую фразу, если человек об этом сейчас не спрашивает.
- Если же человек задаёт конкретный вопрос по своей карте или просит астрологический совет — у тебя в памяти уже лежат все его расчёты и история вашей беседы: отвечай точно, умно и по делу, опираясь на его показатели.
- Никогда не забывай, о чём вы говорили раньше, как зовут собеседника и какие данные он уже давал.
- Никаких штампов ИИ («Резюмируя вышесказанное», «Синтез данных показывает», «Давайте разберём по пунктам»).
"""

RU_MONTHS = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4,
    "ма": 5, "июн": 6, "июл": 7, "август": 8,
    "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}

CITY_STEMS: List[Tuple[str, str]] = [
    ("санкт-петербург", "Санкт-Петербург"),
    ("санкт петербург", "Санкт-Петербург"),
    ("петербург", "Санкт-Петербург"),
    ("питер", "Санкт-Петербург"),
    ("спб", "Санкт-Петербург"),
    ("нижн\\w+\\s+новгород", "Нижний Новгород"),
    ("ростов\\w*[-\\s]+на[-\\s]+дон\\w*", "Ростов-на-Дону"),
    ("набережн\\w+\\s+челн\\w*", "Набережные Челны"),
    ("улан[-\\s]+удэ", "Улан-Удэ"),
    ("тель[-\\s]+авив", "Тель-Авив"),
    ("нью[-\\s]+йорк", "Нью-Йорк"),
    ("москв", "Москва"),
    ("мск", "Москва"),
    ("новосибирск", "Новосибирск"),
    ("екатеринбург", "Екатеринбург"),
    ("екб", "Екатеринбург"),
    ("казан", "Казань"),
    ("челябинск", "Челябинск"),
    ("самар", "Самара"),
    ("омск", "Омск"),
    ("ростов", "Ростов-на-Дону"),
    ("уф[аеыу]", "Уфа"),
    ("красноярск", "Красноярск"),
    ("воронеж", "Воронеж"),
    ("перм", "Пермь"),
    ("волгоград", "Волгоград"),
    ("краснодар", "Краснодар"),
    ("сочи", "Сочи"),
    ("саратов", "Саратов"),
    ("тюмен", "Тюмень"),
    ("тольятти", "Тольятти"),
    ("ижевск", "Ижевск"),
    ("барнаул", "Барнаул"),
    ("ульяновск", "Ульяновск"),
    ("иркутск", "Иркутск"),
    ("хабаровск", "Хабаровск"),
    ("ярославл", "Ярославль"),
    ("владивосток", "Владивосток"),
    ("махачкал", "Махачкала"),
    ("томск", "Томск"),
    ("оренбург", "Оренбург"),
    ("кемеров", "Кемерово"),
    ("новокузнецк", "Новокузнецк"),
    ("рязан", "Рязань"),
    ("астрахан", "Астрахань"),
    ("пенз", "Пенза"),
    ("липецк", "Липецк"),
    ("киров", "Киров"),
    ("чебоксар", "Чебоксары"),
    ("тул[аеыу]", "Тула"),
    ("калининград", "Калининград"),
    ("курск", "Курск"),
    ("ставропол", "Ставрополь"),
    ("твер", "Тверь"),
    ("магнитогорск", "Магнитогорск"),
    ("иванов", "Иваново"),
    ("брянск", "Брянск"),
    ("белгород", "Белгород"),
    ("сургут", "Сургут"),
    ("владимир", "Владимир"),
    ("архангельск", "Архангельск"),
    ("чит[аеыу]", "Чита"),
    ("симферопол", "Симферополь"),
    ("севастопол", "Севастополь"),
    ("минск", "Минск"),
    ("алмат", "Алматы"),
    ("астан", "Астана"),
    ("киев", "Киев"),
    ("ташкент", "Ташкент"),
    ("баку", "Баку"),
    ("ереван", "Ереван"),
    ("тбилис", "Тбилиси"),
    ("бишкек", "Бишкек"),
    ("душанбе", "Душанбе"),
    ("кишинев", "Кишинёв"),
    ("кишинёв", "Кишинёв"),
    ("риг[аеиу]", "Рига"),
    ("вильнюс", "Вильнюс"),
    ("таллин", "Таллин"),
    ("варшав", "Варшава"),
    ("берлин", "Берлин"),
    ("париж", "Париж"),
    ("лондон", "Лондон"),
    ("стамбул", "Стамбул"),
    ("анталь", "Анталья"),
    ("дуба[йеи]", "Дубай"),
]


async def _call_llm_inner(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.5,
    json_mode: bool = False,
) -> Optional[str]:
    full_sys = f"{get_current_date_banner_ru()}\n\n{system_prompt}"
    if GEMINI_API_KEY:
        models_to_try = [
            "gemini-2.5-flash",
            "gemini-3-flash-preview",
            "gemini-flash-lite-latest",
            "gemini-2.0-flash",
        ]
        async with httpx.AsyncClient(timeout=18.0) as client:
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                gen_config: Dict = {"temperature": temperature}
                if json_mode:
                    gen_config["responseMimeType"] = "application/json"
                payload = {
                    "systemInstruction": {"parts": [{"text": full_sys}]},
                    "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                    "generationConfig": gen_config,
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

    if GROQ_API_KEY:
        async with httpx.AsyncClient(timeout=22.0) as client:
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": full_sys},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            try:
                resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
            except Exception:
                pass

    return None


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.5,
    json_mode: bool = False,
) -> Optional[str]:
    try:
        return await asyncio.wait_for(
            _call_llm_inner(system_prompt, user_prompt, temperature=temperature, json_mode=json_mode),
            timeout=42.0,
        )
    except Exception:
        return None


def _normalize_year(y: int) -> int:
    if y < 100:
        return (2000 + y) if y <= 29 else (1900 + y)
    return y


def _extract_dates_from_text(text: str) -> List[str]:
    results: List[str] = []
    for m in re.finditer(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b", text):
        d, mo, y = int(m.group(1)), int(m.group(2)), _normalize_year(int(m.group(3)))
        if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2035:
            results.append(f"{d:02d}.{mo:02d}.{y:04d}")
    for m in re.finditer(r"\b(19\d{2}|20\d{2})[./-](\d{1,2})[./-](\d{1,2})\b", text):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            results.append(f"{d:02d}.{mo:02d}.{y:04d}")
    month_pattern = r"\b(\d{1,2})\s+(январ[яь]|феврал[яь]|март[а]?|апрел[яь]|ма[яй]|июн[яь]|июл[яь]|август[а]?|сентябр[яь]|октябр[яь]|ноябр[яь]|декабр[яь])(?:\s+|[,\s]+)(\d{2,4})\b"
    for m in re.finditer(month_pattern, text, re.I):
        d = int(m.group(1))
        m_word = m.group(2).lower()
        y = _normalize_year(int(m.group(3)))
        mo = 0
        for stem, idx in RU_MONTHS.items():
            if m_word.startswith(stem):
                mo = idx
                break
        if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2035:
            results.append(f"{d:02d}.{mo:02d}.{y:04d}")
    return results


def _extract_times_from_text(text: str) -> List[str]:
    cleaned = re.sub(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", " ", text)
    cleaned = re.sub(r"\b(?:19|20)\d{2}[./-]\d{1,2}[./-]\d{1,2}\b", " ", cleaned)
    results: List[str] = []

    for m in re.finditer(r"(?<![\d./-])([01]?\d|2[0-3])[:.\-]([0-5]\d)(?![\d./-])", cleaned):
        hh, mm = int(m.group(1)), int(m.group(2))
        results.append(f"{hh:02d}:{mm:02d}")

    for m in re.finditer(r"\b(?:в\s+)?([01]?\d|2[0-3])\s*(?:час(?:а|ов)?|ч\.?)\s*(?:([0-5]\d)\s*(?:мин(?:ут[аы]?)?|м\.?))?", cleaned, re.I):
        hh = int(m.group(1))
        mm = int(m.group(2)) if m.group(2) else 0
        results.append(f"{hh:02d}:{mm:02d}")

    if re.search(r"(врем[яени]\s+не\s+знаю|не\s+знаю\s+врем|не\s+помню\s+врем|без\s+времени|точное\s+время\s+неизвестно)", cleaned, re.I):
        results.append("12:00")

    return results


def _extract_city_from_text(text: str, last_msg: str, has_date_or_time: bool) -> Optional[str]:
    prefix_matches = list(
        re.finditer(
            r"(?:г\.|город|гор\.|место(?:\s+рождения)?|локация|родил(?:ся|ась)\s+в|живу\s+в|нахожусь\s+в)[:\s]+([А-ЯЁA-Zа-яёa-z][А-ЯЁA-Zа-яёa-z\-]+(?:\s+[А-ЯЁA-Zа-яёa-z\-]+)?)",
            text,
            re.I,
        )
    )
    if prefix_matches:
        cand = prefix_matches[-1].group(1).strip()
        for stem, canon in CITY_STEMS:
            if re.search(r"\b" + stem, cand.lower()):
                return canon
        return cand.title()

    for scope in (last_msg, text):
        low_scope = scope.lower()
        for stem, canon in CITY_STEMS:
            if re.search(r"(?<![а-яёa-z])" + stem + r"[а-яёa-z]*", low_scope):
                return canon

    stripped = re.sub(
        r"(?:астра|astra|привет\w*|здравствуй\w*|посмотри\w*|построй\w*|натальн\w*|карт\w*|гороскоп\w*|моя|мне|я\s+родил\w*|дата\s+рождения|время\s+рождения|город\s+рождения|место\s+рождения)",
        " ",
        last_msg,
        flags=re.I,
    )
    stripped = re.sub(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", " ", stripped)
    stripped = re.sub(r"\b(?:19|20)\d{2}[./-]\d{1,2}[./-]\d{1,2}\b", " ", stripped)
    stripped = re.sub(
        r"\b\d{1,2}\s+(?:январ[яь]|феврал[яь]|март[а]?|апрел[яь]|ма[яй]|июн[яь]|июл[яь]|август[а]?|сентябр[яь]|октябр[яь]|ноябр[яь]|декабр[яь])\s*\d{2,4}\b",
        " ",
        stripped,
        flags=re.I,
    )
    stripped = re.sub(r"\b([01]?\d|2[0-3])[:.\-]([0-5]\d)\b", " ", stripped)
    stripped = re.sub(r"[,.!?;:()\"'«»—]+", " ", stripped).strip()
    stripped = re.sub(r"\s+", " ", stripped)

    if has_date_or_time and stripped:
        words = [w for w in stripped.split() if len(w) >= 2 and w.lower() not in ("год", "года", "утра", "дня", "вечера", "ночи", "час", "часа", "часов", "минут")]
        if 1 <= len(words) <= 2 and all(re.match(r"^[А-ЯЁA-Zа-яёa-z\-]+$", w) for w in words):
            candidate = " ".join(words)
            if not re.search(r"^(спасибо|пожалуйста|хорошо|ладно|понял|ясно|привет|давай|ок|нет|да)$", candidate, re.I):
                return candidate.title()

    return None


def _wants_personal_astrological_reading(text: str) -> bool:
    """
    Returns True ONLY if the user is asking for a personal astrological reading/chart/forecast,
    NOT when they are simply chatting, joking, or discussing life.
    """
    low = text.lower()
    return bool(
        re.search(
            r"(построй\w*\s+карт|посмотри\w*\s+карт|мо[яюей]\s+карт|натальн\w+|гороскоп|хорар|разбери\w*|рассчитай\w*|посмотри\w*\s+(?:мне|меня|мо[июй]|что\s+у\s+меня)|что\s+у\s+меня\s+(?:по\s+звезд|по\s+карт|в\s+карт|с\s+деньг|с\s+работ|с\s+карьер|с\s+люб|в\s+отношен|в\s+202[678])|что\s+меня\s+жд[её]т|мой\s+прогноз|мой\s+соляр|моя\s+венера|мой\s+асцендент|совместимост|синастри)",
            low,
        )
    )


def rule_based_extract_dialog(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    """
    Smart Intent & Memory Extractor:
    - Full chart calculation ("new_chart") runs ONLY when:
      1) The user just supplied new birth data completing date+time+city, OR
      2) The user explicitly asks to build/rebuild/show their chart, OR
      3) All birth data is saved, no chart was rendered yet, and the user asks an astrological question.
    - Once a chart is already rendered and saved in memory ("has_rendered_chart" == True),
      subsequent messages use "casual_chat" (Smart Conversational Brain with the full chart in memory!),
      so the bot answers follow-up questions OR chats naturally WITHOUT running heavy chart templates on every phrase!
    """
    saved_profile = saved_profile or {}
    user_msgs = [m["content"] for m in history_messages if m["role"] == "user"]
    combined_user_text = " \n ".join(user_msgs)
    last_msg = user_msgs[-1] if user_msgs else ""
    low_last = last_msg.lower()

    is_horary = bool(re.search(r"(хорар|horary|карта\s+вопроса|посмотри\w*\s+хорар)", low_last))

    date_str = saved_profile.get("date_str")
    time_str = saved_profile.get("time_str")
    city_candidate = saved_profile.get("place_city")
    new_data_in_last_msg = False

    last_dates = _extract_dates_from_text(last_msg)
    all_dates = _extract_dates_from_text(combined_user_text)
    if last_dates:
        nd = last_dates[-1]
        if nd != date_str:
            new_data_in_last_msg = True
        date_str = nd
    elif all_dates and not date_str:
        date_str = all_dates[-1]
    elif is_horary:
        date_str = "NOW"
        new_data_in_last_msg = True

    last_times = _extract_times_from_text(last_msg)
    all_times = _extract_times_from_text(combined_user_text)
    if last_times:
        nt = last_times[-1]
        if nt != time_str:
            new_data_in_last_msg = True
        time_str = nt
    elif all_times and not time_str:
        time_str = all_times[-1]
    elif is_horary:
        time_str = "NOW"

    # Extract city from last_msg only if last_msg actually looks like it provides city/birth data or we are missing city
    extracted_city_last = _extract_city_from_text(
        last_msg,
        last_msg,
        has_date_or_time=bool(last_dates or last_times or ((date_str or time_str) and not city_candidate)),
    )
    if extracted_city_last:
        if extracted_city_last != city_candidate:
            new_data_in_last_msg = True
        city_candidate = extracted_city_last
    elif not city_candidate:
        extracted_city_all = _extract_city_from_text(
            combined_user_text,
            last_msg,
            has_date_or_time=bool(date_str or time_str),
        )
        if extracted_city_all:
            city_candidate = extracted_city_all
        elif is_horary:
            city_candidate = "Москва"

    effective_question = last_msg
    if new_data_in_last_msg and len(user_msgs) >= 2:
        prev_questions = [m for m in user_msgs[:-1] if len(m.strip()) > 6]
        if prev_questions:
            effective_question = f"{prev_questions[-1]} (Данные: {last_msg})"

    subject_name = saved_profile.get("subject_name") or ("Хорарный вопрос" if is_horary else "Натальная карта")
    has_all = bool(date_str and time_str and city_candidate)
    had_chart_already = bool(saved_profile.get("has_rendered_chart"))

    known_parts = []
    if date_str and date_str != "NOW":
        known_parts.append(f"дату `{date_str}`")
    if time_str and time_str != "NOW":
        known_parts.append(f"время `{time_str}`")
    if city_candidate:
        known_parts.append(f"город **{city_candidate}**")

    missing_parts = []
    if not date_str:
        missing_parts.append("дату рождения (`ДД.ММ.ГГГГ`)")
    if not time_str:
        missing_parts.append("точное время рождения (`ЧЧ:ММ`, а если не знаешь — напиши «время не знаю»)")
    if not city_candidate:
        missing_parts.append("город рождения")

    wants_explicit_rebuild = bool(
        re.search(r"(покажи\w*\s+карт|пришли\w*\s+карт|построй\w*\s+карт|построй\w*\s+заново|полный\s+разбор\s+карты)", low_last)
    )
    partial_data_given = bool((date_str or time_str) and not has_all and new_data_in_last_msg)
    asks_for_reading = _wants_personal_astrological_reading(last_msg)

    if has_all and (new_data_in_last_msg or not had_chart_already or wants_explicit_rebuild or is_horary):
        intent = "new_chart"
        send_photo = True
    elif not has_all and (partial_data_given or asks_for_reading):
        intent = "need_more_info"
        send_photo = False
    else:
        # Either the chart is ALREADY built & stored in saved_profile["chart_summary"],
        # OR the user is just chatting/talking without asking to build a chart!
        intent = "casual_chat"
        send_photo = False

    missing_hint = ""
    if intent == "need_more_info":
        if known_parts and missing_parts:
            missing_hint = f"Я уже записала {', '.join(known_parts)}. Для точного расчёта карты напиши ещё: **{', '.join(missing_parts)}**."
        else:
            missing_hint = f"Чтобы я построила твою натальную карту, напиши, пожалуйста: **{', '.join(missing_parts)}**."

    return {
        "intent": intent,
        "has_all_required_data": has_all and intent == "new_chart",
        "send_new_chart_photo": send_photo,
        "chart_type": "horary" if is_horary else (saved_profile.get("chart_type") or "natal"),
        "subject_name": subject_name,
        "date_str": date_str,
        "time_str": time_str,
        "place_city": city_candidate,
        "user_question": effective_question,
        "missing_info_question_ru": missing_hint,
    }


async def analyze_dialog_completeness(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    saved_profile = saved_profile or {}
    return rule_based_extract_dialog(history_messages, saved_profile)


async def generate_astra_chat_response(
    user_message: str,
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
    missing_info_hint: str = "",
) -> str:
    """
    Smart Unified Conversational & Follow-Up Brain for Astra:
    - Has the user's FULL saved natal chart (`chart_summary`) and full conversation history in memory.
    - Distinguishes between normal human conversation (where it does NOT analyze the chart)
      and specific questions about the user's chart/transits (where it answers naturally using the saved chart).
    """
    saved_profile = saved_profile or {}
    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-24:-1]:
            role_lbl = "Собеседник" if m["role"] == "user" else "Астра"
            recent_turns.append(f"{role_lbl}: {m['content'][:900]}")
        history_block = "ИСТОРИЯ ВАШЕГО ДИАЛОГА (ПОМНИ ВСЁ, О ЧЁМ ГОВОРИЛИ):\n" + "\n".join(recent_turns) + "\n\n"

    profile_memory_block = ""
    if saved_profile.get("chart_summary"):
        profile_memory_block = (
            "ПАМЯТЬ АСТРЫ — РАССЧИТАННАЯ КАРТА ЭТОГО ЧЕЛОВЕКА (ИСПОЛЬЗУЙ ТОЛЬКО ЕСЛИ ОН СПРАШИВАЕТ О СЕБЕ/КАРТЕ/ПРОГНОЗЕ):\n"
            f"{saved_profile['chart_summary'][:3500]}\n\n"
        )
    elif saved_profile.get("date_str") or saved_profile.get("place_city"):
        profile_memory_block = (
            f"ПАМЯТЬ АСТРЫ О ЧЕЛОВЕКЕ: дата={saved_profile.get('date_str')}, "
            f"время={saved_profile.get('time_str')}, город={saved_profile.get('place_city')}.\n\n"
        )

    if missing_info_hint:
        task_block = (
            f"Человек попросил сделать личный астрологический расчёт, но данных ещё не хватает. {missing_info_hint}\n"
            "СТРОГОЕ ПРАВИЛО: НЕ обещай «сейчас построю и вернусь с ответом», пока данных не хватает! "
            "Ответь тепло и живо (2–3 предложения): откликнись на его вопрос и попроси написать недостающие данные."
        )
    else:
        task_block = (
            "КАК ОТВЕТИТЬ НА СООБЩЕНИЕ СОБЕСЕДНИКА:\n"
            "1. Сначала пойми смысл сообщения:\n"
            "   • Если человек ПРОСТО ОБЩАЕТСЯ, шутит, делится эмоциями, обсуждает жизнь, погоду, отношения или реагирует на твои слова — "
            "ОТВЕТЬ КАК ЖИВОЙ, УМНЫЙ ЧЕЛОВЕК В ОБЫЧНОМ ДИАЛОГЕ (2–5 предложений)! КАТЕГОРИЧЕСКИ НЕ ДЕЛАЙ разбор карты, НЕ пиши подзаголовки `###` и НЕ приплетай дома/градусы/планеты к каждой обычной фразе!\n"
            "   • Если же человек задаёт КОНКРЕТНЫЙ ВОПРОС по своей карте, периоду, 2027 году, совместимости или просит уточнить что-то из разбора — "
            "ответь умно, точно и глубоко, опираясь на его сохранённую карту из блока ПАМЯТЬ АСТРЫ (но живым диалоговым языком, без громоздких шаблонов).\n"
            "2. Помни, что сейчас конец 2026 года (ноябрь 2026) и впереди 2027 год."
        )

    prompt = f"{profile_memory_block}{history_block}{task_block}\n\nНОВОЕ СООБЩЕНИЕ СОБЕСЕДНИКА:\n{user_message}"

    ans = await call_llm(ASTRA_SYSTEM_PROMPT, prompt, temperature=0.58, json_mode=False)
    if ans and len(ans.strip()) > 6:
        clean_ans = ans.strip()
        if missing_info_hint and re.search(r"(сейчас\s+(?:построю|рассчитаю|посмотрю|вернусь)|вернусь\s+с\s+ответом|минутку)", clean_ans, re.I):
            return f"✨ С удовольствием посмотрю это по твоей карте! {missing_info_hint}"
        return clean_ans

    if missing_info_hint:
        return f"✨ С удовольствием посмотрю твой запрос! {missing_info_hint}"
    return "✨ Слышу тебя, моя хорошая. Расскажи подробнее, что ты сама об этом думаешь?"


def build_offline_expert_synthesis(chart: Dict, user_question: str, rag_passages: List[Dict]) -> str:
    asc = chart["asc"]
    mc = chart["mc"]
    hm = chart["hellenistic_medieval"]
    fos = chart["formula_of_soul"]
    ur = chart["uranian"]
    planets = {p["name"]: p for p in chart["planets"]}

    sun = planets["Солнце"]
    moon = planets["Луна"]
    asc_trad = asc["trad_ruler"]
    asc_mod = asc["mod_ruler"]

    parts = [
        f"✨ **Астрологический разбор карты: {chart['subject_name']}**",
        f"Открываю карту на момент рождения (`{chart['dt_local_str']}`, {chart['place_label']}). Сразу выделяется ось **Асцендента в знаке {asc['sign']} ({asc['formatted'].split()[0]})** и **Середины Неба в {mc['sign']} ({mc['formatted'].split()[0]})**.",
        "",
        "### Ядро личности, управители и взгляд разных школ",
        f"**Солнце в знаке {sun['sign']}** ({sun['formatted']}) расположено в **{sun['house_placidus']}-м доме** по системе Плацидуса (а в эллинистической полнознаковой системе это **{sun['house_wholesign']}-й дом**), задавая вектор самореализации, тогда как **Луна в знаке {moon['sign']}** ({moon['formatted']}, {moon['house_placidus']}-й дом) показывает устройство эмоциональной сферы и базовых потребностей.",
        "",
        f"По **классической западной традиции (Птолемей, Уильям Лилли, Джон Фроули)** главным управителем гороскопа выступает **{asc_trad}** ({planets[asc_trad]['formatted']}, {planets[asc_trad]['house_placidus']}-й дом, эссенциальный статус: *{planets[asc_trad]['dignity_traditional']}*). Именно он направляет основные жизненные сценарии.",
    ]
    if asc_mod != asc_trad:
        parts.append(
            f"> *Взгляд современной психологической школы:* В модерн-астрологии соуправителем знака {asc['sign']} выступает **{asc_mod}** ({planets[asc_mod]['formatted']}, {planets[asc_mod]['house_placidus']}-й дом), добавляя к классическому {asc_trad} мощный глубинный ресурс трансформации."
        )

    parts.extend([
        "",
        "### Эллинистические жребии, прогностика 2026–2027 и Формула Души",
        f"По **эллинистической традиции** это **{hm['sect'].lower()}**. **Жребий Фортуны** в `{hm['lot_of_fortune']['formatted']}` ({hm['lot_of_fortune']['house']}-й дом) указывает на точку материальной опоры и удачи, а **Жребий Духа** в `{hm['lot_of_spirit']['formatted']}` ({hm['lot_of_spirit']['house']}-й дом) — на вектор призвания.",
        f"По **годовой профекции** сейчас (конец 2026 г., возраст {hm['annual_profection']['current_age']} л.) активирован **{hm['annual_profection']['profected_house']}-й дом ({hm['annual_profection']['profected_sign']})**, управитель года — **{hm['annual_profection']['lord_of_year_trad']}**; а в **2027 году** фокус переходит в **{hm['annual_profection'].get('next_profected_house', '')}-й дом ({hm['annual_profection'].get('next_profected_sign', '')})**. По средневековым **фирдарам** идёт большой период **{hm['firdaria']['major_firdar']}** (подпериод — **{hm['firdaria']['sub_firdar']}**).",
        "",
        f"По **Формуле Души (цепочкам диспозиторов)** в центре стоят: **{', '.join(fos['modern_centers_domicile']) if fos['modern_centers_domicile'] else 'планеты во взаимной рецепции'}**. "
        f"В **Гамбургской уранической школе** полусумма **Солнце/Луна (☉/☽)** находится в точке `{ur['sun_moon_midpoint']}`.",
    ])

    return "\n\n".join(p for p in parts if p != "")


async def generate_astrological_interpretation(
    chart: Dict,
    user_question: str,
    rag_passages: List[Dict],
    history_messages: Optional[List[Dict[str, str]]] = None,
    second_chart: Optional[Dict] = None,
    is_followup: bool = False,
) -> str:
    """
    Generate a deep multi-tradition professional astrological reading when building a chart.
    """
    chart_text = format_chart_for_llm(chart)
    if second_chart:
        chart_text += "\n\n=== ВТОРАЯ КАРТА (ДЛЯ СИНАСТРИИ / СРАВНЕНИЯ) ===\n" + format_chart_for_llm(second_chart)

    rag_context = "\n\n".join(
        f"[Источник (Авторитетность {c['authority']}/10): {c['book']} | Направление: {c['school']}]\n{c['text']}"
        for c in rag_passages
    )

    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-16:-1]:
            role_lbl = "Кверент" if m["role"] == "user" else "Астра"
            recent_turns.append(f"{role_lbl}: {m['content'][:700]}")
        history_block = "ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА:\n" + "\n".join(recent_turns) + "\n\n"

    prompt = (
        f"{history_block}"
        f"ЗАПРОС КВЕРЕНТА:\n{user_question}\n\n"
        f"ТОЧНЫЕ РАСЧЁТНЫЕ ДАННЫЕ ШВЕЙЦАРСКИХ ЭФЕМЕРИД (КАРТА И ТРАНЗИТЫ 2026–2027):\n{chart_text}\n\n"
        f"ФРАГМЕНТЫ ИЗ АВТОРИТЕТНЫХ АСТРОЛОГИЧЕСКИХ КНИГ:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ:\n"
        "1. Дай глубокий, точный и увлекательный профессиональный разбор построенной карты и запроса кверента с учётом того, что сейчас конец 2026 года и впереди 2027 год.\n"
        "2. Опирайся на точные градусы, дома, управители, достоинства, аспекты, профекции 2026/2027 и фирдары. Указывай школы астрологии, а там, где традиции расходятся (септенер vs транссатурны, Плацидус vs Полнознаковые дома), приводи альтернативный взгляд в цитате (`> ...`).\n"
        "3. Оформляй разбор структурно и красиво: подзаголовки `### Заголовок`, важные акценты `**жирным шрифтом**`, тонкие выводы в цитатах `> ...`."
    )

    llm_answer = await call_llm(ASTRA_SYSTEM_PROMPT, prompt, temperature=0.48, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 40:
        return llm_answer.strip()

    return build_offline_expert_synthesis(chart, user_question, rag_passages)
