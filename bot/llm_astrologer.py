"""
AI Astrological Orchestrator & Multi-Provider LLM Client (Gemini / Groq / OpenRouter)
— Professional-First Astrologer with Vivid Human Character & Post-Session Dialogue:
1. Professional First: Astra ("Астра") is first and foremost a top-tier professional astrologer.
   On ANY substantive question about life, personality, relationships, career, money, future, or timing,
   she immediately looks at the natal/horary chart (or asks for birth date, time, and city if not yet saved).
2. Post-Session & Smalltalk Capable: When the user simply greets her, reacts after a session ("Спасибо!",
   "Ого, как точно!"), or makes small talk without a new analytical question, she replies warmly and naturally
   without re-dumping the entire chart.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import httpx

from bot.astro_engine import format_chart_for_llm
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


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.48,
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

    # If the message contains any analytical/life/astrological question or topic, it is NOT smalltalk!
    substantive_markers = re.search(
        r"(\d|кар[т]|гороскоп|натал|хорар|дом|планет|солнц|лун|асцендент|венер|марс|сатурн|юпитер|меркур|уран|нептун|плутон|уз[ео]л|раху|кету|лилит|хирон|работ|карьер|деньг|финанс|бизнес|доход|отношен|любов|муж|парн|девушк|жен|бывш|брак|сем[ья]|дет[ией]|переезд|релокац|город|стран|здоров|болезн|выбор|стоит\s+ли|когда|почему\s+у\s+меня|что\s+меня\s+ждет|что\s+ждёт|что\s+с\s+мо|прогноз|год|месяц|недел|период|предназначен|талант|сил\w+\s+сторон|слаб\w+\s+сторон|характер|совместим|синастр|транзит|соляр|фирдар|профекц|формул)",
        cleaned,
    )
    if substantive_markers:
        return False

    # Pure greetings, thanks, reactions, or "how are you / tell me about yourself"
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

    # Extract birth data from history + current message
    date_matches = list(re.finditer(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", combined_user_text))
    time_matches = list(re.finditer(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", combined_user_text))

    date_str = saved_profile.get("date_str")
    time_str = saved_profile.get("time_str")
    city_candidate = saved_profile.get("place_city")
    new_data_in_last_msg = False

    last_date_m = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", last_msg)
    if last_date_m:
        d, m, y = int(last_date_m.group(1)), int(last_date_m.group(2)), int(last_date_m.group(3))
        nd = f"{d:02d}.{m:02d}.{y:04d}"
        if nd != date_str:
            new_data_in_last_msg = True
        date_str = nd
    elif date_matches and not date_str:
        m_obj = date_matches[-1]
        d, m, y = int(m_obj.group(1)), int(m_obj.group(2)), int(m_obj.group(3))
        date_str = f"{d:02d}.{m:02d}.{y:04d}"
    elif is_horary:
        date_str = "NOW"
        new_data_in_last_msg = True

    last_time_m = re.search(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", last_msg)
    if last_time_m:
        hh, mm = int(last_time_m.group(1)), int(last_time_m.group(2))
        nt = f"{hh:02d}:{mm:02d}"
        if nt != time_str:
            new_data_in_last_msg = True
        time_str = nt
    elif time_matches and not time_str:
        t_obj = time_matches[-1]
        hh, mm = int(t_obj.group(1)), int(t_obj.group(2))
        time_str = f"{hh:02d}:{mm:02d}"
    elif is_horary:
        time_str = "NOW"

    city_matches = list(
        re.finditer(
            r"(?:г\.|город|место|родил(?:ся|ась)\s+в|живу\s+в|нахожусь\s+в|локация|место\s+рождения)[:\s]+([А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+)?)",
            combined_user_text,
            re.I,
        )
    )
    if city_matches:
        nc = city_matches[-1].group(1).strip()
        if nc != city_candidate:
            new_data_in_last_msg = True
        city_candidate = nc
    else:
        after_time = list(
            re.finditer(
                r"\b(?:[01]?\d|2[0-3])[:.][0-5]\d(?:\s*\([^)]*\))?[,\s]+([А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+)?)",
                combined_user_text,
            )
        )
        if after_time:
            nc = after_time[-1].group(1).strip()
            if nc != city_candidate:
                new_data_in_last_msg = True
            city_candidate = nc
        elif not city_candidate and (date_str or time_str):
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
            missing_hint = f"Я уже записала {', '.join(known_parts)}. Для точного расчёта карты напишите ещё: {', '.join(missing_parts)}."
        else:
            missing_hint = f"Чтобы я посмотрела этот вопрос по вашей натальной карте, напишите, пожалуйста: {', '.join(missing_parts)} (или уточните, если хотите посмотреть хорарный вопрос на текущий момент)."

    return {
        "intent": intent,
        "has_all_required_data": has_all and intent in ("new_chart", "followup_on_existing_chart"),
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
            f"Кверент обратился с запросом, для которого нужно построить карту. {missing_info_hint}\n"
            "Ответь как чуткий, профессиональный астролог Астра: коротко откликнись по сути вопроса и попроси недостающие данные рождения (дату `ДД.ММ.ГГГГ`, точное время `ЧЧ:ММ` и город), чтобы сразу сделать точный разбор."
        )
    else:
        task_block = (
            "Кверент написал реплику после сессии или поздоровался.\n"
            "Ответь тепло, интеллигентно, живо и лаконично (2–4 предложения) в характере профессионального астролога Астры, поддерживая диалог."
        )

    prompt = f"{history_block}{task_block}\n\nСООБЩЕНИЕ:\n{user_message}"

    ans = await call_llm(ASTRA_SYSTEM_PROMPT, prompt, temperature=0.55, json_mode=False)
    if ans and len(ans.strip()) > 10:
        return ans.strip()

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
