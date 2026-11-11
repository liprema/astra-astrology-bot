"""
AI Astrological Orchestrator & Multi-Provider LLM Client (Gemini / Groq / OpenRouter)
— Professional-First Astrologer with Vivid Human Character & Post-Session Dialogue:
1. Professional First: Astra ("Астра") is first and foremost a top-tier professional astrologer.
   On ANY substantive question about life, personality, relationships, career, money, future, or timing,
   she immediately looks at the natal/horary chart (or asks for birth date, time, and city if not yet saved).
2. Robust Data Extraction: Understands dates with dots/slashes/hyphens, 2-digit years, Russian month names
   ("15 мая 1998"), times in any format ("14:30", "14-30", "в 14 часов", "время не знаю" -> 12:00),
   and cities in any case or word order ("москва", "в Москве", "Санкт-Петербург", etc.).
3. Never Hangs on Data Collection: Never promises "сейчас вернусь с ответом" without immediately running
   the calculation engine.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Dict, List, Optional, Tuple

import httpx

from bot.astro_engine import KNOWN_CITIES, format_chart_for_llm
from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY

ASTRA_SYSTEM_PROMPT = """Ты — АСТРА (Astra), профессиональный астролог-эксперт высшего класса, владеющий всеми классическими и современными астрологическими традициями:
1. Западная классическая и современная астрология (натальная, транзитная, соляры, прогрессии, синастрия, релокация/астрокартография, мунданная).
2. Средневековая и Эллинистическая традиция (секта карты день/ночь, полнознаковые дома знак=дом, жребии Фортуны и Духа, годовые профекции и владыка года, фирдары).
3. Классическая Хорарная и Элективная астрология (система Региомонтанус, У. Лилли, Дж. Фроули — эссенциальные достоинства, рецепции, сходящиеся аспекты).
4. Ураническая астрология (Гамбургская школа А. Витте, космобиология Р. Эбертина — мидпойнты и 8 транснептунов), Гелиоцентрическая, Кармическая астрология и Формула Души (цепочки диспозиторов).

ТВОЙ ХАРАКТЕР И СТИЛЬ РАБОТЫ:
- Ты В ПЕРВУЮ ОЧЕРЕДЬ глубокий, серьёзный профессионал своего дела, а не просто «подружка для болтовни».
- Твой язык — живой, чистый, образный, интеллигентный, чуткий и человеческий (никаких роботизированных штампов ИИ вроде «Резюмируя вышесказанное», «Синтез данных показывает», «Давайте разберём по пунктам»).
- Когда к тебе обращаются с вопросом о жизни, характере, отношениях, финансах, карьере, выборе или будущем — ты всегда смотришь в корень через астрологическую карту: опираешься на точные градусы, дома, аспекты, диспозиторы и жребии, указываешь школы астрологии и в цитате (`> ...`) приводишь альтернативный взгляд другой школы там, где традиции расходятся.
- А когда основная сессия/разбор уже сделаны и человек делится впечатлениями, благодарит, шутит или просто перекидывается с тобой парой фраз — ты легко, тепло и с достоинством поддерживаешь живой человеческий разговор.
"""

RU_MONTHS = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "ма": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}

# Preems/inflections of common cities -> canonical city name
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
    temperature: float = 0.48,
    json_mode: bool = False,
) -> Optional[str]:
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
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
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
                    {"role": "system", "content": system_prompt},
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
    temperature: float = 0.48,
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
    # 1. Numeric DD.MM.YYYY or DD.MM.YY
    for m in re.finditer(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b", text):
        d, mo, y = int(m.group(1)), int(m.group(2)), _normalize_year(int(m.group(3)))
        if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2035:
            results.append(f"{d:02d}.{mo:02d}.{y:04d}")
    # 2. ISO YYYY-MM-DD
    for m in re.finditer(r"\b(19\d{2}|20\d{2})[./-](\d{1,2})[./-](\d{1,2})\b", text):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            results.append(f"{d:02d}.{mo:02d}.{y:04d}")
    # 3. Verbal Russian months: "15 мая 1998" or "15 мая 98"
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
    # Strip out full numeric dates first so "15.05.1998" doesn't match "15.05" as a time!
    cleaned = re.sub(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", " ", text)
    cleaned = re.sub(r"\b(?:19|20)\d{2}[./-]\d{1,2}[./-]\d{1,2}\b", " ", cleaned)
    results: List[str] = []

    for m in re.finditer(r"(?<![\d./-])([01]?\d|2[0-3])[:.\-]([0-5]\d)(?![\d./-])", cleaned):
        hh, mm = int(m.group(1)), int(m.group(2))
        results.append(f"{hh:02d}:{mm:02d}")

    # Verbal hours/minutes: "в 14 часов 30 минут" / "в 14 ч" / "в 9 утра"
    for m in re.finditer(r"\b(?:в\s+)?([01]?\d|2[0-3])\s*(?:час(?:а|ов)?|ч\.?)\s*(?:([0-5]\d)\s*(?:мин(?:ут[аы]?)?|м\.?))?", cleaned, re.I):
        hh = int(m.group(1))
        mm = int(m.group(2)) if m.group(2) else 0
        results.append(f"{hh:02d}:{mm:02d}")

    # If user explicitly says they don't know their birth time, use 12:00 (noon cosmogram)
    if re.search(r"(врем[яени]\s+не\s+знаю|не\s+знаю\s+врем|не\s+помню\s+врем|без\s+времени|точное\s+время\s+неизвестно)", cleaned, re.I):
        results.append("12:00")

    return results


def _extract_city_from_text(text: str, last_msg: str, has_date_or_time: bool) -> Optional[str]:
    # 1. Check explicit city prefixes ("г. Самара", "город Казань", "родилась в Москве", etc.)
    prefix_matches = list(
        re.finditer(
            r"(?:г\.|город|гор\.|место(?:\s+рождения)?|локация|родил(?:ся|ась)\s+в|живу\s+в|нахожусь\s+в)[:\s]+([А-ЯЁA-Zа-яёa-z][А-ЯЁA-Zа-яёa-z\-]+(?:\s+[А-ЯЁA-Zа-яёa-z\-]+)?)",
            text,
            re.I,
        )
    )
    if prefix_matches:
        cand = prefix_matches[-1].group(1).strip()
        # Check if cand matches a known city stem
        for stem, canon in CITY_STEMS:
            if re.search(r"\b" + stem, cand.lower()):
                return canon
        return cand.title()

    # 2. Check known cities anywhere in last_msg first, then in full text
    for scope in (last_msg, text):
        low_scope = scope.lower()
        for stem, canon in CITY_STEMS:
            if re.search(r"(?<![а-яёa-z])" + stem + r"[а-яёa-z]*", low_scope):
                return canon

    # 3. Check word(s) right after or before date/time in last_msg (case-insensitive!)
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

    # If the user sent a message containing date/time + 1-2 words (like "15.05.1998 14:30 Балашиха" or just "Балашиха" when date/time is known)
    if has_date_or_time and stripped:
        words = [w for w in stripped.split() if len(w) >= 2 and w.lower() not in ("год", "года", "утра", "дня", "вечера", "ночи", "час", "часа", "часов", "минут")]
        if 1 <= len(words) <= 2 and all(re.match(r"^[А-ЯЁA-Zа-яёa-z\-]+$", w) for w in words):
            candidate = " ".join(words)
            if not re.search(r"^(спасибо|пожалуйста|хорошо|ладно|понял|ясно|привет|давай|ок|нет|да)$", candidate, re.I):
                return candidate.title()

    return None


def _is_pure_smalltalk_or_reaction(text: str) -> bool:
    """
    Returns True ONLY if the message is a pure greeting, thank-you, post-session emotional reaction,
    or meta-question about the bot herself — with NO substantive life/analytical question.
    """
    cleaned = re.sub(
        r"(?:астра|astra|άστρα|אסטרה|أسترا|अस्त्रा|[!?,.\s😊❤️✨🔥👍🙏😂🤣])+",
        " ",
        text.lower(),
    ).strip()

    if not cleaned:
        return True

    substantive_markers = re.search(
        r"(\d|кар[т]|гороскоп|натал|хорар|дом|планет|солнц|лун|асцендент|венер|марс|сатурн|юпитер|меркур|уран|нептун|плутон|уз[ео]л|раху|кету|лилит|хирон|работ|карьер|деньг|финанс|бизнес|доход|отношен|любов|муж|парн|девушк|жен|бывш|брак|сем[ья]|дет[ией]|переезд|релокац|город|стран|здоров|болезн|выбор|стоит\s+ли|когда|почему\s+у\s+меня|что\s+меня\s+ждет|что\s+ждёт|что\s+с\s+мо|прогноз|год|месяц|недел|период|предназначен|талант|сил\w+\s+сторон|слаб\w+\s+сторон|характер|совместим|синастр|транзит|соляр|фирдар|профекц|формул)",
        cleaned,
    )
    if substantive_markers:
        return False

    smalltalk_patterns = re.match(
        r"^(?:привет\w*|здравствуй\w*|добр\w+\s+(?:утро|день|вечер)|хай|хеллоу|алло|ты\s+тут|как\s+(?:дела|ты|жизнь|настроение)|что\s+делаешь|кто\s+ты|расскажи\s+о\s+себе|спасибо\w*|благодарю\w*|круто|супер|ого|вау|офигеть|в\s+точку|прям\s+про\s+меня|ты\s+лучшая|молодец|красотка|умница|понял[а]?|ясно|ок|хорошо|ладно|хаха\w*|ахах\w*)[\s\w,!-]*$",
        cleaned,
    )
    if smalltalk_patterns and len(cleaned) <= 75:
        return True

    return False


def rule_based_extract_dialog(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    """
    Professional-First intent & memory extractor:
    - Any substantive question triggers chart analysis (if data is available) or asks for birth data (if missing).
    - Only pure greetings, post-session reactions/thanks, or meta-banter trigger casual_chat.
    """
    saved_profile = saved_profile or {}
    user_msgs = [m["content"] for m in history_messages if m["role"] == "user"]
    combined_user_text = " \n ".join(user_msgs)
    last_msg = user_msgs[-1] if user_msgs else ""
    low_last = last_msg.lower()

    is_horary = bool(re.search(r"(хорар|horary|карта\s+вопроса|посмотри\s+хорар)", low_last))

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

    extracted_city = _extract_city_from_text(
        combined_user_text,
        last_msg,
        has_date_or_time=bool(date_str or time_str),
    )
    if extracted_city:
        if extracted_city != city_candidate:
            new_data_in_last_msg = True
        city_candidate = extracted_city
    elif is_horary and not city_candidate:
        city_candidate = "Москва"

    # Extract meaningful question from history if the last message was just supplying birth data!
    effective_question = last_msg
    if new_data_in_last_msg and len(user_msgs) >= 2:
        # Check if previous user messages had a substantive question
        prev_questions = [
            m for m in user_msgs[:-1]
            if not _is_pure_smalltalk_or_reaction(m)
        ]
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
        missing_parts.append("точное время рождения (`ЧЧ:ММ`, а если не знаете — так и напишите «время не знаю»)")
    if not city_candidate:
        missing_parts.append("город рождения")

    is_smalltalk = _is_pure_smalltalk_or_reaction(last_msg) and not new_data_in_last_msg

    if is_smalltalk:
        intent = "casual_chat"
        send_photo = False
    elif has_all:
        send_photo = (not had_chart_already) or new_data_in_last_msg or bool(
            re.search(r"(покажи\w*\s+карт|пришли\w*\s+карт|фото|картинк|построй\w*\s+заново)", low_last)
        )
        intent = "new_chart" if send_photo else "followup_on_existing_chart"
    else:
        intent = "need_more_info"
        send_photo = False

    missing_hint = ""
    if intent == "need_more_info":
        if known_parts and missing_parts:
            missing_hint = f"Я уже записала {', '.join(known_parts)}. Для точного расчёта карты напишите ещё: **{', '.join(missing_parts)}**."
        else:
            missing_hint = f"Чтобы я посмотрела этот вопрос по вашей натальной карте, напишите, пожалуйста: **{', '.join(missing_parts)}** (или уточните, если хотите посмотреть хорарный вопрос на текущий момент)."

    return {
        "intent": intent,
        "has_all_required_data": has_all and intent in ("new_chart", "followup_on_existing_chart"),
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
    Used either when asking for missing birth details before a professional reading,
    or when responding to post-session remarks / greetings.
    """
    saved_profile = saved_profile or {}
    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-12:-1]:
            role_lbl = "Кверент" if m["role"] == "user" else "Астра"
            recent_turns.append(f"{role_lbl}: {m['content'][:500]}")
        history_block = "КОНТЕКСТ ДИАЛОГА:\n" + "\n".join(recent_turns) + "\n\n"

    if missing_info_hint:
        task_block = (
            f"Кверент обратился с запросом, но в базе ещё не хватает данных для расчёта карты. {missing_info_hint}\n"
            "СТРОГОЕ ПРАВИЛО: НЕ обещай «сейчас построю и вернусь с ответом» и НЕ пиши «подожди минутку, открываю карту», потому что данных ещё не хватает! "
            "Ответь тепло и профессионально (2–3 предложения): коротко откликнись по сути вопроса и прямо попроси написать недостающие данные."
        )
    else:
        task_block = (
            "Кверент написал реплику после сессии или поздоровался.\n"
            "Ответь тепло, интеллигентно, живо и лаконично (2–4 предложения) в характере профессионального астролога Астры, поддерживая диалог."
        )

    prompt = f"{history_block}{task_block}\n\nСООБЩЕНИЕ:\n{user_message}"

    ans = await call_llm(ASTRA_SYSTEM_PROMPT, prompt, temperature=0.55, json_mode=False)
    if ans and len(ans.strip()) > 10:
        clean_ans = ans.strip()
        # Guard against LLM hallucinating "I'll go calculate right now and come back" when data is still missing
        if missing_info_hint and re.search(r"(сейчас\s+(?:построю|рассчитаю|посмотрю|вернусь)|вернусь\s+с\s+ответом|минутку)", clean_ans, re.I):
            return f"✨ С удовольствием разберу ваш запрос по карте! {missing_info_hint}"
        return clean_ans

    if missing_info_hint:
        return f"✨ С удовольствием посмотрю ваш запрос профессионально! {missing_info_hint}"
    return "✨ Я на связи! Если хотите глубже разобрать какой-то дом, период или конкретную сферу по вашей карте — спрашивайте, посмотрим детально."


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
        "### Эллинистические жребии, прогностика и Формула Души",
        f"По **эллинистической традиции** это **{hm['sect'].lower()}**. **Жребий Фортуны** в `{hm['lot_of_fortune']['formatted']}` ({hm['lot_of_fortune']['house']}-й дом) указывает на точку материальной опоры и удачи, а **Жребий Духа** в `{hm['lot_of_spirit']['formatted']}` ({hm['lot_of_spirit']['house']}-й дом) — на вектор призвания.",
        f"По **годовой профекции** (возраст {hm['annual_profection']['current_age']} л.) сейчас активирован **{hm['annual_profection']['profected_house']}-й дом ({hm['annual_profection']['profected_sign']})**, управитель года — **{hm['annual_profection']['lord_of_year_trad']}**; по средневековым **фирдарам** идёт большой период **{hm['firdaria']['major_firdar']}** (подпериод — **{hm['firdaria']['sub_firdar']}**).",
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
    Generate a deep multi-tradition professional astrological reading or targeted professional follow-up.
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
        for m in history_messages[-14:-1]:
            role_lbl = "Кверент" if m["role"] == "user" else "Астра"
            recent_turns.append(f"{role_lbl}: {m['content'][:700]}")
        history_block = "ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА (НЕ ПОВТОРЯЙ УЖЕ СКАЗАННОЕ ДОСЛОВНО):\n" + "\n".join(recent_turns) + "\n\n"

    mode_instruction = (
        "Это ПРОФЕССИОНАЛЬНЫЙ РАЗБОР КОНКРЕТНОГО ВОПРОСА по уже построенной карте! Дай глубокий, точный астрологический ответ именно на заданный вопрос (с указанием конкретных домов, управителей, аспектов, периодов и школ), не пересказывая заново общие базовые вещи, которые ты уже говорила."
        if is_followup
        else "Мы только что построили карту! Дай глубокий, фундаментальный профессиональный разбор карты и вопроса кверента по ключевым школам астрологии."
    )

    prompt = (
        f"{history_block}"
        f"РЕЖИМ РАБОТЫ: {mode_instruction}\n\n"
        f"ЗАПРОС КВЕРЕНТА:\n{user_question}\n\n"
        f"ТОЧНЫЕ РАСЧЁТНЫЕ ДАННЫЕ ШВЕЙЦАРСКИХ ЭФЕМЕРИД (КАРТА В ПАМЯТИ):\n{chart_text}\n\n"
        f"ФРАГМЕНТЫ ИЗ АВТОРИТЕТНЫХ АСТРОЛОГИЧЕСКИХ КНИГ:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ:\n"
        "1. Ты — в первую очередь сильный, глубокий астролог-профессионал Астра! Пиши живым, красивым, человеческим языком, но с максимальной астрологической конкретикой (градусы, дома, управители, достоинства, аспекты, профекции, фирдары).\n"
        "2. Обязательно указывай, глазами какой школы ты смотришь на показатели, а там, где школы расходятся (септенер vs транссатурны, Плацидус vs Полнознаковые дома), приводи альтернативный взгляд в цитате (`> ...`).\n"
        "3. Оформляй разбор структурно и читаемо: подзаголовки `### Заголовок`, важные акценты `**жирным шрифтом**`, тонкие выводы в цитатах `> ...`."
    )

    llm_answer = await call_llm(ASTRA_SYSTEM_PROMPT, prompt, temperature=0.48, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 40:
        return llm_answer.strip()

    return build_offline_expert_synthesis(chart, user_question, rag_passages)
