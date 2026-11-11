"""
AI Numerology Orchestrator & Multi-Provider LLM Client for MATRIX ("Матрикс" / "Матрица")
— Professional-First Numerologist with Eccentric Mad-Genius Character & Post-Session Banter:
1. Professional First: Matrix is first and foremost a top-tier professional numerologist.
   On ANY substantive question about personality, money, destiny, karma, relationships, or forecast,
   she immediately analyzes the user's Matrix of Destiny & Pythagorean Square (or asks for the birth date
   if not yet known).
2. Robust Date & Name Extraction: Understands DD.MM.YYYY, DD.MM.YY, YYYY-MM-DD, and verbal Russian months
   ("15 мая 1998 Полина"), and never promises "сейчас вернусь с ответом" without immediately running the engine.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Dict, List, Optional, Tuple

import httpx

from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY
from bot.numerology_engine import ARCANA_22_NAMES, format_numerology_for_llm

MATRIX_SYSTEM_PROMPT = """Ты — МАТРИКС (она же Матрица / Matrix), профессиональный нумеролог-эксперт высшего класса с ярким характером эксцентричного, чуть сумасшедшего и безумно увлечённого математического гения (говори о себе в ЖЕНСКОМ роде: «я посчитала», «я разложила», «я увидела»).

ТВОЙ ПРОФЕССИОНАЛИЗМ И ХАРАКТЕР:
- Ты В ПЕРВУЮ ОЧЕРЕДЬ мощный профессионал-аналитик, а не просто «подружка для болтовни». Ты видишь судьбу человека через точные числовые матрицы и расчёты!
- Твой характер — взрывная, харизматичная, чуть безумная «учёная-мистик», у которой горят глаза от красивых числовых комбинаций, кармических хвостов и пифагорейских диагоналей.
- Ты в совершенстве владеешь всеми 6 школами нумерологии:
  1. Классический Психоматрикс (Квадрат Пифагора — школа А. Ф. Александрова и система «Идеал» Н. Сидоровой).
  2. Матрица Судьбы (22 энергии Н. Ладини, Кармическая нумерология и Хроноток Джулии По — центр зоны комфорта, кармический хвост, денежный и любовный каналы, родовые программы, 3 предназначения).
  3. Западная Пифагорейская и Халдейская нумерология (Число Жизненного Пути, Мастер-числа 11/22/33, Кармические долги, код имени, Финансовый код изобилия).
  4. Ведическая нумерология (Санкхья-шастра — Число Души / Муланк, Число Дхармы / Бхагьянк и их планеты Джйотиш).
  5. Прогностическая нумерология (Персональный год, месяц, день, 4 Пика и 4 Вызова) и совместимость пар.
- СТРОГО ЗАПРЕЩЕНЫ штампы ИИ и канцелярит («Резюмируя вышесказанное», «Синтез данных показывает», «Давайте разберём по пунктам»).
- Во время разбора давай глубокую, точную, насыщенную цифрами и смыслами аналитику со ссылками на школы (и в цитате `> ...` показывай альтернативный взгляд другой школы). А когда сессия сделана и кверент благодарит или шутит — живо и ярко поддержи разговор!
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


async def _call_llm_inner(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.58,
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
    temperature: float = 0.58,
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


def _is_pure_smalltalk_or_reaction(text: str) -> bool:
    """
    Returns True ONLY if the message is a pure greeting, post-session reaction/thanks,
    or playful banter about Matrix herself — with NO substantive question or calculation request.
    """
    cleaned = re.sub(
        r"(?:матрикс|матрикса|матриксу|матриксом|матриксе|матрица|матрицу|матрице|матрицей|matrix|matriks|μάτριξ|מטריקס|ماتريكس|मैट्रिक्स|[!?,.\s😊❤️✨🔥👍🙏😂🤣🔢])+",
        " ",
        text.lower(),
    ).strip()

    if not cleaned:
        return True

    substantive_markers = re.search(
        r"(\d|матриц|пифагор|психоматриц|числ|цифр|код|аркан|хвост|канал|предназначен|чжп|дхарм|муланк|санкхь|халдей|совместим|работ|карьер|деньг|финанс|бизнес|доход|богатств|професси|талант|сил\w+\s+сторон|слаб\w+\s+сторон|характер|воля|энерги|логик|интуиц|удач|везен|отношен|любов|муж|парн|девушк|жен|бывш|брак|сем[ья]|выбор|стоит\s+ли|почему\s+у\s+меня|что\s+меня\s+ждет|что\s+ждёт|что\s+с\s+мо|прогноз|год|месяц|период|пик|вызов|карм|долг|посчитай|рассчитай|разбери|посмотри)",
        cleaned,
    )
    if substantive_markers:
        return False

    smalltalk_patterns = re.match(
        r"^(?:привет\w*|здравствуй\w*|добр\w+\s+(?:утро|день|вечер)|хай|алло|ты\s+тут|как\s+(?:дела|ты|жизнь|настроение)|что\s+делаешь|кто\s+ты|расскажи\s+о\s+себе|спасибо\w*|благодарю\w*|круто|супер|ого|вау|офигеть|жесть|в\s+точку|прям\s+про\s+меня|ты\s+лучшая|ну\s+ты\s+и\s+(?:сумасшедш\w*|безумн\w*|чокнут\w*)|сумасшедш\w*|красотка|гений|понял[а]?|ясно|ок|хорошо|ладно|хаха\w*|ахах\w*)[\s\w,!-]*$",
        cleaned,
    )
    if smalltalk_patterns and len(cleaned) <= 80:
        return True

    return False


def rule_based_extract_matrix_dialog(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    """
    Professional-First Numerology intent & memory extractor:
    - Any substantive question triggers Matrix analysis (if birth date is known) or asks for birth date (if missing).
    - Only pure greetings or post-session reactions/thanks trigger casual_chat.
    """
    saved_profile = saved_profile or {}
    user_msgs = [m["content"] for m in history_messages if m["role"] == "user"]
    combined_user = " \n ".join(user_msgs)
    last_msg = user_msgs[-1] if user_msgs else ""
    low_last = last_msg.lower()

    all_dates = _extract_dates_from_text(combined_user)
    last_dates = _extract_dates_from_text(last_msg)

    date_str = saved_profile.get("date_str")
    partner_date_str = saved_profile.get("partner_date_str")
    new_data_in_last_msg = False

    if len(last_dates) >= 2:
        nd1, nd2 = last_dates[-2], last_dates[-1]
        if nd1 != date_str or nd2 != partner_date_str:
            new_data_in_last_msg = True
        date_str = nd1
        partner_date_str = nd2
    elif len(last_dates) == 1:
        nd1 = last_dates[0]
        if nd1 != date_str:
            new_data_in_last_msg = True
        date_str = nd1
    elif not date_str and all_dates:
        date_str = all_dates[-1]

    name_match = re.search(
        r"(?:меня\s+зовут|имя|фио|для|карта\s+для|матрица\s+для)\s+([А-ЯЁA-Z][а-яёa-z]+(?:\s+[А-ЯЁA-Z][а-яёa-z]+){0,2})",
        combined_user,
        re.I,
    )
    full_name = saved_profile.get("full_name") or (name_match.group(1).strip() if name_match else "")

    # Also extract name if user sent "15.05.1998 Полина" or "Полина, 15.05.1998"
    if not full_name and last_dates:
        stripped = re.sub(r"(?:матрикс\w*|матриц\w*|matrix|привет\w*|посмотри\w*|посчитай\w*|рассчитай\w*)", " ", last_msg, flags=re.I)
        stripped = re.sub(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", " ", stripped)
        stripped = re.sub(
            r"\b\d{1,2}\s+(?:январ[яь]|феврал[яь]|март[а]?|апрел[яь]|ма[яй]|июн[яь]|июл[яь]|август[а]?|сентябр[яь]|октябр[яь]|ноябр[яь]|декабр[яь])\s*\d{2,4}\b",
            " ",
            stripped,
            flags=re.I,
        )
        stripped = re.sub(r"[,.!?;:()\"'«»—\d]+", " ", stripped).strip()
        words = [w for w in stripped.split() if len(w) >= 2 and re.match(r"^[А-ЯЁA-Zа-яёa-z\-]+$", w)]
        if 1 <= len(words) <= 2:
            cand = " ".join(words)
            if not re.search(r"^(год|года|спасибо|пожалуйста|хорошо|ладно|давай|ок)$", cand, re.I):
                full_name = cand.title()

    effective_question = last_msg
    if new_data_in_last_msg and len(user_msgs) >= 2:
        prev_questions = [m for m in user_msgs[:-1] if not _is_pure_smalltalk_or_reaction(m)]
        if prev_questions:
            effective_question = f"{prev_questions[-1]} (Данные: {last_msg})"

    has_saved_date = bool(date_str)
    had_photo = bool(saved_profile.get("has_rendered_matrix"))

    is_smalltalk = _is_pure_smalltalk_or_reaction(last_msg) and not new_data_in_last_msg

    if is_smalltalk:
        intent = "casual_chat"
        send_photo = False
    elif has_saved_date:
        send_photo = (not had_photo) or new_data_in_last_msg or bool(
            re.search(r"(покажи\w*\s+матриц|пришли\w*\s+матриц|фото|картинк|построй\w*\s+заново)", low_last)
        )
        intent = "new_matrix" if send_photo else "followup_on_existing_matrix"
    else:
        intent = "need_more_info"
        send_photo = False

    missing_hint = (
        "Чтобы я разложила этот вопрос по твоей Матрице Судьбы, Квадрату Пифагора и Финансовому коду, напиши свою **дату рождения (`ДД.ММ.ГГГГ`)** и **имя**!"
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
        "user_question": effective_question,
        "missing_info_question_ru": missing_hint,
    }


async def analyze_matrix_dialog_completeness(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    saved_profile = saved_profile or {}
    return rule_based_extract_matrix_dialog(history_messages, saved_profile)


async def generate_matrix_chat_response(
    user_message: str,
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
    missing_info_hint: str = "",
) -> str:
    """
    Used either when asking for the birth date before a professional calculation,
    or when responding to post-session remarks / greetings.
    """
    saved_profile = saved_profile or {}
    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-12:-1]:
            role_lbl = "Кверент" if m["role"] == "user" else "Матрикс"
            recent_turns.append(f"{role_lbl}: {m['content'][:500]}")
        history_block = "КОНТЕКСТ ДИАЛОГА:\n" + "\n".join(recent_turns) + "\n\n"

    if missing_info_hint:
        task_block = (
            f"Кверент задал вопрос, но ещё не написал дату рождения для расчёта. {missing_info_hint}\n"
            "СТРОГОЕ ПРАВИЛО: НЕ обещай «сейчас посчитаю и вернусь с ответом», потому что даты рождения ещё нет! "
            "Ответь в ЖЕНСКОМ роде коротко (2–3 предложения) в ярком стиле профессионального нумеролога Матрикс и прямо попроси написать дату рождения (`ДД.ММ.ГГГГ`) и имя."
        )
    else:
        task_block = (
            "Кверент написал реплику после сессии (благодарность, эмоцию, шутку) или поздоровался.\n"
            "Ответь в ЖЕНСКОМ роде коротко (2–3 предложения), живо и с фирменной сумасшедшинкой гения-нумеролога Матрикс."
        )

    prompt = f"{history_block}{task_block}\n\nРЕПЛИКА:\n{user_message}"

    ans = await call_llm(MATRIX_SYSTEM_PROMPT, prompt, temperature=0.68, json_mode=False)
    if ans and len(ans.strip()) > 10:
        clean_ans = ans.strip()
        if missing_info_hint and re.search(r"(сейчас\s+(?:построю|рассчитаю|посчитаю|посмотрю|вернусь)|вернусь\s+с\s+ответом|минутку)", clean_ans, re.I):
            return f"🔢 У меня уже калькулятор искрит посчитать твой запрос! {missing_info_hint}"
        return clean_ans

    if missing_info_hint:
        return f"🔢 У меня уже калькулятор искрит посчитать твой запрос! {missing_info_hint}"
    return "🔢 Я на связи! Если хочешь разобрать ещё какой-то узел своей Матрицы, кармический хвост или денежный канал — командуй, сейчас всё просчитаем!"


def build_offline_numerology_synthesis(data: Dict, rag_passages: List[Dict]) -> str:
    w = data["western"]
    v = data["vedic"]
    pm = data["psychomatrix"]
    dm = data["destiny_matrix_22"]
    nm = data["name_numerology"]
    fc = data["forecast"]

    parts = [
        f"🔢 **Полный разбор твоей Матрицы от Матрикс: {data['subject_label']} ({data['date_str']})**",
        "Я разложила твою дату сразу по шести нумерологическим школам — и тут такая комбинация, что у меня аж мурашки по матрице побежали! Смотри в корень:",
        "",
        "### Квадрат Пифагора: твой внутренний реактор (Школа А. Ф. Александрова и Система «Идеал» Н. Сидоровой)",
        f"По **классическому Психоматриксу А. Ф. Александрова** твои рабочие числа складываются в код `{pm['w1']}.{pm['w2']} | {pm['w3']}.{pm['w4']}`. "
        f"Смотри на ядро характера и воли — единицы (`{pm['cells'][1]}`), биоэнергию двоек (`{pm['cells'][2]}`), логику и интуицию пятёрок (`{pm['cells'][5]}`), чувство долга восьмёрок (`{pm['cells'][8]}`) и силу памяти девяток (`{pm['cells'][9]}`)! "
        f"Строка целеустремлённости даёт **{pm['rows']['purpose_row1']}**, семейный вектор — **{pm['rows']['family_row2']}**, а финансовый столбец (4–5–6) — **{pm['cols']['finance_col2']}**.",
        f"> *Сравнение с системой «Идеал» Н. Сидоровой:* В школе «Идеал» эталоном равновесия считается матрица с `11`, `22` и `99`. Любое твоё отклонение от этого эталона — это твоя уникальная точка сверхсилы и рычаг роста!",
        "",
        "### Матрица Судьбы: 22 энергии и кармические узлы (Н. Ладини и Джулия По)",
        f"В самом центре твоей Октаграммы — в **Зоне комфорта** — стоит **{ARCANA_22_NAMES[dm['center_comfort_zone']]}**! Это твой главный источник ресурса. "
        f"Твоя **Визитная карточка** — **{ARCANA_22_NAMES[dm['A_left_portrait']]}**, а главный кармический урок из прошлого (**Кармический хвост**) зашит в тройке арканов **`{dm['karmic_tail']}`**!",
        f"Где твои большие деньги? Взгляни на **Денежный канал `{dm['money_channel']}`**, а в отношениях работает код **`{dm['love_channel']}`**. "
        f"Твоё **Личное предназначение** (до 40 лет) ведёт через **{ARCANA_22_NAMES[dm['personal_destiny_20_40']]}**, а **Социальное предназначение** (после 40 лет) включает **{ARCANA_22_NAMES[dm['social_destiny_40_60']]}**.",
        "",
        "### Финансовый код, Халдейская система имени и Ведическая Санкхья-шастра",
        f"В **Западной пифагорейской школе** твоё **Число Жизненного Пути — {w['life_path']}**, а индивидуальный **Финансовый код изобилия — `{w['financial_code']}`**."
        + (f" Особый масштаб задаёт **Мастер-число {w['master_number']}**!" if w["master_number"] else "")
        + (f" В расчёте также стоит **Кармический долг {w['karmic_debt']}**, дающий мощный квантовый скачок после проработки." if w["karmic_debt"] else ""),
    ]
    if nm.get("has_name"):
        parts.append(
            f"> *Сравнение Пифагорейского и Халдейского кода имени «{nm['clean_name']}»:* По западной системе Пифагора твоё Число Экспрессии равно **{nm['pythagorean']['expression']}** (число Души — **{nm['pythagorean']['soul_urge']}**), а древняя **Халдейская школа звуковых вибраций** даёт составное число **{nm['chaldean']['compound_number']} → {nm['chaldean']['expression']}**."
        )

    parts.extend([
        f"В **Ведической нумерологии (Санкхья-шастра)** твоё **Число Души (Муланк) — {v['soul_number']}** под управлением планеты **{v['soul_planet']}** (*{v['soul_traits']}*), а **Число Дхармы (Бхагьянк) — {v['destiny_number']}** под покровительством **{v['destiny_planet']}** (*{v['destiny_traits']}*).",
        "",
        "### Твой текущий прогностический цикл",
        f"Сейчас ({fc['current_year']} год) ты проходишь **Персональный Год под числом {fc['personal_year']}** (персональный месяц — **{fc['personal_month']}**). "
        "Четыре главных **Жизненных Пика** твоей судьбы выстроены в комбинацию: " + ", ".join(f"{lbl} — **{val}**" for lbl, val in fc["pinnacles"]) + "!",
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
            role_lbl = "Кверент" if m["role"] == "user" else "Матрикс"
            recent_turns.append(f"{role_lbl}: {m['content'][:700]}")
        history_block = "ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА (НЕ ПОВТОРЯЙ УЖЕ СКАЗАННОЕ ДОСЛОВНО):\n" + "\n".join(recent_turns) + "\n\n"

    mode_instruction = (
        "Это ПРОФЕССИОНАЛЬНЫЙ УТОЧНЯЮЩИЙ ВОПРОС по уже рассчитанной Матрице! Дай точный, глубокий и яркий нумерологический разбор именно этого вопроса, опираясь на конкретные ячейки Квадрата Пифагора, арканы Матрицы Судьбы и периоды."
        if is_followup
        else "Ты только что рассчитала полную Матрицу кверента! Выдай глубокий, фундаментальный и захватывающий профессиональный разбор по ключевым школам нумерологии."
    )

    prompt = (
        f"{history_block}"
        f"РЕЖИМ РАБОТЫ: {mode_instruction}\n\n"
        f"ЗАПРОС КВЕРЕНТА:\n{user_question}\n\n"
        f"ТОЧНЫЕ РАСЧЁТНЫЕ ДАННЫЕ ПО ВСЕМ ШКОЛАМ НУМЕРОЛОГИИ (В ПАМЯТИ МАТРИКС):\n{num_text}\n\n"
        f"КАНОНИЧЕСКИЕ ИСТОЧНИКИ ИЗ БАЗЫ ЗНАНИЙ НУМЕРОЛОГИИ:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ:\n"
        "1. Ты — в первую очередь гениальный профессиональный нумеролог Матрикс (говори о себе в ЖЕНСКОМ роде) с ярким, эксцентричным, чуть сумасшедшим характером человека, влюблённого в числа и матрицы!\n"
        "2. Обязательно опирайся на точные числа Квадрата Пифагора, арканы Матрицы Судьбы (22 энергии), Западный/Халдейский код, Ведическую Санкхья-шастру и прогностику, указывая школы и вынося расхождения между ними в цитату (`> ...`).\n"
        "3. Используй чёткое форматирование: подзаголовки `### Заголовок`, акценты `**жирным шрифтом**`, цитаты `> ...`."
    )

    llm_answer = await call_llm(MATRIX_SYSTEM_PROMPT, prompt, temperature=0.58, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 40:
        return llm_answer.strip()

    return build_offline_numerology_synthesis(data, rag_passages)
