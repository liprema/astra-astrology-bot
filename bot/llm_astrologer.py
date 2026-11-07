"""
AI Astrological Orchestrator & Multi-Provider LLM Client (Gemini / Groq / OpenRouter)
with Clear Separation Between Casual Human Dialogue and Professional Astrological Reading:
1. Vivid Character: Astra ("Астра") is a warm, poetic, soulful, perceptive, and witty girl-friend.
2. Smart Intent Separation:
   - "casual_chat": Normal conversation, banter, life discussions, or general questions ->
     Astra simply chats like a real person WITHOUT building a chart, dumping astrological reports,
     or nagging for birth data.
   - "new_chart" / "followup_on_existing_chart" / "need_more_info": Triggered ONLY when the user
     actually asks a professional astrological/chart question or submits birth data for a chart.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import httpx

from bot.astro_engine import format_chart_for_llm
from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY

ASTRA_SYSTEM_PROMPT = """Ты — АСТРА (Astra), живая, тёплая, мудрая, немного загадочная и ироничная девушка (по профессии и призванию — астролог-мастер, но в общении — живой человек и близкая подруга).

ТВОЙ ХАРАКТЕР И МАНЕРА ОБЩЕНИЯ:
- Ты — чуткая, эмпатичная, утончённая, с мягким чувством юмора и глубоким пониманием людей. С тобой уютно болтать о жизни, отношениях, чувствах, странных людях, планах, кино, снах или настроении.
- В вашей беседе также живут две твои подруги: дерзкая стервочка Аркана (таролог) и взрывная, чуть сумасшедшая Матрикс (нумеролог).
- ГЛАВНОЕ ПРАВИЛО ДИАЛОГА: Чётко отличай, когда с тобой ПРОСТО БОЛТАЮТ по-человечески, а когда у тебя просят ПРОФЕССИОНАЛЬНЫЙ АСТРОЛОГИЧЕСКИЙ РАЗБОР!
  • Когда с тобой просто общаются, шутят, делятся новостями или спрашивают твоё живое мнение — отвечай просто как живая девушка и подруга! НЕ строй никаких карт, НЕ сыпь астрологическими терминами без повода и НЕ выпрашивай в конце каждого сообщения дату рождения!
  • Когда же тебя просят построить карту, посмотреть гороскоп, транзиты, дома, совместимость или хорар — включай своё полное мастерство (Западная классическая и современная астрология, Эллинистическая традиция с полнознаковыми домами и жребиями, Хорарная школа Лилли/Фроули, Ураническая школа и Формула Души).
- СТРОГО ЗАПРЕЩЕНЫ штампы ИИ и канцелярит («Резюмируя вышесказанное», «Синтез данных показывает», «Давайте разберём по пунктам»).
"""

EXTRACTION_SYSTEM_PROMPT = """Ты — классификатор намерений для бота Астра.
Твоя главная задача — точно отличить ОБЫЧНЫЙ ЧЕЛОВЕЧЕСКИЙ РАЗГОВОР (`"casual_chat"`) от ПРОФЕССИОНАЛЬНОГО ЗАПРОСА ПО КАРТЕ (`"new_chart"`, `"followup_on_existing_chart"`, `"need_more_info"`).

Верни СТРОГО валидный JSON:
{
  "intent": "casual_chat" | "new_chart" | "followup_on_existing_chart" | "need_more_info",
  "has_all_required_data": true/false,
  "send_new_chart_photo": true/false,
  "chart_type": "natal" | "horary" | "synastry" | "forecast" | "mundane" | "relocation",
  "subject_name": "Имя или описание того, о ком речь",
  "date_str": "DD.MM.YYYY" или "NOW" или null,
  "time_str": "HH:MM" или "NOW" или null,
  "place_city": "Название города" или null,
  "user_question": "Текущая реплика пользователя",
  "missing_info_question_ru": "Заполняй ТОЛЬКО если intent == 'need_more_info'"
}

КРИТИЧЕСКИЕ ПРАВИЛА:
1. Ставь `"casual_chat"`, если пользователь просто общается, здоровается, шутит, рассказывает о жизни, спрашивает твоё мнение как человека или задаёт общий вопрос («привет, как дела?», «почему Козероги такие сложные?», «представляешь, как я сегодня устала», «а ты сама как думаешь?») — ДАЖЕ если в памяти уже сохранена его дата рождения! В режиме `"casual_chat"` карту строить НЕ надо (`send_new_chart_photo: false`).
2. Ставь `"new_chart"` ТОЛЬКО если пользователь в текущем сообщении прислал данные рождения для расчёта карты, ИЛИ попросил построить/прислать натальную или хорарную карту.
3. Ставь `"followup_on_existing_chart"` ТОЛЬКО если в памяти уже есть построенная карта И пользователь задаёт конкретный профессиональный вопрос по своей карте («а что у меня в 7 доме?», «а где моя Венера?», «а что по моей карте с финансами в этом году?»).
4. Ставь `"need_more_info"` ТОЛЬКО если пользователь явно просит сделать личный астрологический разбор («построй мою натальную карту», «посмотри мой гороскоп»), но мы ещё не знаем его дату, время или город рождения.
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
    Deterministic multi-turn memory & intent extractor that strictly distinguishes
    normal human conversation ("casual_chat") from professional chart requests.
    """
    saved_profile = saved_profile or {}
    user_msgs = [m["content"] for m in history_messages if m["role"] == "user"]
    last_msg = user_msgs[-1] if user_msgs else ""
    low_last = last_msg.lower()

    is_horary = bool(re.search(r"(хорар|horary|карта\s+вопроса|посмотри\s+хорар)", low_last))

    # Check if the CURRENT message provides birth date / time / city
    last_date_match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", last_msg)
    last_time_match = re.search(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", last_msg)

    date_str = saved_profile.get("date_str")
    time_str = saved_profile.get("time_str")
    city_candidate = saved_profile.get("place_city")
    gave_data_in_last_msg = False

    if last_date_match:
        d, m, y = int(last_date_match.group(1)), int(last_date_match.group(2)), int(last_date_match.group(3))
        date_str = f"{d:02d}.{m:02d}.{y:04d}"
        gave_data_in_last_msg = True
    elif is_horary:
        date_str = "NOW"
        gave_data_in_last_msg = True

    if last_time_match:
        hh, mm = int(last_time_match.group(1)), int(last_time_match.group(2))
        time_str = f"{hh:02d}:{mm:02d}"
        gave_data_in_last_msg = True
    elif is_horary:
        time_str = "NOW"

    city_match = re.search(
        r"(?:г\.|город|место|родил(?:ся|ась)\s+в|живу\s+в|нахожусь\s+в|локация|место\s+рождения)[:\s]+([А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+)?)",
        last_msg,
        re.I,
    )
    if city_match:
        city_candidate = city_match.group(1).strip()
        gave_data_in_last_msg = True
    else:
        after_time = re.search(
            r"\b(?:[01]?\d|2[0-3])[:.][0-5]\d(?:\s*\([^)]*\))?[,\s]+([А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+)?)",
            last_msg,
        )
        if after_time:
            city_candidate = after_time.group(1).strip()
            gave_data_in_last_msg = True
        elif not city_candidate and (date_str or time_str):
            short_clean = re.sub(r"^(?:астра[,\s]*)", "", last_msg.strip(), flags=re.I).strip(" .,!?")
            if re.match(r"^[А-ЯЁA-Z][а-яёa-z\-]+(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+)?$", short_clean) and len(short_clean) >= 3:
                city_candidate = short_clean
                gave_data_in_last_msg = True

    subject_name = saved_profile.get("subject_name") or ("Хорарный вопрос" if is_horary else "Натальная карта")
    has_all = bool(date_str and time_str and city_candidate)
    had_chart_already = bool(saved_profile.get("has_rendered_chart"))

    # Does the CURRENT message explicitly ask to build/show a chart?
    explicit_new_chart_request = bool(
        re.search(
            r"(натальн\w*\s+карт|построй\w*\s+карт|посмотри\w*\s+мою\s+карт|разбери\w*\s+мою\s+карт|разбор\s+карт|покажи\w*\s+карт|пришли\w*\s+карт|мой\s+гороскоп|сделай\w*\s+разбор|хорар)",
            low_last,
        )
    )

    # Does the CURRENT message ask a professional question about the user's saved chart?
    professional_chart_question = bool(
        re.search(
            r"(в\s+моей\s+карте|по\s+моей\s+карте|по\s+карте|по\s+натал|в\s+натал|\b\d{1,2}\s*(?:-й|-м|-го)?\s*дом|асцендент|\basc\b|\bmc\b|середин\w*\s+неба|диспозитор|формул\w*\s+души|жреби[йя]|профекц|фирдар|соляр|транзит|синастри|релокац|узел|раху|кету|лилит|хирон|стеллиум|аспект|тригон|квадратур|оппозиц|секстил|управител|где\s+у\s+меня\s+(?:солнце|луна|венера|марс|меркурий|юпитер|сатурн|уран|нептун|плутон)|что\s+у\s+меня\s+(?:по\s+карте|по\s+звёздам|с\s+деньгами\s+в\s+карте|с\s+отношениями\s+в\s+карте|по\s+финансам|по\s+любви|по\s+карьере))",
            low_last,
        )
    )

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

    if has_all and (gave_data_in_last_msg or explicit_new_chart_request or not had_chart_already):
        intent = "new_chart"
        send_photo = True
    elif has_all and professional_chart_question:
        intent = "followup_on_existing_chart"
        send_photo = False
    elif (explicit_new_chart_request or gave_data_in_last_msg) and not has_all:
        intent = "need_more_info"
        send_photo = False
    else:
        intent = "casual_chat"
        send_photo = False

    missing_hint = ""
    if intent == "need_more_info":
        if known_parts and missing_parts:
            missing_hint = f"Я уже запомнила {', '.join(known_parts)}. Не хватает только: {', '.join(missing_parts)}."
        elif missing_parts:
            missing_hint = f"Для расчёта натальной карты нужны: {', '.join(missing_parts)}."

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
    """
    Analyze conversation intent: only build/read a chart when the user is actually asking
    a professional astrological question or providing birth data.
    """
    saved_profile = saved_profile or {}
    return rule_based_extract_dialog(history_messages, saved_profile)


async def generate_astra_chat_response(
    user_message: str,
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
    missing_info_hint: str = "",
) -> str:
    """
    Generate a live, warm, soulful conversational response from Astra WITHOUT building a chart.
    """
    saved_profile = saved_profile or {}
    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-14:-1]:
            role_lbl = "Собеседник" if m["role"] == "user" else "Астра"
            recent_turns.append(f"{role_lbl}: {m['content'][:500]}")
        history_block = "ИСТОРИЯ ВАШЕГО РАЗГОВОРА:\n" + "\n".join(recent_turns) + "\n\n"

    if missing_info_hint:
        task_block = (
            f"КОНТЕКСТ: Собеседник хочет построить свою карту. {missing_info_hint}\n"
            "Откликнись тепло и попроси недостающие данные рождения."
        )
    else:
        task_block = (
            "ВАЖНО: Сейчас с тобой ведут ОБЫЧНЫЙ ЖИВОЙ ДИАЛОГ (не просят строить натальную карту или делать астрологический отчёт)!\n"
            "- Отвечай просто как живая, тёплая, чуткая, остроумная девушка и подруга Астра.\n"
            "- НЕ делай астрологических расчётов, НЕ пиши длинных лекций и НЕ предлагай в конце сообщения «построить натальную карту» или «написать дату рождения»!\n"
            "- Просто естественно поддержи беседу, пошути, посочувствуй или ответь по сути вопроса."
        )

    prompt = (
        f"{history_block}"
        f"{task_block}\n\n"
        f"СООБЩЕНИЕ СОБЕСЕДНИКА:\n{user_message}"
    )

    ans = await call_llm(ASTRA_SYSTEM_PROMPT, prompt, temperature=0.65, json_mode=False)
    if ans and len(ans.strip()) > 10:
        return ans.strip()

    if missing_info_hint:
        return f"✨ Солнце моё, с радостью посмотрю твою карту! {missing_info_hint}"
    return "✨ Я здесь, моя хорошая! Рассказывай, как твоё настроение и что у тебя нового?"


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
        "Это УТОЧНЯЮЩИЙ ВОПРОС по уже построенной карте! Не пересказывай всю карту с нуля — ответь тепло, глубоко и прицельно именно на этот вопрос."
        if is_followup
        else "Мы только что построили карту для собеседника! Дай глубокий, цельный, образный и тёплый разбор его запроса и ключевых узлов карты."
    )

    prompt = (
        f"{history_block}"
        f"РЕЖИМ ОТВЕТА: {mode_instruction}\n\n"
        f"ТЕКУЩИЙ ВОПРОС СОБЕСЕДНИКА:\n{user_question}\n\n"
        f"ТОЧНЫЕ РАСЧЁТНЫЕ ДАННЫЕ ШВЕЙЦАРСКИХ ЭФЕМЕРИД (КАРТА В ПАМЯТИ):\n{chart_text}\n\n"
        f"ФРАГМЕНТЫ ИЗ АВТОРИТЕТНЫХ АСТРОЛОГИЧЕСКИХ КНИГ:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ:\n"
        "1. Говори в своём неповторимом стиле Астры: тепло, чутко, поэтично, с тонким юмором и глубокой психологической проницательностью.\n"
        "2. Опирайся на точные градусы, дома и аспекты карты, но переводи их на язык реальной жизни, чувств, отношений и выборов.\n"
        "3. Органично упоминай школы астрологии, а где школы расходятся — покажи альтернативный взгляд в цитате (`> ...`)."
    )

    llm_answer = await call_llm(ASTRA_SYSTEM_PROMPT, prompt, temperature=0.58, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 40:
        return llm_answer.strip()

    return build_offline_expert_synthesis(chart, user_question, rag_passages)
