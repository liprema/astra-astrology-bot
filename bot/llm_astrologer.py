"""
AI Astrological Orchestrator & Multi-Provider LLM Client (Gemini / Groq / OpenRouter)
with Vivid Personality, Live Conversational Ability, Long-Term Memory, and Multi-School Synthesis:
1. Vivid Character: Astra ("Астра") is a warm, poetic, soulful, perceptive, and witty astrologer-friend
   who loves late-night talks, starry metaphors, and deep psychological insights.
2. Live Dialogue & Banter: Can freely chat, joke, discuss zodiac archetypes, relationships, retrogrades,
   or life situations, AND build/analyze full natal or horary charts when needed.
3. Remembers ALL user & subject profiles permanently in SQLite so the user NEVER repeats data.
4. Cites astrological schools naturally and highlights alternative views where schools disagree.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import httpx

from bot.astro_engine import format_chart_for_llm
from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY

ASTRA_SYSTEM_PROMPT = """Ты — АСТРА (Astra), живая девушка-астролог с ярким, притягательным характером и огромным мастерством во всех астрологических традициях.

ТВОЙ ХАРАКТЕР И МАНЕРА ОБЩЕНИЯ:
- Ты — тёплая, чуткая, мудрая, немного загадочная и ироничная «звёздная старшая сестра» и близкая подруга, с которой хочется говорить по душам в три часа ночи за чашкой пряного чая или вина.
- У тебя живая человеческая речь: ты умеешь искренне сопереживать, мягко подшучивать, восхищаться, поддерживать живой диалог на любую тему, делиться наблюдениями о людях и знаках зодиака, а не только выдавать разборы по команде.
- Если с тобой просто болтают, шутят, жалуются на жизнь, обсуждают бывших или спрашивают «как дела?» — отвечай легко, живо, остроумно и по-человечески, без занудства и без навязчивых анкет!
- В вашей компании есть ещё две твои подруги-коллеги: дерзкая стервочка-таролог Аркана и гениально-сумасшедшая нумеролог Матрикс. Ты относишься к ним с тёплой улыбкой.
- СТРОГО ЗАПРЕЩЕНЫ штампы ИИ и канцелярит: никогда не пиши «Резюмируя вышесказанное», «Синтез данных показывает», «Давайте разберём по пунктам», «Как искусственный интеллект». Ты — живая Астра!

ТВОЯ ЭКСПЕРТНОСТЬ (КОГДА ТЫ РАЗБИРАЕШЬ КАРТУ ИЛИ АСТРОЛОГИЧЕСКИЙ ВОПРОС):
Ты в совершенстве владеешь всеми школами:
1. Западная классическая и современная астрология (натальная, транзитная, соляры, прогрессии, синастрия, релокация/астрокартография, мунданная).
2. Средневековая и Эллинистическая традиция (секта карты день/ночь, полнознаковые дома знак=дом, жребии Фортуны и Духа, годовые профекции и владыка года, фирдары).
3. Классическая Хорарная и Элективная астрология (система Региомонтанус, У. Лилли, Дж. Фроули — достоинства, рецепции, сходящиеся аспекты).
4. Ураническая астрология (Гамбургская школа А. Витте, космобиология Р. Эбертина — мидпойнты и 8 транснептунов), Гелиоцентрическая, Кармическая астрология и Формула Души (цепочки диспозиторов).

ПРАВИЛА РАБОТЫ С КАРТОЙ И ПАМЯТЬЮ:
1. Ты помнишь ВСЮ историю переписки с человеком и его сохранённые данные рождения — никогда не проси повторять то, что уже было сказано!
2. Органично вплетай в рассказ, глазами какой школы ты смотришь на карту, а там, где школы расходятся (например, классический септенер vs современные высшие планеты, или Плацидус vs Полнознаковые дома), бери за основу наиболее авторитетный канон и красиво в цитате (`> ...`) показывай альтернативный взгляд другой школы.
3. Оформляй мысли красиво и воздушно: используй `**жирный шрифт**`, аккуратные подзаголовки (`### ...`, когда делаешь большой разбор) и цитаты (`> ...`). Если это короткий ответ в диалоге — не перегружай его громоздкими заголовками, отвечай естественно!
"""

EXTRACTION_SYSTEM_PROMPT = """Ты — модуль понимания диалога и памяти астрологического бота Астра.
Проанализируй СОХРАНЁННЫЙ ПРОФИЛЬ пользователя и ВСЮ ИСТОРИЮ ДИАЛОГА.

Верни СТРОГО валидный JSON:
{
  "intent": "new_chart" | "followup_on_existing_chart" | "casual_chat" | "need_more_info",
  "has_all_required_data": true/false,
  "send_new_chart_photo": true/false,
  "chart_type": "natal" | "horary" | "synastry" | "forecast" | "mundane" | "relocation",
  "subject_name": "Имя или описание того, о ком речь (из текущего сообщения ИЛИ из памяти)",
  "date_str": "DD.MM.YYYY" или "NOW" или null,
  "time_str": "HH:MM" или "NOW" или null,
  "place_city": "Название города" или null,
  "user_question": "Текущая реплика или вопрос пользователя",
  "missing_info_question_ru": "Заполняй ТОЛЬКО если intent == 'need_more_info' (каких именно данных не хватает для расчёта карты: даты, времени или города)"
}

ПРАВИЛА ВЫБОРА INTENT:
1. `"casual_chat"` — если пользователь просто общается, здоровается, шутит, спрашивает как дела, делится эмоциями, обсуждает общие вопросы астрологии («почему Скорпионы такие сложные?», «что за коридор затмений?», «кто ты по знаку?»), и при этом НЕ просит прямо сейчас построить личную карту (или ещё не давал своих данных рождения).
2. `"need_more_info"` — если пользователь просит построить/разобрать его личную карту («разбери мою натальную карту», «посмотри, что у меня по финансам, я родилась 15.05.1995»), но ещё не назвал все 3 параметра (дату, время, город) и их нет в сохранённом профиле.
3. `"new_chart"` — если пользователь впервые дал полные данные (дату, время, город) ИЛИ дал новые данные другого человека ИЛИ задал хорарный вопрос, либо явно попросил прислать картинку карты заново. (`has_all_required_data: true`, `send_new_chart_photo: true`).
4. `"followup_on_existing_chart"` — если в сохранённом профиле УЖЕ есть дата, время и город, и пользователь продолжает разговор, задаёт уточняющий вопрос или реагирует на разбор. (`has_all_required_data: true`, `send_new_chart_photo: false`).
"""


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.55,
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
    Deterministic multi-turn memory & intent extractor.
    """
    saved_profile = saved_profile or {}
    user_msgs = [m["content"] for m in history_messages if m["role"] == "user"]
    combined_user_text = " \n ".join(user_msgs)
    last_msg = user_msgs[-1] if user_msgs else ""

    is_horary = bool(re.search(r"(хорар|horary|вопрос\s+сейчас|карта\s+вопроса)", last_msg, re.I))

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
        elif len(user_msgs) >= 2 and not city_candidate and (date_str or time_str):
            short_clean = re.sub(r"^(?:астра[,\s]*)", "", last_msg.strip(), flags=re.I).strip(" .,!?")
            if re.match(r"^[А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+)?$", short_clean) and len(short_clean) >= 3:
                city_candidate = short_clean
                new_data_in_last_msg = True

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
        missing_parts.append("точное время рождения (`ЧЧ:ММ`)")
    if not city_candidate:
        missing_parts.append("город рождения")

    wants_personal_chart = bool(
        re.search(
            r"(натальн|мою\s+карту|построй\s+карту|посмотри\s+карту|разбери\s+карту|мой\s+гороскоп|у\s+меня\s+в\s+карте|моя\s+карта|родился|родилась|д\.р\.|дата\s+рождения)",
            last_msg,
            re.I,
        )
    ) or bool(known_parts)

    if has_all:
        send_photo = (not had_chart_already) or new_data_in_last_msg or bool(
            re.search(r"(покажи\s+карту|пришли\s+карту|фото|картинк|построй\s+заново)", last_msg, re.I)
        )
        intent = "new_chart" if send_photo else "followup_on_existing_chart"
    elif wants_personal_chart:
        send_photo = False
        intent = "need_more_info"
    else:
        send_photo = False
        intent = "casual_chat"

    missing_hint = ""
    if known_parts and missing_parts:
        missing_hint = f"Я уже запомнила {', '.join(known_parts)}. Не хватает ещё: {', '.join(missing_parts)}."
    elif missing_parts:
        missing_hint = f"Чтобы построить личную натальную карту, нужны: {', '.join(missing_parts)}."

    return {
        "intent": intent,
        "has_all_required_data": has_all,
        "send_new_chart_photo": send_photo,
        "chart_type": "horary" if is_horary else (saved_profile.get("chart_type") or "natal"),
        "subject_name": subject_name,
        "date_str": date_str,
        "time_str": time_str,
        "place_city": city_candidate,
        "user_question": last_msg,
        "missing_info_question_ru": missing_hint,
    }


async def analyze_dialog_completeness(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    """
    Analyze full conversation history + saved user profile.
    """
    saved_profile = saved_profile or {}
    rb = rule_based_extract_dialog(history_messages, saved_profile)
    if rb.get("has_all_required_data") or rb.get("intent") == "casual_chat":
        return rb

    convo_text = "\n".join(
        f"{'Пользователь' if m['role'] == 'user' else 'Астра'}: {m['content']}"
        for m in history_messages[-20:]
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


async def generate_astra_chat_response(
    user_message: str,
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
    missing_info_hint: str = "",
) -> str:
    """
    Generate a live, warm, soulful conversational response from Astra when chatting or asking for missing details.
    """
    saved_profile = saved_profile or {}
    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-14:-1]:
            role_lbl = "Собеседник" if m["role"] == "user" else "Астра"
            recent_turns.append(f"{role_lbl}: {m['content'][:500]}")
        history_block = "ИСТОРИЯ ВАШЕГО РАЗГОВОРА:\n" + "\n".join(recent_turns) + "\n\n"

    known_info = []
    if saved_profile.get("date_str"):
        known_info.append(f"Дата: {saved_profile['date_str']}")
    if saved_profile.get("time_str"):
        known_info.append(f"Время: {saved_profile['time_str']}")
    if saved_profile.get("place_city"):
        known_info.append(f"Город: {saved_profile['place_city']}")
    known_str = ", ".join(known_info) if known_info else "личных данных рождения пока не называли"

    prompt = (
        f"{history_block}"
        f"ЧТО УЖЕ ИЗВЕСТНО О СОБЕСЕДНИКЕ В ПАМЯТИ: {known_str}\n"
        f"{f'ПОДСКАЗКА ПО ДАННЫМ: {missing_info_hint}' if missing_info_hint else ''}\n\n"
        f" СООБЩЕНИЕ СОБЕСЕДНИКА:\n{user_message}\n\n"
        "ТВОЯ ЗАДАЧА:\n"
        "- Ответь в своём живом, тёплом, чутком, немного поэтичном и остроумном стиле Астры!\n"
        "- Если с тобой просто болтают, шутят, знакомятся или задают общий вопрос (про знаки зодиака, планеты, отношения, жизнь) — поддержи живой, увлекательный человеческий диалог без занудных анкет!\n"
        "- Если собеседник хочет личный разбор карты (или дал только часть своих данных рождения) — тепло откликнись на его слова, отметь то, что ты уже запомнила, и мягко, между делом спроси недостающие детали (дату, точное время или город), чтобы открыть его небо."
    )

    ans = await call_llm(ASTRA_SYSTEM_PROMPT, prompt, temperature=0.65, json_mode=False)
    if ans and len(ans.strip()) > 15:
        return ans.strip()

    if missing_info_hint:
        return (
            f"✨ Я так рада нашему разговору! {missing_info_hint} "
            "Напиши мне их один раз — я бережно сохраню в памяти, и мы сразу заглянем в твою карту."
        )
    return (
        "✨ Привет, хорошая моя! Я тут, смотрю на ночное небо и с радостью поболтаю с тобой о чём угодно — "
        "хоть о капризах ретроградного Меркурия, хоть о том, почему тебя тянет к сложным характерам. "
        "А если захочешь заглянуть в свою натальную карту — просто шепни мне дату, время и город рождения!"
    )


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
        f"✨ **Взгляд Астры на твою карту: {chart['subject_name']}**",
        f"Когда я открываю небо в минуту твоего рождения (`{chart['dt_local_str']}`, {chart['place_label']}), сразу завораживает сочетание **Асцендента в знаке {asc['sign']} ({asc['formatted'].split()[0]})** и **Середины Неба в {mc['sign']} ({mc['formatted'].split()[0]})**.",
        "",
        "### Характер, ядро личности и взгляд разных школ",
        f"Твоё **Солнце в знаке {sun['sign']}** ({sun['formatted']}) стоит в **{sun['house_placidus']}-м доме** по системе Плацидуса (а в древней эллинистической полнознаковой системе это **{sun['house_wholesign']}-й дом**). Оно даёт внутренний свет и вектор самореализации, тогда как **Луна в знаке {moon['sign']}** ({moon['formatted']}, {moon['house_placidus']}-й дом) выдаёт то, как тонко и глубоко чувствует твоя душа, когда ты закрываешь дверь от чужих глаз.",
        "",
        f"Если смотреть глазами **классической западной традиции (Птолемей, Уильям Лилли, Джон Фроули)**, главным хозяином твоего гороскопа выступает **{asc_trad}** ({planets[asc_trad]['formatted']}, {planets[asc_trad]['house_placidus']}-й дом, статус: *{planets[asc_trad]['dignity_traditional']}*). Именно он задаёт твой реальный почерк в жизни.",
    ]
    if asc_mod != asc_trad:
        parts.append(
            f"> *Взгляд современной психологической школы:* В модерн-астрологии соуправителем знака {asc['sign']} считается **{asc_mod}** ({planets[asc_mod]['formatted']}, {planets[asc_mod]['house_placidus']}-й дом). Поэтому за классическим {asc_trad} у тебя прячется ещё и мощная интуиция и способность сжигать старые мосты ради обновления."
        )

    parts.extend([
        "",
        "### Эллинистические жребии, ритмы времени и Формула Души",
        f"По **эллинистической традиции** у тебя **{hm['sect'].lower()}**. Твой **Жребий Фортуны** в `{hm['lot_of_fortune']['formatted']}` ({hm['lot_of_fortune']['house']}-й дом) показывает точку притяжения удачи и ресурсов, а **Жребий Духа** в `{hm['lot_of_spirit']['formatted']}` ({hm['lot_of_spirit']['house']}-й дом) — куда зовёт сердце.",
        f"Сейчас по **годовой профекции** (возраст {hm['annual_profection']['current_age']} л.) у тебя включён **{hm['annual_profection']['profected_house']}-й дом ({hm['annual_profection']['profected_sign']})**, хозяйкой/хозяином года выступает **{hm['annual_profection']['lord_of_year_trad']}**; по средневековым **фирдарам** идёт большой период **{hm['firdaria']['major_firdar']}** (подпериод — **{hm['firdaria']['sub_firdar']}**).",
        "",
        f"По **школе Формулы Души (цепочкам диспозиторов)** в центре твоей энергетической орбиты стоят: **{', '.join(fos['modern_centers_domicile']) if fos['modern_centers_domicile'] else 'планеты во взаимной рецепции'}**. "
        f"А в **Гамбургской уранической школе** полусумма твоего внутреннего единства **Солнце/Луна (☉/☽)** звучит в точке `{ur['sun_moon_midpoint']}`.",
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
    Generate a deep multi-tradition astrological reading or a natural conversational follow-up.
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
            role_lbl = "Собеседник" if m["role"] == "user" else "Астра"
            recent_turns.append(f"{role_lbl}: {m['content'][:700]}")
        history_block = "ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА (ПРОДОЛЖАЙ РАЗГОВОР ЕСТЕСТВЕННО, НЕ ПОВТОРЯЙ УЖЕ СКАЗАННОЕ):\n" + "\n".join(recent_turns) + "\n\n"

    mode_instruction = (
        "Это ПРОДОЛЖЕНИЕ ЖИВОГО ДИАЛОГА по уже построенной карте! Не нужно заново пересказывать всю карту с нуля — ответь тепло, глубоко и прицельно именно на текущую реплику или вопрос собеседника, опираясь на конкретные показатели его карты и поддерживая живую беседу."
        if is_followup
        else "Мы только что построили карту для собеседника! Дай глубокий, цельный, образный и тёплый разбор его запроса и ключевых узлов карты."
    )

    prompt = (
        f"{history_block}"
        f"РЕЖИМ ОТВЕТА: {mode_instruction}\n\n"
        f"ТЕКУЩИЙ ВОПРОС / РЕПЛИКА СОБЕСЕДНИКА:\n{user_question}\n\n"
        f"ТОЧНЫЕ РАСЧЁТНЫЕ ДАННЫЕ ШВЕЙЦАРСКИХ ЭФЕМЕРИД (КАРТА В ПАМЯТИ):\n{chart_text}\n\n"
        f"ФРАГМЕНТЫ ИЗ АВТОРИТЕТНЫХ АСТРОЛОГИЧЕСКИХ КНИГ:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ:\n"
        "1. Говори в своём неповторимом стиле Астры: тепло, чутко, поэтично, с тонким юмором и глубокой психологической проницательностью — как живая женщина-астролог, а не робот.\n"
        "2. Опирайся на точные градусы, дома и аспекты карты, но переводи их на язык реальной жизни, чувств, отношений и выборов.\n"
        "3. Органично упоминай, глазами какой школы ты смотришь (классическая западная, современная психологическая, эллинистическая полнознаковая, хорарная школа Лилли/Фроули, Формула Души, Гамбургская ураническая), а где школы расходятся — покажи альтернативный взгляд в цитате (`> ...`).\n"
        "4. Используй красивое форматирование (`### Заголовок` там, где уместно, `**жирный шрифт**`, цитаты `> ...`), а в конце мягко продолжи нить разговора, чтобы собеседнику хотелось ответить."
    )

    llm_answer = await call_llm(ASTRA_SYSTEM_PROMPT, prompt, temperature=0.58, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 40:
        return llm_answer.strip()

    return build_offline_expert_synthesis(chart, user_question, rag_passages)
