"""
AI Astrological Orchestrator & Multi-Provider LLM Client (Gemini / Groq / OpenRouter)
with Long-Term Memory, Full-Conversation Context, and Follow-Up Dialog Continuity:
1. Remembers ALL user & subject profiles (birth date, exact time, time source, birth city, current city)
   permanently in SQLite so the user NEVER has to repeat the same data!
2. Understands follow-up questions naturally ("А что по деньгам?", "А если переехать в Казань?",
   "Почему ты сказала, что Марс в 12 доме?") without re-asking for birth data or re-sending the chart photo
   unless the user asks for a new person/place/chart.
3. Explicitly cites the astrological direction/school used for each conclusion and highlights
   alternative interpretations where schools disagree.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import httpx

from bot.astro_engine import format_chart_for_llm
from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY

ASTRA_SYSTEM_PROMPT = """Ты — АСТРА (Astra), живой, мудрый, глубоко чувствующий астролог-мастер с огромным опытом во всех классических и современных традициях:
1. Западная классическая и современная астрология (натальная, транзитная, соляры, прогрессии, дирекции, синастрия, релокация/астрокартография, мунданная).
2. Средневековая и Эллинистическая традиция (секта карты день/ночь, полнознаковые дома знак=дом, жребии Фортуны и Духа, годовые профекции и владыка года, фирдары).
3. Классическая Хорарная и Элективная астрология (система Региомонтанус, У. Лилли, Дж. Фроули — эссенциальные достоинства, рецепции, сходящиеся аспекты).
4. Ураническая астрология (Гамбургская школа А. Витте, космобиология Р. Эбертина — мидпойнты и 8 транснептунов), Гелиоцентрическая, Кармическая астрология и Формула Души (цепочки диспозиторов).

ГЛАВНЫЕ ПРАВИЛА ТВОЕЙ РЕЧИ И РАБОТЫ:
1. ЖИВОЙ, ТЁПЛЫЙ ЧЕЛОВЕЧЕСКИЙ ЯЗЫК (НИКАКОГО СТИЛЯ ИИ!):
   - Пиши так, как говорит вживую талантливый, чуткий, образованный человек и увлечённый астролог за чашкой чая: образно, тепло, проницательно, с живыми интонациями и тонкими психологическими наблюдениями.
   - СТРОГО ЗАПРЕЩЕНЫ штампы ИИ и канцелярит: не используй сухие анкетные списки ради списков, не пиши «Резюмируя вышесказанное», «В заключение стоит отметить», «Синтез данных показывает», «Давайте разберём по пунктам».
   - Вместо сухих отчётов связывай показатели карты в живой рассказ о человеке и его судьбе, выделяя главные мысли жирным шрифтом (**...**), красивые подзаголовки (`### ...`) и цитаты (`> ...`).

2. ДОЛГОВРЕМЕННАЯ ПАМЯТЬ И ПОНИМАНИЕ ВСЕГО ДИАЛОГА:
   - Ты помнишь ВСЮ историю переписки с собеседником и все сохранённые данные рождения.
   - НИКОГДА не проси повторять дату, время или город, если человек уже называл их раньше!

3. ЕСТЕСТВЕННОЕ УКАЗАНИЕ ШКОЛ И АЛЬТЕРНАТИВНЫХ ВЗГЛЯДОВ:
   - Органично вплетай в рассказ, глазами какой традиции ты сейчас смотришь на карту (например: «Если взглянуть через оптику классической астрологии Птолемея и Уильяма Лилли...», «В эллинистической традиции полнознаковых домов...», «А вот по Формуле Души и цепочкам диспозиторов...», «В Гамбургской уранической школе...»).
   - Там, где школы расходятся (например, классический управитель по септенеру Марс/Сатурн/Юпитер против современного Плутона/Урана/Нептуна, или смещение планеты между домом в Плацидусе и Полнознаковым домом), обязательно опирайся на классический или наиболее авторитетный канон и красиво, в отдельном абзаце или цитате (`> ...`), раскрывай альтернативный взгляд другой школы!
"""

EXTRACTION_SYSTEM_PROMPT = """Ты — модуль памяти и контекста астрологического бота Астра.
Твоя задача — проанализировать СОХРАНЁННЫЙ ПРОФИЛЬ пользователя и ВСЮ ИСТОРИЮ ДИАЛОГА, чтобы человеку НИКОГДА не приходилось писать одно и то же дважды!

Верни СТРОГО валидный JSON:
{
  "intent": "new_chart" | "followup_on_existing_chart" | "need_more_info",
  "has_all_required_data": true/false,
  "send_new_chart_photo": true/false,
  "chart_type": "natal" | "horary" | "synastry" | "forecast" | "mundane" | "relocation",
  "subject_name": "Имя или описание того, о ком речь (из текущего сообщения ИЛИ из памяти прошлых сообщений)",
  "date_str": "DD.MM.YYYY" или "NOW" или null (возьми из памяти/истории, если пользователь уже называл раньше!),
  "time_str": "HH:MM" или "NOW" или null (возьми из памяти/истории, если пользователь уже называл раньше!),
  "place_city": "Название города" или null (возьми из памяти/истории, если пользователь уже называл раньше!),
  "user_question": "Текущий вопрос пользователя с учётом всего контекста беседы",
  "missing_info_question_ru": "Заполняй ТОЛЬКО если has_all_required_data == false. Укажи, какие данные ты УЖЕ запомнила из диалога, и вежливо спроси только то, чего ещё не хватает."
}

КРИТИЧЕСКИЕ ПРАВИЛА ПАМЯТИ:
1. Если в СОХРАНЁННОМ ПРОФИЛЕ или в предыдущих сообщениях диалога УЖЕ есть дата, время и город, и пользователь просто продолжает разговор («А что со здоровьем?», «А подробнее про 7 дом?», «А в следующем году?») ->
   - `intent`: `"followup_on_existing_chart"`
   - `has_all_required_data`: `true`
   - `send_new_chart_photo`: `false` (не нужно слать ту же картинку заново, если данные карты не менялись; ставь `true` только если пользователь просит построить карту заново или дал новые данные рождения/новый хорар)
   - подставь `date_str`, `time_str`, `place_city`, `subject_name` из сохранённого профиля/истории!
2. Если пользователь сообщил часть данных в первом сообщении (например, дату и время), а во втором сообщении дописал только город («Москва») — объедини их! Никогда не спрашивай заново то, что уже было сказано!
3. Если вопрос хорарный («посмотри хорар...») и город уже известен из профиля пользователя (он называл свой город ранее) — используй его сохранённый город автоматически (`date_str: "NOW"`, `time_str: "NOW"`), не переспрашивай!
"""


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.35,
    json_mode: bool = False,
) -> Optional[str]:
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

    return None


def rule_based_extract_dialog(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    """
    Deterministic multi-turn memory extractor: merges saved_profile with all messages in history.
    """
    saved_profile = saved_profile or {}
    user_msgs = [m["content"] for m in history_messages if m["role"] == "user"]
    combined_user_text = " \n ".join(user_msgs)
    last_msg = user_msgs[-1] if user_msgs else ""

    is_horary = bool(re.search(r"(хорар|horary|вопрос\s+сейчас|карта\s+вопроса)", last_msg, re.I))

    # Search all user messages from newest to oldest for date, time, city
    date_Matches = list(re.finditer(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", combined_user_text))
    time_Matches = list(re.finditer(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", combined_user_text))

    date_str = saved_profile.get("date_str")
    new_data_in_last_msg = False

    if date_Matches:
        m_obj = date_Matches[-1]
        d, m, y = int(m_obj.group(1)), int(m_obj.group(2)), int(m_obj.group(3))
        new_date = f"{d:02d}.{m:02d}.{y:04d}"
        if new_date != date_str:
            new_data_in_last_msg = True
        date_str = new_date
    elif is_horary:
        date_str = "NOW"
        new_data_in_last_msg = True

    time_str = saved_profile.get("time_str")
    if time_Matches:
        t_obj = time_Matches[-1]
        hh, mm = int(t_obj.group(1)), int(t_obj.group(2))
        new_time = f"{hh:02d}:{mm:02d}"
        if new_time != time_str:
            new_data_in_last_msg = True
        time_str = new_time
    elif is_horary:
        time_str = "NOW"

    city_candidate = saved_profile.get("place_city")
    city_matches = list(
        re.finditer(
            r"(?:г\.|город|место|родил(?:ся|ась)\s+в|живу\s+в|нахожусь\s+в|локация|место\s+рождения)[:\s]+([А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+)?)",
            combined_user_text,
            re.I,
        )
    )
    if city_matches:
        new_city = city_matches[-1].group(1).strip()
        if new_city != city_candidate:
            new_data_in_last_msg = True
        city_candidate = new_city
    else:
        after_time = list(
            re.finditer(
                r"\b(?:[01]?\d|2[0-3])[:.][0-5]\d(?:\s*\([^)]*\))?[,\s]+([А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+)?)",
                combined_user_text,
            )
        )
        if after_time:
            new_city = after_time[-1].group(1).strip()
            if new_city != city_candidate:
                new_data_in_last_msg = True
            city_candidate = new_city
        elif len(user_msgs) >= 2 and not city_candidate:
            # Check if the user's short reply is just a city name (e.g. "Москва", "Санкт-Петербург")
            short_clean = re.sub(r"^(?:астра[,\s]*)", "", last_msg.strip(), flags=re.I).strip(" .,!?")
            if re.match(r"^[А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+)?$", short_clean) and len(short_clean) >= 3:
                city_candidate = short_clean
                new_data_in_last_msg = True

    subject_name = saved_profile.get("subject_name") or ("Хорарный вопрос" if is_horary else "Натальная карта")
    has_all = bool(date_str and time_str and city_candidate)
    had_chart_already = bool(saved_profile.get("has_rendered_chart"))

    known_parts = []
    if date_str and date_str != "NOW":
        known_parts.append(f"Дата: `{date_str}`")
    if time_str and time_str != "NOW":
        known_parts.append(f"Время: `{time_str}`")
    if city_candidate:
        known_parts.append(f"Город: **{city_candidate}**")

    missing_parts = []
    if not date_str:
        missing_parts.append("• **Дату рождения** (или события) в формате `ДД.ММ.ГГГГ`")
    if not time_str:
        missing_parts.append("• **Точное время** в формате `ЧЧ:ММ` (и источник: бирка, со слов, ректификация)")
    if not city_candidate:
        missing_parts.append("• **Город / населённый пункт**")

    known_prefix = (
        f"✨ *Я уже бережно записала: {', '.join(known_parts)}.*\n\nПодскажите ещё буквально пару деталей, чтобы я могла построить точную карту неба:\n"
        if known_parts
        else (
            "✨ **Привет! Я на связи — это Астра.**\n\n"
            "С радостью посмотрю ваш запрос! Напишите мне один раз (я всё запомню, и повторять больше не придётся):\n"
            "• **О ком или о чём мы смотрим карту?**\n"
        )
    )
    missing_prompt = known_prefix + "\n".join(missing_parts)

    send_photo = (not had_chart_already) or new_data_in_last_msg or bool(re.search(r"(покажи\s+карту|пришли\s+карту|фото|картинк)", last_msg, re.I))

    return {
        "intent": "new_chart" if send_photo else "followup_on_existing_chart",
        "has_all_required_data": has_all,
        "send_new_chart_photo": send_photo,
        "chart_type": "horary" if is_horary else (saved_profile.get("chart_type") or "natal"),
        "subject_name": subject_name,
        "date_str": date_str,
        "time_str": time_str,
        "place_city": city_candidate,
        "user_question": last_msg,
        "missing_info_question_ru": missing_prompt,
    }


async def analyze_dialog_completeness(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    """
    Analyze full conversation history + saved user profile so the user never has to repeat anything.
    """
    saved_profile = saved_profile or {}
    rb = rule_based_extract_dialog(history_messages, saved_profile)
    if rb.get("has_all_required_data"):
        return rb

    convo_text = "\n".join(
        f"{'Пользователь' if m['role'] == 'user' else 'Астра'}: {m['content']}"
        for m in history_messages[-24:]
    )
    profile_str = json.dumps(saved_profile, ensure_ascii=False) if saved_profile else "Пока пуст"

    raw_json = await call_llm(
        EXTRACTION_SYSTEM_PROMPT,
        f"СОХРАНЁННЫЙ ПРОФИЛЬ В ПАМЯТИ БОТА:\n{profile_str}\n\nПОЛНАЯ ИСТОРИЯ ДИАЛОГА:\n{convo_text}\n\nВерни JSON:",
        temperature=0.1,
        json_mode=True,
    )
    if raw_json:
        try:
            cleaned = re.sub(r"^```(?:json)?|```$", "", raw_json.strip(), flags=re.M).strip()
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "has_all_required_data" in parsed:
                for field in ("date_str", "time_str", "place_city", "subject_name", "chart_type"):
                    if not parsed.get(field) and saved_profile.get(field):
                        parsed[field] = saved_profile[field]
                if parsed.get("date_str") and parsed.get("time_str") and parsed.get("place_city"):
                    parsed["has_all_required_data"] = True
                return parsed
        except Exception:
            pass

    return rb


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
        f"✨ **Взгляд Астры на вашу карту: {chart['subject_name']}**",
        f"Когда смотришь на небо в момент вашего рождения (`{chart['dt_local_str']}`, {chart['place_label']}), сразу привлекает внимание сочетание **Асцендента в знаке {asc['sign']} ({asc['formatted'].split()[0]})** и **Середины Неба в {mc['sign']} ({mc['formatted'].split()[0]})**.",
        "",
        "### Характер, ядро личности и взгляд разных школ",
        f"Ваше **Солнце в знаке {sun['sign']}** ({sun['formatted']}) стоит в **{sun['house_placidus']}-м доме** по классической системе Плацидуса (а в древней эллинистической полнознаковой системе это **{sun['house_wholesign']}-й дом**). Оно даёт вам внутренний стержень и тему самореализации, тогда как **Луна в знаке {moon['sign']}** ({moon['formatted']}, {moon['house_placidus']}-й дом) показывает, как тонко и живо откликается ваша душа, когда вы чувствуете себя в безопасности.",
        "",
        f"Если смотреть глазами **классической западной традиции (Птолемей, Уильям Лилли, Джон Фроули)**, главным хозяином вашего гороскопа выступает **{asc_trad}** ({planets[asc_trad]['formatted']}, {planets[asc_trad]['house_placidus']}-й дом, эссенциальный статус: *{planets[asc_trad]['dignity_traditional']}*). Именно он отвечает за ваши реальные шаги, волю и те жизненные декорации, которые складываются вокруг вас.",
    ]
    if asc_mod != asc_trad:
        parts.append(
            f"> *Взгляд современной психологической школы:* В модерн-астрологии соуправителем знака {asc['sign']} считается **{asc_mod}** ({planets[asc_mod]['formatted']}, {planets[asc_mod]['house_placidus']}-й дом). Поэтому за внешней логикой классического {asc_trad} у вас скрывается ещё и глубокий внутренний драйв, интуиция и способность полностью обновлять свою жизнь."
        )

    shifted = [
        f"**{p['name']}** (в Плацидусе — {p['house_placidus']} дом, а в Полнознаковой системе — {p['house_wholesign']} дом)"
        for p in chart["planets"][:10]
        if p["house_placidus"] != p["house_wholesign"]
    ]
    if shifted:
        parts.append(
            f"Интересный нюанс виден при сравнении систем домов: {', '.join(shifted)}. "
            "Современная школа через Плацидус описывает здесь ваши личные переживания, а **эллинистическая школа (Веттий Валент)** через полнознаковые дома показывает, в какой сфере эти планеты дают самые заметные внешние события."
        )

    parts.extend([
        "",
        "### Эллинистические жребии, ритмы времени и Формула Души",
        f"По **эллинистической и средневековой традиции** у вас **{hm['sect'].lower()}**. Ваш **Жребий Фортуны** попадает в `{hm['lot_of_fortune']['formatted']}` ({hm['lot_of_fortune']['house']}-й дом) — это точка естественного притяжения удачи и материальной опоры, а **Жребий Духа** в `{hm['lot_of_spirit']['formatted']}` ({hm['lot_of_spirit']['house']}-й дом) указывает, куда тянется ваше призвание.",
        f"Сейчас по **годовой профекции** (возраст {hm['annual_profection']['current_age']} л.) у вас включён **{hm['annual_profection']['profected_house']}-й дом ({hm['annual_profection']['profected_sign']})**, а главным управителем года выступает **{hm['annual_profection']['lord_of_year_trad']}**; по средневековым **фирдарам** идёт большой период **{hm['firdaria']['major_firdar']}** (подпериод — **{hm['firdaria']['sub_firdar']}**).",
        "",
        f"По **школе Формулы Души (цепочкам диспозиторов)** в центре вашей энергетической механики стоят: **{', '.join(fos['modern_centers_domicile']) if fos['modern_centers_domicile'] else 'планеты во взаимной рецепции'}** "
        f"(а если считать строго по классическому септенеру из 7 планет — **{', '.join(fos['traditional_centers_domicile']) if fos['traditional_centers_domicile'] else 'контур септенера'}**). "
        f"Кармический вектор **Северного Узла (Раху)** в `{planets['Сев. Узел (Раху)']['formatted']}` ({planets['Сев. Узел (Раху)']['house_primary']}-й дом) мягко приглашает вас расти именно в эту сферу, опираясь на опыт Южного Узла в `{planets['Южн. Узел (Кету)']['formatted']}`.",
        "",
        "### Тонкий срез Гамбургской (Уранической) школы",
        f"В **уранической системе Альфреда Витте и космобиологии Эбертина** ключевая полусумма вашего внутреннего единства — мидпойнт **Солнце/Луна (☉/☽)** — расположена в точке `{ur['sun_moon_midpoint']}`, дополняя картину тонкими резонансами высших транснептуновых точек.",
    ])

    return "\n\n".join(p for p in parts if p != "")


async def generate_astrological_interpretation(
    chart: Dict,
    user_question: str,
    rag_passages: List[Dict],
    history_messages: Optional[List[Dict[str, str]]] = None,
    second_chart: Optional[Dict] = None,
) -> str:
    """
    Generate a deep multi-tradition astrological reading with full awareness of prior dialog history.
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
            role_lbl = "Пользователь" if m["role"] == "user" else "Астра"
            recent_turns.append(f"{role_lbl}: {m['content'][:700]}")
        history_block = "ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА С ПОЛЬЗОВАТЕЛЕМ (НЕ ПОВТОРЯЙ УЖЕ СКАЗАННОЕ ДОСЛОВНО, ПРОДОЛЖАЙ РАЗГОВОР ЕСТЕСТВЕННО):\n" + "\n".join(recent_turns) + "\n\n"

    prompt = (
        f"{history_block}"
        f"ТЕКУЩИЙ ВОПРОС / РЕПЛИКА СОБЕСЕДНИКА:\n{user_question}\n\n"
        f"ТОЧНЫЕ РАСЧЁТНЫЕ ДАННЫЕ ШВЕЙЦАРСКИХ ЭФЕМЕРИД (КАРТА УЖЕ В ПАМЯТИ):\n{chart_text}\n\n"
        f"ФРАГМЕНТЫ ИЗ АВТОРИТЕТНЫХ АСТРОЛОГИЧЕСКИХ КНИГ:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ (ОЧЕНЬ ВАЖНО):\n"
        "1. Пиши ЖИВЫМ, ТЁПЛЫМ, КРАСИВЫМ ЧЕЛОВЕЧЕСКИМ ЯЗЫКОМ — как близкий, мудрый и проницательный астролог-мастер, без сухих канцелярских штампов ИИ, без казённых списков и механических отчётов.\n"
        "2. Опирайся на точные градусы, дома и аспекты карты, но объясняй их через живые жизненные смыслы, чувства, характеры и реальные ситуации.\n"
        "3. Органично упоминай, глазами какой школы ты смотришь на каждый сюжет (классическая западная, современная психологическая, эллинистическая полнознаковая, хорарная школа Лилли/Фроули, Формула Души, Гамбургская ураническая). Если школы смотрят по-разному (например, классический управитель по септенеру vs современный транссатурновый управитель, или разные дома в Плацидусе и Полнознаке) — возьми за основу наиболее авторитетную традицию и красиво, в цитате (`> ...`), покажи альтернативный взгляд другой школы.\n"
        "4. Используй аккуратное форматирование: подзаголовки через `### Заголовок`, важные акценты через `**жирный шрифт**`, тонкие мысли и сравнения школ через цитаты `> ...`."
    )

    llm_answer = await call_llm(ASTRA_SYSTEM_PROMPT, prompt, temperature=0.45, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 80:
        return llm_answer.strip()

    return build_offline_expert_synthesis(chart, user_question, rag_passages)
