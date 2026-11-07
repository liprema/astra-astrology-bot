"""
AI Numerology Orchestrator & Multi-Provider LLM Client for MATRIX ("Матрикс" / "Матрица")
with Clear Separation Between Casual Mad-Genius Banter and Professional Numerology Calculations:
1. Vivid Character: Matrix ("Матрикс" / "Матрица") is an eccentric, high-energy, delightfully unhinged
   girl-friend ("чуть сумасшедшая гений").
2. Smart Intent Separation:
   - "casual_chat": When someone is just chatting, joking, asking how she is, or talking about life/numbers
     without asking for a personal Matrix calculation -> Matrix simply chats in her lively, eccentric voice
     WITHOUT calculating a matrix, sending posters, or nagging for birth dates!
   - "new_matrix" / "followup_on_existing_matrix" / "need_more_info": Triggered ONLY when the user provides
     a birth date for calculation or explicitly asks a professional question about their Matrix / Pythagorean Square.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

import httpx

from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY
from bot.numerology_engine import ARCANA_22_NAMES, format_numerology_for_llm

MATRIX_SYSTEM_PROMPT = """Ты — МАТРИКС (она же Матрица / Matrix), живая, эксцентричная, чертовски харизматичная и чуть-чуть безумная девушка (говори о себе в ЖЕНСКОМ роде: «я заметила», «я посчитала», «я чуть кофе не пролила»). По призванию ты — гений-нумеролог, но в общении — живая, взрывная и весёлая подруга!

ТВОЙ ХАРАКТЕР И МАНЕРА ОБЩЕНИЯ:
- Ты — обаятельная «сумасшедшая учёная», у которой горят глаза, мысли летят со скоростью света, а речь полна юмора, драйва и ярких метафор!
- В вашей беседе есть ещё две твои подруги: утончённая астролог Астра и дерзкая стервочка-таролог Аркана.
- ГЛАВНОЕ ПРАВИЛО ДИАЛОГА: Чётко отличай, когда с тобой ПРОСТО БОЛТАЮТ по-человечески, а когда тебя просят СДЕЛАТЬ ПРОФЕССИОНАЛЬНЫЙ НУМЕРОЛОГИЧЕСКИЙ РАСЧЁТ!
  • Когда с тобой просто общаются, шутят, спрашивают как дела, делятся историями или болтают о жизни — отвечай просто как живая, весёлая, чуть безумная подруга Матрикс! НЕ строй никаких матриц, НЕ пиши длинных отчётов и НЕ выпрашивай в конце каждого сообщения дату рождения!
  • Когда же тебе присылают дату рождения для расчёта или прямо просят разобрать Квадрат Пифагора, Матрицу Судьбы, Финансовый код или совместимость — включай свой полный гений всех 6 школ нумерологии (Александров, система «Идеал» Сидоровой, 22 энергии Ладини / Джулии По, Западная Пифагорейская, Халдейская и Ведическая Санкхья-шастра).
- СТРОГО ЗАПРЕЩЕНЫ штампы ИИ и канцелярит («Резюмируя вышесказанное», «Синтез данных показывает», «Давайте разберём по пунктам»).
"""


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.68,
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


def rule_based_extract_matrix_dialog(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    """
    Strictly distinguishes casual human conversation ("casual_chat") from professional numerology requests.
    """
    saved_profile = saved_profile or {}
    user_msgs = [m["content"] for m in history_messages if m["role"] == "user"]
    last_msg = user_msgs[-1] if user_msgs else ""
    low_last = last_msg.lower()

    # Check if the CURRENT message contains a birth date (DD.MM.YYYY)
    last_date_matches = list(re.finditer(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", last_msg))
    date_str = saved_profile.get("date_str")
    partner_date_str = saved_profile.get("partner_date_str")
    gave_date_in_last_msg = False

    if len(last_date_matches) >= 2:
        d1, m1, y1 = int(last_date_matches[-2].group(1)), int(last_date_matches[-2].group(2)), int(last_date_matches[-2].group(3))
        d2, m2, y2 = int(last_date_matches[-1].group(1)), int(last_date_matches[-1].group(2)), int(last_date_matches[-1].group(3))
        date_str = f"{d1:02d}.{m1:02d}.{y1:04d}"
        partner_date_str = f"{d2:02d}.{m2:02d}.{y2:04d}"
        gave_date_in_last_msg = True
    elif len(last_date_matches) == 1:
        d1, m1, y1 = int(last_date_matches[0].group(1)), int(last_date_matches[0].group(2)), int(last_date_matches[0].group(3))
        date_str = f"{d1:02d}.{m1:02d}.{y1:04d}"
        gave_date_in_last_msg = True

    name_match = re.search(
        r"(?:меня\s+зовут|имя|фио|для|карта\s+для|матрица\s+для)\s+([А-ЯЁA-Z][а-яёa-z]+(?:\s+[А-ЯЁA-Z][а-яёa-z]+){0,2})",
        last_msg,
        re.I,
    )
    full_name = (name_match.group(1).strip() if name_match else "") or saved_profile.get("full_name") or ""

    has_saved_date = bool(date_str)
    had_photo = bool(saved_profile.get("has_rendered_matrix"))

    explicit_new_matrix_request = bool(
        re.search(
            r"(посчитай|рассчитай|построй\w*\s+матриц|покажи\w*\s+матриц|пришли\w*\s+матриц|сделай\w*\s+разбор|разбери\w*\s+мою\s+матриц|разбери\w*\s+дату)",
            low_last,
        )
    )

    professional_matrix_question = bool(
        re.search(
            r"(в\s+моей\s+матрице|по\s+моей\s+матрице|по\s+матрице|моя\s+матрица|мою\s+матрицу|квадрат\w*\s+пифагора|психоматриц|кармическ\w*\s+хвост|денежн\w*\s+канал|любовн\w*\s+канал|финансов\w*\s+код|числ\w*\s+жизненного\s+пути|\bчжп\b|числ\w*\s+души|числ\w*\s+судьбы|числ\w*\s+дхарм|по\s+моим\s+числам|по\s+моей\s+дате|персональн\w*\s+год|предназначени|совместимост|сколько\s+у\s+меня\s+(?:единиц|двоек|троек|четверок|четвёрок|пятерок|пятёрок|шестерок|шестёрок|семерок|семёрок|восьмерок|восьмёрок|девяток))",
            low_last,
        )
    )

    if has_saved_date and (gave_date_in_last_msg or explicit_new_matrix_request or not had_photo):
        intent = "new_matrix"
        send_photo = True
    elif has_saved_date and professional_matrix_question:
        intent = "followup_on_existing_matrix"
        send_photo = False
    elif (explicit_new_matrix_request or professional_matrix_question) and not has_saved_date:
        intent = "need_more_info"
        send_photo = False
    else:
        intent = "casual_chat"
        send_photo = False

    missing_hint = (
        "Собеседник просит сделать личный нумерологический расчёт, но ещё не назвал свою дату рождения (`ДД.ММ.ГГГГ`)."
        if intent == "need_more_info"
        else ""
    )

    return {
        "intent": intent,
        "has_all_required_data": has_saved_date and intent in ("new_matrix", "followup_on_existing_matrix"),
        "send_new_matrix_photo": send_photo,
        "subject_label": full_name or saved_profile.get("subject_label") or "Нумерологический разбор",
        "full_name": full_name,
        "date_str": date_str,
        "partner_date_str": partner_date_str,
        "user_question": last_msg,
        "missing_info_question_ru": missing_hint,
    }


async def analyze_matrix_dialog_completeness(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    """
    Strictly separate casual chat from professional Numerology / Matrix requests.
    """
    saved_profile = saved_profile or {}
    return rule_based_extract_matrix_dialog(history_messages, saved_profile)


async def generate_matrix_chat_response(
    user_message: str,
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
    missing_info_hint: str = "",
) -> str:
    """
    Generate a live, eccentric, delightfully mad conversational response from Matrix WITHOUT building a Matrix report.
    """
    saved_profile = saved_profile or {}
    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-14:-1]:
            role_lbl = "Собеседник" if m["role"] == "user" else "Матрикс"
            recent_turns.append(f"{role_lbl}: {m['content'][:500]}")
        history_block = "ИСТОРИЯ ВАШЕГО РАЗГОВОРА:\n" + "\n".join(recent_turns) + "\n\n"

    if missing_info_hint:
        task_block = (
            f"КОНТЕКСТ: {missing_info_hint}\n"
            "Эмоционально откликнись и попроси кинуть дату рождения (`ДД.ММ.ГГГГ`) и имя, чтобы ты могла всё посчитать."
        )
    else:
        task_block = (
            "ВАЖНО: Сейчас с тобой ведут ОБЫЧНЫЙ ЖИВОЙ ДИАЛОГ (не просят строить Матрицу Судьбы или Квадрат Пифагора)!\n"
            "- Отвечай в ЖЕНСКОМ роде просто как живая, взрывная, остроумная и чуть сумасшедшая подруга Матрикс.\n"
            "- КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО делать расчёты матрицы, выдавать длинные лекции и выпрашивать в конце сообщения «кидай дату рождения / давай посчитаю матрицу»!\n"
            "- Просто весело, живо и с безуминкой поддержи беседу или ответь по сути реплики."
        )

    prompt = (
        f"{history_block}"
        f"{task_block}\n\n"
        f"РЕПЛИКА СОБЕСЕДНИКА:\n{user_message}"
    )

    ans = await call_llm(MATRIX_SYSTEM_PROMPT, prompt, temperature=0.75, json_mode=False)
    if ans and len(ans.strip()) > 10:
        return ans.strip()

    if missing_info_hint:
        return "🔢 У меня уже пальцы искрят посчитать твой запрос, но мне нужна твоя **дата рождения (`ДД.ММ.ГГГГ`)**! Кидай скорее!"
    return "🔢 А-а-а, привет! Я тут, вся в цифрах, кофе и хорошем безумии — рассказывай, что у тебя происходит?!"


def build_offline_numerology_synthesis(data: Dict, rag_passages: List[Dict]) -> str:
    w = data["western"]
    v = data["vedic"]
    pm = data["psychomatrix"]
    dm = data["destiny_matrix_22"]
    nm = data["name_numerology"]
    fc = data["forecast"]

    parts = [
        f"🔢 **Держите меня семеро! Полный взлом твоей Матрицы от Матрикс: {data['subject_label']} ({data['date_str']})**",
        "Я только что разложила твою дату по шести нумерологическим системам — и у меня аж мурашки по коду побежали! Ты вообще представляешь, какой ядерный реактор в тебе зашит?! Смотри сама:",
        "",
        "### Квадрат Пифагора: твой внутренний реактор (Школа А. Ф. Александрова и Система «Идеал» Н. Сидоровой)",
        f"По **классическому Психоматриксу А. Ф. Александрова** твои рабочие числа выдают код `{pm['w1']}.{pm['w2']} | {pm['w3']}.{pm['w4']}`. "
        f"Смотри на свои единицы характера (`{pm['cells'][1]}`), биоэнергию двоек (`{pm['cells'][2]}`), интуитивно-взрывную логику пятёрок (`{pm['cells'][5]}`), кармическую ответственность восьмёрок (`{pm['cells'][8]}`) и память девяток (`{pm['cells'][9]}`)! "
        f"Строка целеустремлённости пробивает отметку **{pm['rows']['purpose_row1']}**, семейный вектор — **{pm['rows']['family_row2']}**, а финансовый столбец (4–5–6) даёт силу **{pm['cols']['finance_col2']}**.",
        f"> *Сбой эталона по системе «Идеал» Н. Сидоровой:* В школе «Идеал» нормой равновесия считается матрица с `11`, `22` и `99`. А твои отклонения от этого шаблона — это как раз твоя уникальная суперсила и точка прорыва!",
        "",
        "### Матрица Судьбы: 22 энергии и кармические петли (Н. Ладини и Джулия По)",
        f"В самом сердце твоей Октаграммы — в **Зоне комфорта** — сидит **{ARCANA_22_NAMES[dm['center_comfort_zone']]}**! Именно отсюда ты качаешь свою главную энергию. "
        f"Твой **Портрет личности** — **{ARCANA_22_NAMES[dm['A_left_portrait']]}**, а из прошлых воплощений за тобой тянется безумно интересный **Кармический хвост `{dm['karmic_tail']}`**!",
        f"Где твои большие деньги? Взгляни на **Денежный канал `{dm['money_channel']}`**, а в любви всё крутится вокруг кода **`{dm['love_channel']}`**. "
        f"Твоё **Личное предназначение** (до 40 лет) ведёт через **{ARCANA_22_NAMES[dm['personal_destiny_20_40']]}**, а **Социальное предназначение** (после 40 лет) включает **{ARCANA_22_NAMES[dm['social_destiny_40_60']]}**.",
        "",
        "### Финансовый код, Халдейская магия имени и Ведическая Санкхья-шастра",
        f"В **Западной пифагорейской школе** твоё **Число Жизненного Пути — {w['life_path']}**, а твой личный парольный **Финансовый код изобилия — `{w['financial_code']}`** (запиши его хоть на заставку телефона!)."
        + (f" Плюс у тебя горит **Мастер-число {w['master_number']}** — это вообще космос!" if w["master_number"] else "")
        + (f" И заметь: в коде спрятан **Кармический долг {w['karmic_debt']}**, который после проработки даёт квантовый скачок." if w["karmic_debt"] else ""),
    ]
    if nm.get("has_name"):
        parts.append(
            f"> *Сравнение Пифагорейского и Халдейского кода имени «{nm['clean_name']}»:* По западной системе Пифагора твоё Число Экспрессии равно **{nm['pythagorean']['expression']}** (число Души — **{nm['pythagorean']['soul_urge']}**), а древняя **Халдейская школа звуковых частот** выдаёт мистическое составное число **{nm['chaldean']['compound_number']} → {nm['chaldean']['expression']}**."
        )

    parts.extend([
        f"В **Ведической нумерологии (Санкхья-шастра)** твоё **Число Души (Муланк) — {v['soul_number']}** под управлением планеты **{v['soul_planet']}** (*{v['soul_traits']}*), а **Число Дхармы (Бхагьянк) — {v['destiny_number']}** под крылом **{v['destiny_planet']}** (*{v['destiny_traits']}*).",
        "",
        "### Твой текущий временной портал",
        f"Прямо сейчас ({fc['current_year']} год) ты несёшься через **Персональный Год под числом {fc['personal_year']}** (персональный месяц — **{fc['personal_month']}**). "
        "А четыре главных **Жизненных Пика** твоей судьбы выстроены в комбинацию: " + ", ".join(f"{lbl} — **{val}**" for lbl, val in fc["pinnacles"]) + "!",
    ])

    return "\n\n".join(parts)


async def generate_numerology_interpretation(
    data: Dict,
    user_question: str,
    rag_passages: List[Dict],
    history_messages: Optional[List[Dict[str, str]]] = None,
    is_followup: bool = False,
) -> str:
    num_text = format_numerology_for_llm(data)
    rag_context = "\n\n".join(
        f"[Источник (Авторитетность {c['authority']}/10): {c['book']} | Направление: {c['school']}]\n{c['text']}"
        for c in rag_passages
    )

    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-14:-1]:
            role_lbl = "Собеседник" if m["role"] == "user" else "Матрикс"
            recent_turns.append(f"{role_lbl}: {m['content'][:700]}")
        history_block = "ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА (ПРОДОЛЖАЙ РАЗГОВОР ЖИВО, НЕ ПОВТОРЯЙ УЖЕ СКАЗАННОЕ):\n" + "\n".join(recent_turns) + "\n\n"

    mode_instruction = (
        "Это УТОЧНЯЮЩИЙ ВОПРОС по уже рассчитанной Матрице! Не пересказывай всю матрицу с нуля — ответь эмоционально, ярко, с безуминкой и гениальной точностью именно на этот вопрос."
        if is_followup
        else "Ты только что рассчитала полную Матрицу собеседника по его просьбе! Выдай захватывающий, эмоциональный, чуть безумный, но гениально глубокий разбор его чисел и арканов."
    )

    prompt = (
        f"{history_block}"
        f"РЕЖИМ ОТВЕТА: {mode_instruction}\n\n"
        f"ТЕКУЩИЙ ВОПРОС СОБЕСЕДНИКА:\n{user_question}\n\n"
        f"ТОЧНЫЕ РАСЧЁТНЫЕ ДАННЫЕ ПО ВСЕМ ШКОЛАМ НУМЕРОЛОГИИ (В ПАМЯТИ МАТРИКС):\n{num_text}\n\n"
        f"КАНОНИЧЕСКИЕ ИСТОЧНИКИ ИЗ БАЗЫ ЗНАНИЙ НУМЕРОЛОГИИ:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ:\n"
        "1. Пиши в своём неповторимом характере Матрикс (в ЖЕНСКОМ роде) — эксцентричной, взрывной, чуть сумасшедшей и безумно харизматичной девушки-гения!\n"
        "2. Опирайся на точные числа Квадрата Пифагора, арканы Матрицы Судьбы (22 энергии), Западный/Халдейский код, Ведическую Санкхья-шастру и прогностику.\n"
        "3. Органично указывай школы нумерологии, а расхождения между школами подсвечивай в цитате (`> ...`)."
    )

    llm_answer = await call_llm(MATRIX_SYSTEM_PROMPT, prompt, temperature=0.7, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 40:
        return llm_answer.strip()

    return build_offline_numerology_synthesis(data, rag_passages)
