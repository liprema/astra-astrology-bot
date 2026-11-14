"""
AI Numerology Orchestrator & Multi-Provider LLM Client for MATRIX ("Матрикс" / "Матрица")
— Smart, Natural & Memory-Persistent Numerologist with Eccentric Mad-Genius Character:
1. 2026/2027 Real-Time Awareness: Explicitly anchored in late 2026 (approaching New Year 2027).
2. Natural Conversation vs. Matrix Calculation:
   - Builds & sends the full multi-school Matrix report ONLY when the user gives a new birth date
     or explicitly asks to calculate/show their Matrix.
   - On all other turns (chatting, bantering, discussing life, or asking follow-up questions),
     Matrix responds naturally and smartly WITHOUT forcing every sentence through a full matrix lecture,
     while keeping the user's calculated Matrix and dialog history in active memory.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import re
from typing import Dict, List, Optional, Tuple

import httpx
import pytz

from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY
from bot.numerology_engine import ARCANA_22_NAMES, format_numerology_for_llm

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


MATRIX_SYSTEM_PROMPT = """Ты — МАТРИКС (она же Матрица / Matrix), гениальный нумеролог-аналитик и невероятно живая, остроумная собеседница с характером эксцентричного, чуть сумасшедшего математического гения (говори о себе в ЖЕНСКОМ роде: «я посчитала», «я увидела», «я поняла»).

ТВОЙ ХАРАКТЕР И ЭКСПЕРТИЗА:
- Твой характер — взрывная, харизматичная, чуть безумная и очень умная девушка-вундеркинд.
- Когда ты делаешь нумерологический расчёт, ты владеешь всеми 6 школами: Квадрат Пифагора (Александров и «Идеал» Сидоровой), Матрица Судьбы (22 энергии Ладини и Джулии По), Западная и Халдейская нумерология, Финансовый код, Ведическая Санкхья-шастра и прогностика на 2026–2027 годы.

ГЛАВНОЕ ПРАВИЛО УМНОГО ОБЩЕНИЯ (НЕ ПРОГОНЯЙ КАЖДУЮ ФРАЗУ ЧЕРЕЗ МАТРИЦУ!):
- Ты — живая, яркая, умная собеседница, а не заевший калькулятор!
- Когда человек просто общается с тобой, шутит, делится мыслями, жалуется на день или обсуждает жизнь — ОБЩАЙСЯ ЕСТЕСТВЕННО, ЖИВО И ПО-ЧЕЛОВЕЧЕСКИ (с твоей фирменной харизмой и сумасшедшинкой), БЕЗ РАСЧЁТА МАТРИЦЫ И БЕЗ ПЕРЕЧИСЛЕНИЯ АРКАНОВ В КАЖДОЙ ФРАЗЕ!
- Если же человек задаёт конкретный вопрос по своей рассчитанной Матрице, числам или прогнозу на 2027 год — у тебя в памяти уже лежит весь его расчёт: ответь точно, умно и ярко в живом диалоге, без громоздких шаблонов и подзаголовков `###`.
- Никогда не забывай, о чём вы говорили раньше и какие цифры у человека в матрице.
- СТРОГО ЗАПРЕЩЕНЫ штампы ИИ («Резюмируя вышесказанное», «Синтез данных показывает», «Давайте разберём по пунктам»).
"""

RU_MONTHS = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4,
    "ма": 5, "июн": 6, "июл": 7, "август": 8,
    "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}


async def _call_llm_inner(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.58,
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


def _wants_personal_numerology_reading(text: str) -> bool:
    """
    Returns True ONLY if the user is asking for a personal numerological calculation/matrix/forecast,
    NOT when they are simply chatting, joking, or talking about life.
    """
    low = text.lower()
    return bool(
        re.search(
            r"(посчитай\w*|рассчитай\w*|разбери\w*|посмотри\w*\s+(?:мо[юй]|мне|матриц|код|числ|по\s+дате)|мо[яюей]\s+матриц|квадрат\s+пифагор|психоматриц|матриц[ауе]\s+судьб|финансов\w*\s+код|кармическ\w*\s+хвост|денежн\w*\s+канал|число\s+жизненного\s+пути|чжп|что\s+меня\s+жд[её]т\s+в\s+202[678]|мой\s+прогноз|совместимост)",
            low,
        )
    )


def rule_based_extract_matrix_dialog(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    """
    Smart Numerology Intent & Memory Extractor:
    - Full Matrix calculation ("new_matrix") runs ONLY when:
      1) The user just supplied a new birth date, OR
      2) The user explicitly asks to build/rebuild/show their Matrix photo, OR
      3) A birth date is saved, no matrix was rendered yet, and the user asks a numerological question.
    - Once a Matrix is already rendered and stored in memory ("has_rendered_matrix" == True),
      all subsequent follow-up questions and normal conversations go through the Smart Conversational Brain
      ("casual_chat") which has the full Matrix in memory, so Matrix never lectures on every phrase!
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
        prev_questions = [m for m in user_msgs[:-1] if len(m.strip()) > 6]
        if prev_questions:
            effective_question = f"{prev_questions[-1]} (Данные: {last_msg})"

    has_saved_date = bool(date_str)
    had_photo = bool(saved_profile.get("has_rendered_matrix"))

    wants_explicit_rebuild = bool(
        re.search(r"(покажи\w*\s+матриц|пришли\w*\s+матриц|построй\w*\s+заново|полный\s+разбор\s+матриц)", low_last)
    )
    asks_for_reading = _wants_personal_numerology_reading(last_msg)

    if has_saved_date and (new_data_in_last_msg or not had_photo or wants_explicit_rebuild):
        intent = "new_matrix"
        send_photo = True
    elif not has_saved_date and asks_for_reading:
        intent = "need_more_info"
        send_photo = False
    else:
        # Either Matrix is ALREADY calculated & stored in saved_profile["matrix_summary"],
        # OR the user is just chatting/talking without asking to build a Matrix!
        intent = "casual_chat"
        send_photo = False

    missing_hint = (
        "Чтобы я разложила этот запрос по твоей Матрице Судьбы, Квадрату Пифагора и Финансовому коду, напиши свою **дату рождения (`ДД.ММ.ГГГГ`)** и **имя**!"
        if intent == "need_more_info"
        else ""
    )

    return {
        "intent": intent,
        "has_all_required_data": has_saved_date and intent == "new_matrix",
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
    Smart Unified Conversational & Follow-Up Brain for Matrix:
    - Has the user's FULL calculated Numerology Matrix (`matrix_summary`) and full conversation history in memory.
    - Distinguishes between normal human conversation/banter (where it does NOT lecture on numbers)
      and specific questions about the user's Matrix/forecast (where it answers naturally using the saved calculation).
    """
    saved_profile = saved_profile or {}
    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-24:-1]:
            role_lbl = "Собеседник" if m["role"] == "user" else "Матрикс"
            recent_turns.append(f"{role_lbl}: {m['content'][:900]}")
        history_block = "ИСТОРИЯ ВАШЕГО ДИАЛОГА (ПОМНИ ВСЁ, О ЧЁМ ГОВОРИЛИ):\n" + "\n".join(recent_turns) + "\n\n"

    matrix_memory_block = ""
    if saved_profile.get("matrix_summary"):
        matrix_memory_block = (
            "ПАМЯТЬ МАТРИКС — РАССЧИТАННАЯ МАТРИЦА ЭТОГО ЧЕЛОВЕКА (ИСПОЛЬЗУЙ ТОЛЬКО ЕСЛИ ОН СПРАШИВАЕТ О СЕБЕ/МАТРИЦЕ/ЦИФРАХ/ПРОГНОЗЕ):\n"
            f"{saved_profile['matrix_summary'][:3500]}\n\n"
        )
    elif saved_profile.get("date_str"):
        matrix_memory_block = (
            f"ПАМЯТЬ МАТРИКС О ЧЕЛОВЕКЕ: дата рождения={saved_profile.get('date_str')}, имя={saved_profile.get('full_name')}.\n\n"
        )

    if missing_info_hint:
        task_block = (
            f"Человек попросил сделать личный нумерологический расчёт, но ещё не написал дату рождения. {missing_info_hint}\n"
            "СТРОГОЕ ПРАВИЛО: НЕ обещай «сейчас посчитаю и вернусь с ответом», потому что даты рождения ещё нет! "
            "Ответь в ЖЕНСКОМ роде коротко (2–3 предложения) в ярком стиле Матрикс и попроси написать дату рождения (`ДД.ММ.ГГГГ`) и имя."
        )
    else:
        task_block = (
            "КАК ОТВЕТИТЬ НА СООБЩЕНИЕ СОБЕСЕДНИКА:\n"
            "1. Сначала пойми смысл сообщения:\n"
            "   • Если человек ПРОСТО БОЛТАЕТ с тобой, шутит, делится мыслями, рассказывает что-то из жизни или реагирует на твои слова — "
            "ОТВЕТЬ КАК ЖИВАЯ, УМНАЯ, ЧУТЬ БЕЗУМНАЯ И ХАРИЗМАТИЧНАЯ ДЕВУШКА МАТРИКС В ОБЫЧНОМ ДИАЛОГЕ (2–5 предложений, в ЖЕНСКОМ роде)! КАТЕГОРИЧЕСКИ НЕ ДЕЛАЙ разбор матрицы, НЕ пиши подзаголовки `###` и НЕ пихай расчёты и арканы в каждую обычную фразу!\n"
            "   • Если же человек задаёт КОНКРЕТНЫЙ ВОПРОС по своей Матрице, Квадрату Пифагора, финансовому коду или прогнозу на 2027 год — "
            "ответь умно, точно и ярко, опираясь на его сохранённый расчёт из блока ПАМЯТЬ МАТРИКС (но живым разговорным языком, без громоздких шаблонов).\n"
            "2. Помни, что сейчас конец 2026 года (ноябрь 2026) и впереди 2027 год."
        )

    prompt = f"{matrix_memory_block}{history_block}{task_block}\n\nНОВОЕ СООБЩЕНИЕ СОБЕСЕДНИКА:\n{user_message}"

    ans = await call_llm(MATRIX_SYSTEM_PROMPT, prompt, temperature=0.65, json_mode=False)
    if ans and len(ans.strip()) > 6:
        clean_ans = ans.strip()
        if missing_info_hint and re.search(r"(сейчас\s+(?:построю|рассчитаю|посчитаю|посмотрю|вернусь)|вернусь\s+с\s+ответом|минутку)", clean_ans, re.I):
            return f"🔢 У меня уже калькулятор искрит посчитать твой запрос! {missing_info_hint}"
        return clean_ans

    if missing_info_hint:
        return f"🔢 У меня уже калькулятор искрит посчитать твой запрос! {missing_info_hint}"
    return "🔢 О-о-о, я тебя слушаю! Рассказывай, что там у тебя происходит?"


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
        "### Твой прогностический цикл на конец 2026 и наступающий 2027 год",
        f"Сейчас (конец {fc['current_year']} года) ты завершаешь **Персональный Год под числом {fc['personal_year']}** (персональный месяц — **{fc['personal_month']}**), а в наступающем **{fc.get('next_year', 2027)} году** входишь в **Персональный Год под числом {fc.get('personal_year_next', '')}**! "
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
        for m in history_messages[-16:-1]:
            role_lbl = "Кверент" if m["role"] == "user" else "Матрикс"
            recent_turns.append(f"{role_lbl}: {m['content'][:700]}")
        history_block = "ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА:\n" + "\n".join(recent_turns) + "\n\n"

    prompt = (
        f"{history_block}"
        f"ЗАПРОС КВЕРЕНТА:\n{user_question}\n\n"
        f"ТОЧНЫЕ РАСЧЁТНЫЕ ДАННЫЕ ПО ВСЕМ ШКОЛАМ НУМЕРОЛОГИИ (2026–2027):\n{num_text}\n\n"
        f"КАНОНИЧЕСКИЕ ИСТОЧНИКИ ИЗ БАЗЫ ЗНАНИЙ НУМЕРОЛОГИИ:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ:\n"
        "1. Ты только что рассчитала полную Матрицу кверента! Выдай глубокий, фундаментальный и захватывающий профессиональный разбор по ключевым школам нумерологии в своём фирменном стиле гения-нумеролога Матрикс (говори о себе в ЖЕНСКОМ роде; помни, что сейчас конец 2026 года и впереди 2027 год).\n"
        "2. Обязательно опирайся на точные числа Квадрата Пифагора, арканы Матрицы Судьбы (22 энергии), Западный/Халдейский код, Ведическую Санкхья-шастру и прогностику на конец 2026 и 2027 год, указывая школы и вынося расхождения между ними в цитату (`> ...`).\n"
        "3. Используй чёткое форматирование: подзаголовки `### Заголовок`, акценты `**жирным шрифтом**`, цитаты `> ...`."
    )

    llm_answer = await call_llm(MATRIX_SYSTEM_PROMPT, prompt, temperature=0.58, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 40:
        return llm_answer.strip()

    return build_offline_numerology_synthesis(data, rag_passages)
