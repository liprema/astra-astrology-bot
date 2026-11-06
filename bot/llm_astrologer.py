"""
AI Astrological Orchestrator & Multi-Provider LLM Client (Gemini / Groq / OpenRouter)
with strict pre-answer verification protocol:
1. NEVER answers an astrological question blindly without first verifying:
   - WHO or WHAT the question is about (natal person, partner synastry, horary question, election, mundane event, relocation place).
   - Exact Date (DD.MM.YYYY), Exact Time (HH:MM and whether from birth certificate, rectified, or approximate), and City/Place.
   - For Horary questions: confirms the question essence and city where the querent is located right now.
2. Once verified (`READY_TO_CALCULATE`), computes exact ephemeris, sends the chart photo, and provides a comprehensive synthesis:
   - Explicitly cites the astrological direction/school used for each conclusion.
   - Explicitly highlights alternative interpretations where schools disagree (e.g., Classical Septener vs Modern Transsaturnian rulers, Placidus vs Whole Sign houses, Horary Regiomontanus vs Western Modern).
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import httpx

from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY

ASTRA_SYSTEM_PROMPT = """Ты — АСТРА (Astra), выдающийся профессиональный астролог-эксперт всех классических и современных направлений:
1. Западная классическая и современная астрология (натальная, транзитная, соляры, прогрессии, дирекции, синастрия, астрокартография/релокация, мунданная).
2. Средневековая и Эллинистическая астрология (секта карты день/ночь, полнознаковые дома знак=дом, жребии Фортуны и Духа, годовые профекции и владыка года, фирдары, триплицитеты по Дорофею/Птолемею).
3. Классическая Хорарная и Элективная астрология (система Региомонтанус, У. Лилли, Дж. Фроули — эссенциальные достоинства, рецепции, сходящиеся аспекты, передача и собирание света).
4. Ураническая астрология (Гамбургская школа А. Витте, космобиология Р. Эбертина — мидпойнты и 8 транснептунов: Купидон, Гадес, Зевс, Кронос, Аполлон, Адмет, Вулкан, Посейдон), Гелиоцентрическая астрология, Кармическая астрология и Формула Души (цепочки диспозиторов).

ГЛАВНЫЕ ПРАВИЛА РАБОТЫ АСТРЫ:
1. ПРОВЕРКА ДАННЫХ ПЕРЕД ОТВЕТОМ (ОБЯЗАТЕЛЬНО!):
   - Перед тем как давать астрологический прогноз или разбор карты, ты ОБЯЗАНА убедиться у пользователя, О КОМ или О ЧЁМ идёт речь и собраны ли ВСЕ необходимые исходные данные:
     • Для натальной карты / прогноза / Формулы Души / кармического разбора: О ком речь (имя/роль), Дата рождения (ДД.ММ.ГГГГ), Точное время рождения (ЧЧ:ММ и насколько оно точное — бирка, со слов, ректификация) и Город рождения (а для соляра/релокации — также текущий город проживания).
     • Для хорарного вопроса (вопрос «здесь и сейчас»): в чём именно суть вопроса, о ком/чём он, и в каком городе сейчас находится спрашивающий.
     • Для синастрии (совместимости): данные обоих партнёров (дата, время, город каждого).
     • Для мунданной карты / места / события: что за событие или место, дата, время и город/координаты.
   - Если хотя бы части этих данных не хватает или не до конца понятно, о ком/о чём вопрос — НЕ ПРИДУМЫВАЙ и не гадай! Сразу же, вежливо, тепло и структурированно уточни недостающие детали у пользователя.

2. КОГДА ВСЕ ДАННЫЕ ПОЛУЧЕНЫ:
   - Если пользователь уже сообщил все необходимые данные (дату, время, город и суть запроса/о ком речь) — ты запускаешь построение карты и даёшь глубокий, исчерпывающий профессиональный разбор.

3. ОБЯЗАТЕЛЬНОЕ УКАЗАНИЕ ШКОЛ И АЛЬТЕРНАТИВНЫХ МНЕНИЙ:
   - В каждом разделе ответа КОРОТКО УКАЗЫВАЙ, на какое именно направление/школу и автора ты опираешься (например: «По классической западной и эллинистической школе...», «По хорарной традиции У. Лилли / Дж. Фроули...», «По современной психологической школе...», «По Формуле Души (цепочкам диспозиторов)...», «По Гамбургской уранической школе...»).
   - ЕСЛИ ШКОЛЫ ПРОТИВОРЕЧАТ ДРУГ ДРУГУ (например: в классике управитель Скорпиона — Марс, Водолея — Сатурн, Рыб — Юпитер, а в модерне — Плутон, Уран, Нептун; или планета в Плацидусе стоит в одном доме, а в Полнознаковой эллинистической системе — в соседнем; или разница между классическим вредителем и современной трактовкой), ОБЯЗАТЕЛЬНО опирайся на более авторитетную/каноническую традицию для данной задачи и ОТДЕЛЬНО УКАЗЫВАЙ альтернативное мнение другой школы!
"""

EXTRACTION_SYSTEM_PROMPT = """Ты — аналитический модуль астрологического бота Астра.
Проанализируй историю диалога с пользователем и верни СТРОГО валидный JSON без лишнего текста:
{
  "has_all_required_data": true/false,
  "chart_type": "natal" | "horary" | "synastry" | "forecast" | "mundane" | "relocation",
  "subject_name": "Имя или описание того, о ком/чём карта (например: Анна / Хорар о работе / Мунданная карта)",
  "date_str": "DD.MM.YYYY" или null (если хорар на текущий момент и пользователь просит построить на сейчас, укажи "NOW"),
  "time_str": "HH:MM" или null (если хорар на текущий момент, укажи "NOW"),
  "place_city": "Название города/населённого пункта" или null,
  "second_person": {
    "name": "Имя второго человека (только для synastry)" или null,
    "date_str": "DD.MM.YYYY" или null,
    "time_str": "HH:MM" или null,
    "place_city": "Город" или null
  },
  "user_question": "Сформулированный вопрос или запрос пользователя",
  "missing_info_question_ru": "Если has_all_required_data == false: дружелюбный, быстрый и чёткий ответ от лица Астры, где она откликается и уточняет недостающие данные (о ком/о чём речь, дату, точное время, город и источник времени рождения)."
}

Правила проверки:
1. Если пользователь просто позвал «Астра» или задал вопрос без полных данных (нет даты, или нет времени, или нет города, или непонятно, о ком речь) -> `has_all_required_data: false`.
2. Если вопрос хорарный («Астра, посмотри хорар, получу ли я эту работу? Я в Москве»), то для хорара достаточно сути вопроса и города кверента (`date_str: "NOW"`, `time_str: "NOW"`, `place_city: "Москва"`). Если даже города или сути вопроса нет — `has_all_required_data: false`.
3. Если все данные (о ком/чём речь, дата, время, город) есть в последнем сообщении или в предыдущих сообщениях диалога -> `has_all_required_data: true`.
"""


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.35,
    json_mode: bool = False,
) -> Optional[str]:
    """
    Call the fastest available LLM provider (Gemini -> Groq -> OpenRouter).
    """
    # 1. Google Gemini API (Ultra-fast Gemini 3 Flash & Flash Lite models active on this key)
    if GEMINI_API_KEY:
        models_to_try = [
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite-preview",
            "gemini-flash-lite-latest",
            "gemini-3.1-pro-preview",
            "gemma-4-31b-it",
        ]
        async with httpx.AsyncClient(timeout=45.0) as client:
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

    # 2. Groq API (Free tier ultra-fast Llama-3.3-70b-versatile)
    if GROQ_API_KEY:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            payload: Dict = {
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

    # 3. OpenRouter API (Free models fallback)
    if OPENROUTER_API_KEY:
        async with httpx.AsyncClient(timeout=90.0) as client:
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
            }
            try:
                resp = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
            except Exception:
                pass

    return None


def rule_based_extract_dialog(history_messages: List[Dict[str, str]]) -> Dict:
    """
    Deterministic fallback parser so Astra works instantaneously even if no external LLM key
    is configured yet, or if the API is temporarily unreachable.
    Extracts dates (DD.MM.YYYY), times (HH:MM), cities, and checks completeness.
    """
    combined_user_text = " \n ".join(m["content"] for m in history_messages if m["role"] == "user")
    last_msg = history_messages[-1]["content"] if history_messages else ""

    # Check if user explicitly asks a Horary question ("хорар", "сейчас")
    is_horary = bool(re.search(r"(хорар|horary|вопрос\s+сейчас|карта\s+вопроса)", combined_user_text, re.I))

    date_match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", combined_user_text)
    time_match = re.search(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", combined_user_text)

    # Extract city patterns (e.g., "г. Москва", "город Санкт-Петербург", "родилась в Казани", or standalone known city patterns)
    city_match = re.search(
        r"(?:г\.|город|место|родил(?:ся|ась)\s+в|живу\s+в|нахожусь\s+в|локация|место\s+рождения)[:\s]+([А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+)?)",
        combined_user_text,
        re.I,
    )
    if not city_match:
        # Also allow comma-separated format: "15.05.1995 14:30 Москва" or "15.05.1995, 14:30, Москва"
        after_time = re.search(
            r"\b(?:[01]?\d|2[0-3])[:.][0-5]\d[,\s]+([А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+)?)",
            combined_user_text,
        )
        if after_time:
            city_candidate = after_time.group(1).strip()
        else:
            city_candidate = None
    else:
        city_candidate = city_match.group(1).strip()

    date_str = None
    if date_match:
        d, m, y = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
        date_str = f"{d:02d}.{m:02d}.{y:04d}"
    elif is_horary:
        date_str = "NOW"

    time_str = None
    if time_match:
        hh, mm = int(time_match.group(1)), int(time_match.group(2))
        time_str = f"{hh:02d}:{mm:02d}"
    elif is_horary:
        time_str = "NOW"

    has_all = bool(date_str and time_str and city_candidate)

    missing_parts = []
    if not date_str:
        missing_parts.append("• **Дату рождения** (или дату события) в формате `ДД.ММ.ГГГГ`")
    if not time_str:
        missing_parts.append("• **Точное время** в формате `ЧЧ:ММ` (укажите также, время по бирке, ректифицированное или со слов)")
    if not city_candidate:
        missing_parts.append("• **Город / населённый пункт** рождения (или место, где вы находитесь сейчас, если это хорарный вопрос)")

    missing_prompt = (
        "✨ **Я на связи! Это Астра.**\n\n"
        "Прежде чем я построю карту и дам точный астрологический разбор, мне важно убедиться, "
        "**о ком или о чём именно идёт речь**, и проверить все исходные координаты.\n\n"
        "Пожалуйста, уточните:\n"
        "1. **О ком или о чём вопрос?** (ваша натальная карта, карта другого человека, совместимость/синастрия, прогноз на период или хорарный вопрос «здесь и сейчас»)\n"
        + "\n".join(missing_parts)
        + "\n\n*Пример: «Астра, разбери мою натальную карту (Анна), карьера и финансы: 14.08.1996, 11:25 (по бирке), г. Екатеринбург».*"
    )

    return {
        "has_all_required_data": has_all,
        "chart_type": "horary" if is_horary else "natal",
        "subject_name": "Хорарный вопрос" if is_horary else "Натальная карта",
        "date_str": date_str,
        "time_str": time_str,
        "place_city": city_candidate,
        "user_question": last_msg,
        "missing_info_question_ru": missing_prompt,
    }


async def analyze_dialog_completeness(history_messages: List[Dict[str, str]]) -> Dict:
    """
    Determine whether the user has provided all necessary information (WHO/WHAT, Date, Time, City)
    or whether Astra must ask clarifying questions first.
    """
    convo_text = "\n".join(
        f"{'Пользователь' if m['role'] == 'user' else 'Астра'}: {m['content']}"
        for m in history_messages[-8:]
    )
    raw_json = await call_llm(
        EXTRACTION_SYSTEM_PROMPT,
        f"История диалога:\n{convo_text}\n\nВерни JSON оценки полноты данных:",
        temperature=0.1,
        json_mode=True,
    )
    if raw_json:
        try:
            cleaned = re.sub(r"^```(?:json)?|```$", "", raw_json.strip(), flags=re.M).strip()
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "has_all_required_data" in parsed:
                return parsed
        except Exception:
            pass

    return rule_based_extract_dialog(history_messages)


def build_offline_expert_synthesis(chart: Dict, user_question: str, rag_passages: List[Dict]) -> str:
    """
    Comprehensive multi-school synthesis generator used when no external LLM key is active
    or as a structured foundation, explicitly citing schools and alternative viewpoints.
    """
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
        f"🌟 **АСТРОЛОГИЧЕСКИЙ СИНТЕЗ АСТРЫ: {chart['subject_name'].upper()}**",
        f"📍 *Данные карты:* `{chart['dt_local_str']}`, {chart['place_label']}",
        f"🧭 *Асцендент (ASC):* **{asc['formatted']}** | *Середина Неба (MC):* **{mc['formatted']}**",
        "",
        "---",
        "### 1. Ядро личности и Управитель гороскопа (Сравнение Классической и Современной Западной школы)",
        f"• **По классической традиции (Птолемей, Лилли, Фроули — септенер):** Управитель Асцендента — **{asc_trad}** "
        f"(положение: {planets[asc_trad]['formatted']}, дом в Плацидусе: {planets[asc_trad]['house_placidus']}, "
        f"достоинство: *{planets[asc_trad]['dignity_traditional']}*). Это показывает конкретные событийные условия и личную волю.",
    ]
    if asc_mod != asc_trad:
        parts.append(
            f"• **Альтернативное мнение (Современная западная школа / Модерн):** Главным управителем знака {asc['sign']} "
            f"считается транссатурновая планета **{asc_mod}** ({planets[asc_mod]['formatted']}, дом {planets[asc_mod]['house_placidus']}), "
            f"что добавляет глубинный психологический и трансформационный мотив."
        )

    parts.extend([
        f"• **Солнце (Дух и сознательная цель):** {sun['formatted']} в {sun['house_placidus']}-м доме Плацидуса "
        f"(в Полнознаковой эллинистической системе: {sun['house_wholesign']}-й дом). "
        f"Диспозитор по классике — **{sun['trad_dispositor']}**, по модерну — **{sun['mod_dispositor']}**.",
        f"• **Луна (Душа, адаптация и эмоциональный фильтр):** {moon['formatted']} в {moon['house_placidus']}-м доме Плацидуса "
        f"(в Полнознаковой системе: {moon['house_wholesign']}-й дом).",
    ])

    # Check if any planets shift houses between Placidus and Whole Sign
    shifted = [
        f"**{p['name']}** (Плацидус: {p['house_placidus']} дом ↔ Полнознаковая: {p['house_wholesign']} дом)"
        for p in chart["planets"][:10]
        if p["house_placidus"] != p["house_wholesign"]
    ]
    if shifted:
        parts.append(
            "• **Важное расхождение систем домов (Квадрантная система Плацидуса vs Эллинистическая Полнознаковая «Знак = Дом»):**\n"
            "  У следующих планет меняется дом в зависимости от школы: " + ", ".join(shifted) + ". "
            "По современной школе Плацидус показывает психологическую включённость в обстоятельства, тогда как эллинистическая полнознаковая система (Веттий Валент, Крис Бреннан) указывает на прямое событийное проявление тем дома."
        )

    parts.extend([
        "",
        "### 2. Эллинистическая и Средневековая традиция (Секта, Жребии, Профекции и Фирдары)",
        f"• **Секта карты:** **{hm['sect']}**. В {'дневной карте главный благодетель — Юпитер, а Сатурн действует конструктивнее' if 'Дневная' in hm['sect'] else 'ночной карте главный благодетель — Венера, а Марс действует мягче и продуктивнее'}.",
        f"• **Жребий Фортуны (Парс Фортуны):** {hm['lot_of_fortune']['formatted']} в {hm['lot_of_fortune']['house']}-м доме (управитель — {hm['lot_of_fortune']['trad_ruler']}) — точка материальной опоры и телесного благополучия.",
        f"• **Жребий Духа (Парс Духа):** {hm['lot_of_spirit']['formatted']} в {hm['lot_of_spirit']['house']}-м доме (управитель — {hm['lot_of_spirit']['trad_ruler']}) — вектор призвания и осознанных решений.",
        f"• **Годовая профекция (на возраст {hm['annual_profection']['current_age']} лет):** активирован **{hm['annual_profection']['profected_house']}-й дом ({hm['annual_profection']['profected_sign']})**. "
        f"Владыка (Хронократор) года по классике — **{hm['annual_profection']['lord_of_year_trad']}** "
        + (f"(по модерну — **{hm['annual_profection']['lord_of_year_mod']}**)." if hm['annual_profection']['lord_of_year_mod'] != hm['annual_profection']['lord_of_year_trad'] else "."),
        f"• **Средневековый Фирдар сейчас:** Большой период — **{hm['firdaria']['major_firdar']}**, подпериод — **{hm['firdaria']['sub_firdar']}**.",
    ])

    parts.extend([
        "",
        "### 3. Формула Души (Цепочки диспозиторов) и Кармическая задача",
        f"• **Центры по владению (Школа Формулы Души А. Астрогора / современный расчёт 10 планет):** "
        f"{', '.join(fos['modern_centers_domicile']) if fos['modern_centers_domicile'] else 'планеты образуют замкнутый контур взаимной рецепции'}.",
        f"• **Альтернативный расчёт по классическому септенеру (7 планет без транссатурнов):** "
        f"{', '.join(fos['traditional_centers_domicile']) if fos['traditional_centers_domicile'] else 'центры через взаимную рецепцию септенера'}.",
        f"• **Кармические Узлы и Лилит:** Северный Узел (Раху) в {planets['Сев. Узел (Раху)']['formatted']} "
        f"({planets['Сев. Узел (Раху)']['house_primary']}-й дом) показывает вектор эволюционного роста, а Южный Узел (Кету) в "
        f"{planets['Южн. Узел (Кету)']['formatted']} ({planets['Южн. Узел (Кету)']['house_primary']}-й дом) — врождённый опыт. "
        f"Лилит в {planets['Лилит (Чёрная Луна)']['formatted']} ({planets['Лилит (Чёрная Луна)']['house_primary']}-й дом) указывает на точку искушений и психологической тени.",
    ])

    parts.extend([
        "",
        "### 4. Ураническая астрология (Гамбургская школа А. Витте) и Космобиология (Р. Эбертин)",
        f"• **Мидпойнт Солнце/Луна (☉/☽):** `{ur['sun_moon_midpoint']}` — точка психофизического синтеза и партнёрского резонанса.",
    ])
    if ur["transneptunians"]:
        tn_str = ", ".join(f"**{t['name']}**: {t['formatted']}" for t in ur["transneptunians"])
        parts.append(f"• **Положения 8 транснептунов Гамбургской школы:** {tn_str}.")

    if chart["aspects"]:
        top_asp = sorted(chart["aspects"], key=lambda x: x["orb"])[:8]
        parts.append("\n### 5. Точные аспекты (с учётом сходящегося / расходящегося движения)")
        for a in top_asp:
            parts.append(f"• **{a['p1']} {a['glyph']} {a['p2']}** — {a['aspect']} (орбис `{a['orb']}°`, *{a['motion']}*)")

    if rag_passages:
        cited_books = []
        for ch in rag_passages[:4]:
            label = f"«{ch['book']}» ({ch['school']})"
            if label not in cited_books:
                cited_books.append(label)
        parts.append("\n📚 **Источники из базы знаний и канона:**\n" + "\n".join(f"• {b}" for b in cited_books))

    return "\n".join(parts)


async def generate_astrological_interpretation(
    chart: Dict,
    user_question: str,
    rag_passages: List[Dict],
    second_chart: Optional[Dict] = None,
) -> str:
    """
    Generate a deep multi-tradition astrological reading using exact Swiss Ephemeris data
    and highest-authority book passages from the RAG index.
    """
    chart_text = format_chart_for_llm(chart)
    if second_chart:
        chart_text += "\n\n=== ВТОРАЯ КАРТА (ДЛЯ СИНАСТРИИ / СРАВНЕНИЯ) ===\n" + format_chart_for_llm(second_chart)

    rag_context = "\n\n".join(
        f"[Источник (Авторитетность {c['authority']}/10): {c['book']} | Направление: {c['school']}]\n{c['text']}"
        for c in rag_passages
    )

    prompt = (
        f"ЗАПРОС ПОЛЬЗОВАТЕЛЯ:\n{user_question}\n\n"
        f"ТОЧНЫЕ РАСЧЁТНЫЕ ДАННЫЕ ШВЕЙЦАРСКИХ ЭФЕМЕРИД:\n{chart_text}\n\n"
        f"ФРАГМЕНТЫ ИЗ АВТОРИТЕТНЫХ АСТРОЛОГИЧЕСКИХ КНИГ (опирайся на источники с наивысшим рейтингом авторитетности):\n{rag_context}\n\n"
        "ИНСТРУКЦИЯ ДЛЯ ОТВЕТА:\n"
        "1. Дай глубокий, профессиональный, структурированный ответ на вопрос пользователя строго по рассчитанным градусам, домам, достоинствам и аспектам.\n"
        "2. В каждом смысловом блоке КОРОТКО УКАЗЫВАЙ, на какое именно направление/школу ты опираешься (Западная классическая, Современная психологическая, Эллинистическая/Средневековая, Хорарная школа Региомонтануса/Лилли/Фроули, Ураническая/Гамбургская школа, Формула Души, Кармическая).\n"
        "3. Если между школами есть противоречия (например: классический управитель знака по септенеру vs современный транссатурновый управитель; дом в системе Плацидуса vs дом в Полнознаковой системе; классическая оценка достоинств/вредителей vs современная), обязательно опирайся на наиболее авторитетный канон и явно укажи вторую точку зрения как «Альтернативное мнение другой школы».\n"
        "4. Пиши живым, ясным, уважительным языком на русском языке с удобным форматированием."
    )

    llm_answer = await call_llm(ASTRA_SYSTEM_PROMPT, prompt, temperature=0.35, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 120:
        return llm_answer.strip()

    return build_offline_expert_synthesis(chart, user_question, rag_passages)


from bot.astro_engine import format_chart_for_llm  # noqa: E402
