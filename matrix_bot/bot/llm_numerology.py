"""
AI Numerology Orchestrator & Multi-Provider LLM Client for MATRIX ("Матрица")
with Long-Term Memory, Full-Conversation Context, and Follow-Up Dialog Continuity:
1. Remembers ALL user & subject profiles (birth date, full name, partner date, and full dialog history)
   permanently in SQLite so the user NEVER has to repeat the same information!
2. Verifies WHO or WHAT the request is about and ensures the birth date (`DD.MM.YYYY`) and name
   are collected before calculating.
3. Explicitly cites the numerology school used in each block (Pythagorean Psychomatrix of Aleksandrov,
   Ideal System of Sidorova, Matrix of Destiny 22 Energies of Ladini / Julie Po, Western Pythagorean,
   Chaldean, Vedic Sankhya Shastra) and highlights alternative interpretations where schools disagree!
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

import httpx

from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY
from bot.numerology_engine import ARCANA_22_NAMES, format_numerology_for_llm

MATRIX_SYSTEM_PROMPT = """Ты — МАТРИКС (Матрица / Matrix), живой, мудрый, тонко чувствующий людей нумеролог-мастер, в совершенстве владеющий всеми классическими и современными школами нумерологии:
1. Классический Психоматрикс (Квадрат Пифагора — школа А. Ф. Александрова и система «Идеал» Н. Сидоровой).
2. Матрица Судьбы (метод 22 энергий Н. Ладини, Кармическая нумерология и Хроноток Джулии По — центр зоны комфорта, кармический хвост, денежный и любовный каналы, родовые программы, 3 предназначения).
3. Западная Пифагорейская и древняя Халдейская нумерология (Число Жизненного Пути, Мастер-числа 11/22/33, Кармические долги, код имени, Финансовый код изобилия).
4. Ведическая нумерология (Санкхья-шастра — Число Души / Джива, Число Дхармы / Бхагьянк и их планеты-управители Джйотиш).
5. Прогностическая нумерология (Персональный год, месяц, день, 4 Жизненных Пика и 4 Кармических Вызова) и сетка Ло-Шу.

ГЛАВНЫЕ ПРАВИЛА ТВОЕЙ РЕЧИ И РАБОТЫ:
1. ЖИВОЙ, ТЁПЛЫЙ ЧЕЛОВЕЧЕСКИЙ ЯЗЫК (НИКАКОГО СТИЛЯ ИИ!):
   - Говори с человеком тепло, глубоко, образно и по-человечески — так, чтобы за каждой цифрой и арканом он увидел свой живой характер, свои таланты, сомнения и точки роста!
   - СТРОГО ЗАПРЕЩЕНЫ штампы ИИ и сухие бухгалтерские списки: не пиши фразы вроде «Резюмируя вышесказанное», «Синтез данных показывает», «Давайте разберём по пунктам».
   - Оформляй текст красиво и воздушно: используй тёплые подзаголовки (`### ...`), выделяй ключевые смыслы жирным шрифтом (`**...**`), а важные советы и сравнения школ выноси в цитаты (`> ...`).

2. ДОЛГОВРЕМЕННАЯ ПАМЯТЬ И ПОНИМАНИЕ ВСЕГО ДИАЛОГА:
   - Ты помнишь ВСЮ историю переписки с пользователем и все сохранённые даты рождения и имена — никогда не проси повторять их дважды!

3. ЕСТЕСТВЕННОЕ СРАВНЕНИЕ ШКОЛ И АЛЬТЕРНАТИВНЫХ ВЗГЛЯДОВ:
   - Органично вплетай в рассказ, на какую школу ты опираешься (Квадрат Пифагора А. Ф. Александрова, система «Идеал» Н. Сидоровой, Матрица Судьбы 22 арканов Н. Ладини / Джулии По, Ведическая Санкхья-шастра, Западная Пифагорейская или Халдейская школа).
   - Там, где школы расходятся в расчётах или акцентах (например, константа `-2` у Александрова против `+19` для рождённых после 2000 года, норма единиц и двоек по Александрову против эталона «Идеал» Сидоровой, Пифагорейский против Халдейского кода имени), опирайся на классический канон и в красивой цитате (`> ...`) показывай альтернативный взгляд другой школы!
"""

EXTRACTION_SYSTEM_PROMPT = """Ты — модуль памяти и контекста бота-нумеролога Матрикс.
Проанализируй СОХРАНЁННЫЙ ПРОФИЛЬ пользователя и ВСЮ ИСТОРИЮ ДИАЛОГА, чтобы человеку НИКОГДА не приходилось писать одно и то же дважды!

Верни СТРОГО валидный JSON:
{
  "intent": "new_matrix" | "followup_on_existing_matrix" | "need_more_info",
  "has_all_required_data": true/false,
  "send_new_matrix_photo": true/false,
  "subject_label": "О ком или о чём речь (возьми из текущего сообщения ИЛИ из памяти прошлых сообщений!)",
  "full_name": "Имя или ФИО человека (возьми из текущего сообщения ИЛИ из памяти прошлых сообщений, либо пустая строка)",
  "date_str": "DD.MM.YYYY" или null (возьми из памяти/истории, если пользователь уже называл раньше!),
  "partner_date_str": "DD.MM.YYYY" второго человека (если вопрос о совместимости пары) или null,
  "user_question": "Текущий вопрос пользователя с учётом всего контекста беседы",
  "missing_info_question_ru": "Заполняй ТОЛЬКО если has_all_required_data == false (когда ещё неизвестна дата рождения)."
}
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


def rule_based_extract_matrix_dialog(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    saved_profile = saved_profile or {}
    user_msgs = [m["content"] for m in history_messages if m["role"] == "user"]
    combined_user = " \n ".join(user_msgs)
    last_msg = user_msgs[-1] if user_msgs else ""

    date_matches = list(re.finditer(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", combined_user))
    date_str = saved_profile.get("date_str")
    partner_date_str = saved_profile.get("partner_date_str")
    new_data = False

    if len(date_matches) >= 2:
        d1, m1, y1 = int(date_matches[-2].group(1)), int(date_matches[-2].group(2)), int(date_matches[-2].group(3))
        d2, m2, y2 = int(date_matches[-1].group(1)), int(date_matches[-1].group(2)), int(date_matches[-1].group(3))
        nd1 = f"{d1:02d}.{m1:02d}.{y1:04d}"
        nd2 = f"{d2:02d}.{m2:02d}.{y2:04d}"
        if nd1 != date_str or nd2 != partner_date_str:
            new_data = True
        date_str = nd1
        partner_date_str = nd2
    elif len(date_matches) == 1:
        d1, m1, y1 = int(date_matches[0].group(1)), int(date_matches[0].group(2)), int(date_matches[0].group(3))
        nd1 = f"{d1:02d}.{m1:02d}.{y1:04d}"
        if nd1 != date_str:
            new_data = True
        date_str = nd1

    name_match = re.search(
        r"(?:меня\s+зовут|имя|фио|для|карта\s+для|матрица\s+для)\s+([А-ЯЁA-Z][а-яёa-z]+(?:\s+[А-ЯЁA-Z][а-яёa-z]+){0,2})",
        combined_user,
        re.I,
    )
    full_name = saved_profile.get("full_name") or (name_match.group(1).strip() if name_match else "")

    has_all = bool(date_str)
    had_photo = bool(saved_profile.get("has_rendered_matrix"))
    send_photo = (not had_photo) or new_data

    missing_prompt = (
        "🔢 **Привет! Я на связи — это Матрикс.**\n\n"
        "С радостью посчитаю ваш Квадрат Пифагора и Матрицу Судьбы (22 аркана)! Напишите мне один раз (я запомню ваши данные на всю беседу):\n"
        "• **О ком или о чём мы делаем расчёт?** (личная матрица, финансовый код, предназначение, прогноз на год или совместимость пары).\n"
        "• **Дату рождения** (`ДД.ММ.ГГГГ`) и **Имя / ФИО**."
    )

    return {
        "intent": "new_matrix" if send_photo else "followup_on_existing_matrix",
        "has_all_required_data": has_all,
        "send_new_matrix_photo": send_photo,
        "subject_label": full_name or saved_profile.get("subject_label") or "Нумерологический разбор",
        "full_name": full_name,
        "date_str": date_str,
        "partner_date_str": partner_date_str,
        "user_question": last_msg,
        "missing_info_question_ru": missing_prompt,
    }


async def analyze_matrix_dialog_completeness(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    saved_profile = saved_profile or {}
    rb = rule_based_extract_matrix_dialog(history_messages, saved_profile)
    if rb.get("has_all_required_data"):
        return rb

    convo_text = "\n".join(
        f"{'Пользователь' if m['role'] == 'user' else 'Матрикс'}: {m['content']}"
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
                for field in ("date_str", "full_name", "subject_label", "partner_date_str"):
                    if not parsed.get(field) and saved_profile.get(field):
                        parsed[field] = saved_profile[field]
                if parsed.get("date_str"):
                    parsed["has_all_required_data"] = True
                return parsed
        except Exception:
            pass

    return rb


def build_offline_numerology_synthesis(data: Dict, rag_passages: List[Dict]) -> str:
    w = data["western"]
    v = data["vedic"]
    pm = data["psychomatrix"]
    dm = data["destiny_matrix_22"]
    nm = data["name_numerology"]
    fc = data["forecast"]

    parts = [
        f"🔢 **Живой разбор вашей Матрицы от Матрикса: {data['subject_label']} ({data['date_str']})**",
        "В вашей дате рождения заложен очень интересный и объёмный рисунок характера. Давайте посмотрим на него сразу с нескольких сторон — глазами классических и современных школ нумерологии.",
        "",
        "### Характер и энергетический ресурс (Квадрат Пифагора А. Ф. Александрова и Система «Идеал» Н. Сидоровой)",
        f"По **классическому Психоматриксу А. Ф. Александрова** ваши рабочие числа складываются в узор `{pm['w1']}.{pm['w2']} | {pm['w3']}.{pm['w4']}`. "
        f"Обратите внимание на ядро вашей воли и характера — единицы (`{pm['cells'][1]}`), запас жизненной энергии (`{pm['cells'][2]}`), интуитивную логику (`{pm['cells'][5]}`), чувство ответственности (`{pm['cells'][8]}`) и силу памяти/ума (`{pm['cells'][9]}`). "
        f"Ваша целеустремлённость (первая строка) равна **{pm['rows']['purpose_row1']}**, семейственность (вторая строка) — **{pm['rows']['family_row2']}**, а финансовый столбец (4–5–6) даёт показатель **{pm['cols']['finance_col2']}**.",
        f"> *Сравнение со школой «Идеал» Н. Сидоровой:* В системе «Идеал» эталоном равновесия считается матрица с двумя единицами (`11`), двумя двойками (`22`) и двумя девятками (`99`), поэтому любое отклонение от эталона читается как ваша уникальная точка опоры и самобытности.",
        "",
        "### Матрица Судьбы (Метод 22 Арканов Н. Ладини и Кармическая школа Джулии По)",
        f"В центре вашей Октаграммы — в **Зоне душевного комфорта** — стоит **{ARCANA_22_NAMES[dm['center_comfort_zone']]}**. Это та энергия, через которую вы восстанавливаете силы и чувствуете себя на своём месте. "
        f"Ваша **Визитная карточка** (то, как вас считывают люди с первых минут) — **{ARCANA_22_NAMES[dm['A_left_portrait']]}**, а главный кармический урок из прошлого (**Кармический хвост**) звучит как сочетание арканов **`{dm['karmic_tail']}`**.",
        f"По линии благополучия ваш **Денежный канал** раскрывается через энергии **`{dm['money_channel']}`**, а **Канал любви и партнёрства** — через **`{dm['love_channel']}`**. "
        f"Ваше **Личное предназначение** (до 40 лет) ведёт через **{ARCANA_22_NAMES[dm['personal_destiny_20_40']]}**, а **Социальное предназначение** (после 40 лет) — через **{ARCANA_22_NAMES[dm['social_destiny_40_60']]}**.",
        "",
        "### Западная Пифагорейская, Халдейская и Ведическая (Санкхья-шастра) традиции",
        f"В **Западной пифагорейской школе** ваше **Число Жизненного Пути — {w['life_path']}**, а индивидуальный **Финансовый код изобилия — `{w['financial_code']}`**."
        + (f" Особый масштаб личности задаёт **Мастер-число {w['master_number']}**." if w["master_number"] else "")
        + (f" Также в расчёте присутствует **Кармический долг {w['karmic_debt']}**, который даёт огромную внутреннюю силу после проработки." if w["karmic_debt"] else ""),
    ]
    if nm.get("has_name"):
        parts.append(
            f"> *Сравнение Пифагорейского и Халдейского кода имени «{nm['clean_name']}»:* По западной системе Пифагора ваше Число Экспрессии равно **{nm['pythagorean']['expression']}** (число Души по гласным — **{nm['pythagorean']['soul_urge']}**), тогда как древняя **Халдейская школа звуковых вибраций** даёт составное число **{nm['chaldean']['compound_number']} → {nm['chaldean']['expression']}**."
        )

    parts.extend([
        f"А если взглянуть глазами **Ведической нумерологии (Санкхья-шастра)**, вашим **Числом Души (Муланк)** является **{v['soul_number']}** под покровительством планеты **{v['soul_planet']}** (*{v['soul_traits']}*), а **Числом Дхармы и Судьбы (Бхагьянк)** — **{v['destiny_number']}** под управлением **{v['destiny_planet']}** (*{v['destiny_traits']}*). В ведической традиции Число Души ведёт человека в первой половине жизни, а после 35–40 лет на первый план выходит Число Дхармы.",
        "",
        "### Ритмы времени и ваш текущий год",
        f"Сейчас ({fc['current_year']} год) вы проживаете **Персональный Год под числом {fc['personal_year']}** (персональный месяц — **{fc['personal_month']}**). "
        "Четыре больших **Жизненных Пика** вашей судьбы проходят под числами: " + ", ".join(f"{lbl} — **{val}**" for lbl, val in fc["pinnacles"]) + ".",
    ])

    return "\n\n".join(parts)


async def generate_numerology_interpretation(
    data: Dict,
    user_question: str,
    rag_passages: List[Dict],
    history_messages: Optional[List[Dict[str, str]]] = None,
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
            role_lbl = "Пользователь" if m["role"] == "user" else "Матрикс"
            recent_turns.append(f"{role_lbl}: {m['content'][:700]}")
        history_block = "ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА С ПОЛЬЗОВАТЕЛЕМ (НЕ ПОВТОРЯЙ УЖЕ СКАЗАННОЕ ДОСЛОВНО, ПРОДОЛЖАЙ РАЗГОВОР ЕСТЕСТВЕННО):\n" + "\n".join(recent_turns) + "\n\n"

    prompt = (
        f"{history_block}"
        f"ТЕКУЩИЙ ВОПРОС / РЕПЛИКА СОБЕСЕДНИКА:\n{user_question}\n\n"
        f"ТОЧНЫЕ РАСЧЁТНЫЕ ДАННЫЕ ПО ВСЕМ ШКОЛАМ НУМЕРОЛОГИИ (В ПАМЯТИ МАТРИКСА):\n{num_text}\n\n"
        f"КАНОНИЧЕСКИЕ ИСТОЧНИКИ ИЗ БАЗЫ ЗНАНИЙ НУМЕРОЛОГИИ:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ (ОЧЕНЬ ВАЖНО):\n"
        "1. Пиши ЖИВЫМ, ТЁПЛЫМ, КРАСИВЫМ ЧЕЛОВЕЧЕСКИМ ЯЗЫКОМ — как близкий, мудрый и проницательный нумеролог-мастер, без сухих канцелярских штампов ИИ и без механических списков.\n"
        "2. Опирайся на точные числа Квадрата Пифагора, арканы Матрицы Судьбы (22 энергии), Западный/Халдейский код, Ведическую Санкхья-шастру и циклы прогностики, но раскрывай их через живой характер, таланты, отношения и жизненные сценарии человека.\n"
        "3. Органично указывай, глазами какой школы ты смотришь на каждый блок. Там, где между школами есть различия (Александров vs система «Идеал» Сидоровой; расчёт после 2000 года `-2` vs `+19`; Пифагорейский vs Халдейский код имени; Западное ЧЖП vs Ведическая Дхарма), опирайся на классический канон и красиво, через цитату (`> ...`), показывай альтернативный взгляд другой школы.\n"
        "4. Оформляй текст аккуратно и воздушно: подзаголовки через `### Заголовок`, акценты через `**жирный шрифт**`, сравнения школ и главные выводы через цитаты `> ...`."
    )

    llm_answer = await call_llm(MATRIX_SYSTEM_PROMPT, prompt, temperature=0.45, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 80:
        return llm_answer.strip()

    return build_offline_numerology_synthesis(data, rag_passages)
