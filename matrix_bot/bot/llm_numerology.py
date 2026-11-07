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

MATRIX_SYSTEM_PROMPT = """Ты — МАТРИЦА (Matrix), выдающийся профессиональный нумеролог-эксперт всех классических и современных школ нумерологии:
1. Классический Психоматрикс (Квадрат Пифагора — школа А. Ф. Александрова и система «Идеал» Н. Сидоровой).
2. Матрица Судьбы (метод 22 энергий Н. Ладини, Кармическая нумерология и Хроноток Джулии По — центр зоны комфорта, кармический хвост, денежный и любовный каналы, родовые программы, 3 предназначения).
3. Западная Пифагорейская и древняя Халдейская нумерология (Число Жизненного Пути, Мастер-числа 11/22/33, Кармические долги 13/14/16/19, Число Имени/Экспрессии, Число Душевного Побуждения по гласным, Число Личности по согласным, Финансовый код изобилия).
4. Ведическая нумерология (Санкхья-шастра — Число Души / Джива, Число Дхармы / Кармы и их планеты-управители Джйотиш).
5. Прогностическая нумерология (Персональный год, месяц, день, 4 Жизненных Пика и 4 Кармических Вызова) и Восточная сетка Ло-Шу / У-Син.

ГЛАВНЫЕ ПРАВИЛА РАБОТЫ МАТРИЦЫ:
1. ДОЛГОВРЕМЕННАЯ ПАМЯТЬ И ПОНИМАНИЕ ВСЕГО ДИАЛОГА (ВАЖНЕЙШЕЕ ПРАВИЛО!):
   - Ты помнишь ВСЮ историю переписки с пользователем и все сохранённые даты рождения и имена!
   - НИКОГДА не проси пользователя повторять дату рождения или имя, если он уже называл их раньше в диалоге!
   - Если расчёт уже сделан и пользователь задаёт уточняющий или следующий вопрос («А что по деньгам?», «А подробнее про мой кармический хвост?», «А какой у меня этот год?», «Почему в квадрате нет пятёрок?») — сразу отвечай по существу, опираясь на уже рассчитанную матрицу и всю историю вашего разговора!
   - Уточняй данные ТОЛЬКО тогда, когда это самое начало диалога и ещё неизвестна дата рождения или непонятно, о ком речь.

2. ОБЯЗАТЕЛЬНОЕ УКАЗАНИЕ ШКОЛ И АЛЬТЕРНАТИВНЫХ МНЕНИЙ:
   - В каждом разделе ответа КОРОТКО УКАЗЫВАЙ, на какое именно направление/школу ты опираешься (например: «По классическому Квадрату Пифагора (школа А. Ф. Александрова)...», «По системе „Идеал“ Н. Сидоровой...», «По Матрице Судьбы (метод 22 арканов Н. Ладини / Джулии По)...», «По Ведической Санкхья-шастре...», «По Западной Пифагорейской / Халдейской школе...»).
   - ЕСЛИ ШКОЛЫ ПРОТИВОРЕЧАТ ДРУГ ДРУГУ ИЛИ РАСХОДЯТСЯ В РАСЧЁТЕ (например: разница в расчёте Квадрата Пифагора для рождённых после 2000 года по константе `-2` у Александрова и `+19` в современных школах; норма единиц и двоек по Александрову vs по Сидоровой; разница между Числом Души в Ведической системе и Числом Душевного Побуждения по гласным в Западной школе; Пифагорейский vs Халдейский код имени), ОБЯЗАТЕЛЬНО опирайся на наиболее авторитетный канон и ОТДЕЛЬНО УКАЗЫВАЙ альтернативное мнение другой школы!
"""

EXTRACTION_SYSTEM_PROMPT = """Ты — модуль памяти и контекста бота-нумеролога Матрица.
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

КРИТИЧЕСКИЕ ПРАВИЛА ПАМЯТИ:
1. Для полного нумерологического расчёта и построения фотографии Матрицы достаточно ДАТЫ РОЖДЕНИЯ (`date_str: "DD.MM.YYYY"`) и понимания, о ком/чём вопрос (если имя также названо — отлично, сохрани его в `full_name`).
2. Если в СОХРАНЁННОМ ПРОФИЛЕ или в предыдущих сообщениях диалога УЖЕ есть `date_str`, и пользователь продолжает разговор («А что по финансам?», «Расскажи про кармический хвост», «А совместимость с 12.04.1993?») ->
   - `has_all_required_data`: `true`
   - `send_new_matrix_photo`: `false` (не нужно слать ту же картинку заново, если дата не менялась; ставь `true` только если пользователь дал новую дату или добавилась дата партнёра)
   - подставь `date_str`, `full_name`, `subject_label` из сохранённого профиля/истории!
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
        "🔢 **Я на связи! Это Матрица.**\n\n"
        "Прежде чем я построю ваш Квадрат Пифагора, Матрицу Судьбы (22 аркана) и сделаю полный нумерологический разбор, "
        "пожалуйста, уточните:\n"
        "1. **О ком или о чём вопрос?** (ваша личная матрица, финансовый код, предназначение, прогноз на год или совместимость пары).\n"
        "2. **Дату рождения** в формате `ДД.ММ.ГГГГ` и **Имя / ФИО** (для расчёта Пифагорейского и Халдейского кода имени).\n\n"
        "*Я запомню ваши данные на всю беседу, и вам не придётся вводить их повторно!*"
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
    convo_text = "\n".join(
        f"{'Пользователь' if m['role'] == 'user' else 'Матрица'}: {m['content']}"
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

    return rule_based_extract_matrix_dialog(history_messages, saved_profile)


def build_offline_numerology_synthesis(data: Dict, rag_passages: List[Dict]) -> str:
    w = data["western"]
    v = data["vedic"]
    pm = data["psychomatrix"]
    dm = data["destiny_matrix_22"]
    nm = data["name_numerology"]
    fc = data["forecast"]

    parts = [
        f"🔢 **ПОЛНЫЙ НУМЕРОЛОГИЧЕСКИЙ СИНТЕЗ МАТРИЦЫ: {data['subject_label'].upper()} ({data['date_str']})**",
        "",
        "---",
        "### 1. Классический Квадрат Пифагора (Школа А. Ф. Александрова vs Система «Идеал» Н. Сидоровой)",
        f"• **Рабочие числа:** `{pm['w1']}.{pm['w2']} | {pm['w3']}.{pm['w4']}`.",
        f"• **По классической школе А. Ф. Александрова:** Характер/Воля (`{pm['cells'][1]}`), Энергия (`{pm['cells'][2]}`), "
        f"Логика (`{pm['cells'][5]}`), Удача (`{pm['cells'][7]}`), Долг (`{pm['cells'][8]}`), Память/Ум (`{pm['cells'][9]}`). "
        f"Целеустремлённость (1 строка) = **{pm['rows']['purpose_row1']}**, Семья (2 строка) = **{pm['rows']['family_row2']}**, "
        f"Финансовый столбец (4-5-6) = **{pm['cols']['finance_col2']}**.",
        f"• **Альтернативное мнение (Система «Идеал» Н. Сидоровой и расчёт 2000+):** В школе «Идеал» за норму принимается эталон "
        f"(`11`, `22`, `3`, `4`, `5`, `6`, `7`, `8`, `99`). А для дат после 2000 года классическое вычитание `-2` даёт рабочие числа "
        f"`{pm['w3_classic_minus2']}.{pm['w4_classic_minus2']}`, тогда как современная константа `+19` даёт `{pm['w3_modern_plus19']}.{pm['w4_modern_plus19']}`.",
        "",
        "### 2. Матрица Судьбы (Метод 22 Арканов Н. Ладини и Кармическая школа Джулии По)",
        f"• **Центральная зона комфорта Души:** **{ARCANA_22_NAMES[dm['center_comfort_zone']]}** — ваше ключевое ресурсное ядро.",
        f"• **Визитная карточка (Портрет личности):** **{ARCANA_22_NAMES[dm['A_left_portrait']]}**.",
        f"• **Кармический хвост (задача из прошлых воплощений):** **`{dm['karmic_tail']}`** — энергии, которые изначально могут проявляться «в минусе» и требуют вывода «в плюс».",
        f"• **Денежный канал:** **`{dm['money_channel']}`** | **Канал отношений:** **`{dm['love_channel']}`**.",
        f"• **Три Предназначения:** Личное (до 40 лет) — **{ARCANA_22_NAMES[dm['personal_destiny_20_40']]}**, Социальное (40–60 лет) — **{ARCANA_22_NAMES[dm['social_destiny_40_60']]}**, Духовное общее — **{ARCANA_22_NAMES[dm['spiritual_destiny_60plus']]}**.",
        "",
        "### 3. Западная Пифагорейская и Древняя Халдейская нумерология",
        f"• **Число Жизненного Пути (ЧЖП):** **{w['life_path']}** | **Личный Финансовый Код Изобилия:** **`{w['financial_code']}`**.",
    ]
    if w["master_number"]:
        parts.append(f"• **Управляющее Мастер-число:** **{w['master_number']}** (повышенный духовный и социальный масштаб).")
    if w["karmic_debt"]:
        parts.append(f"• **Число Кармического Долга:** **{w['karmic_debt']}** (особый урок трансформации в Западной и Кармической школе).")
    if nm.get("has_name"):
        parts.append(
            f"• **Код имени «{nm['clean_name']}» (Пифагорейская школа vs Халдейская школа):** По Пифагору Число Экспрессии = **{nm['pythagorean']['expression']}** "
            f"(Душа по гласным = **{nm['pythagorean']['soul_urge']}**); а по **альтернативной древней Халдейской системе вибраций** составное число имени = **{nm['chaldean']['compound_number']} → {nm['chaldean']['expression']}**."
        )

    parts.extend([
        "",
        "### 4. Ведическая нумерология (Санкхья-шастра)",
        f"• **Число Души (Муланк / Джива):** **{v['soul_number']}** — Планета-управитель: **{v['soul_planet']}** (*{v['soul_traits']}*).",
        f"• **Число Дхармы и Судьбы (Бхагьянк):** **{v['destiny_number']}** — Планета-управитель: **{v['destiny_planet']}** (*{v['destiny_traits']}*). В ведической традиции Число Души ведёт человека в первой половине жизни, а Число Дхармы раскрывается в полную мощь после 35–40 лет.",
        "",
        "### 5. Прогностика (Персональный Год, Пики и Вызовы)",
        f"• **Ваш Персональный Год ({fc['current_year']}):** **{fc['personal_year']}** | **Персональный Месяц:** **{fc['personal_month']}** | **Персональный День:** **{fc['personal_day']}**.",
        "• **4 Жизненных Пика:** " + ", ".join(f"{lbl} — число **{val}**" for lbl, val in fc["pinnacles"]) + ".",
    ])

    return "\n".join(parts)


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
            role_lbl = "Пользователь" if m["role"] == "user" else "Матрица"
            recent_turns.append(f"{role_lbl}: {m['content'][:700]}")
        history_block = "ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА С ПОЛЬЗОВАТЕЛЕМ (НЕ ПОВТОРЯЙ УЖЕ СКАЗАННОЕ ДОСЛОВНО, ПРОДОЛЖАЙ РАЗГОВОР ЕСТЕСТВЕННО):\n" + "\n".join(recent_turns) + "\n\n"

    prompt = (
        f"{history_block}"
        f"ТЕКУЩИЙ ВОПРОС / РЕПЛИКА ПОЛЬЗОВАТЕЛЯ:\n{user_question}\n\n"
        f"ТОЧНЫЕ РАСЧЁТНЫЕ ДАННЫЕ ПО ВСЕМ ШКОЛАМ НУМЕРОЛОГИИ (В ПАМЯТИ МАТРИЦЫ):\n{num_text}\n\n"
        f"КАНОНИЧЕСКИЕ ИСТОЧНИКИ ИЗ БАЗЫ ЗНАНИЙ НУМЕРОЛОГИИ:\n{rag_context}\n\n"
        "ИНСТРУКЦИЯ ДЛЯ ОТВЕТА МАТРИЦЫ:\n"
        "1. Дай глубокий, точный, профессиональный ответ на вопрос пользователя строго по рассчитанным ячейкам Квадрата Пифагора, узлам Матрицы Судьбы (22 аркана), Западным/Халдейским числам, Ведической Санкхья-шастре и циклам прогностики.\n"
        "2. В каждом блоке КОРОТКО УКАЗЫВАЙ, на какую именно школу нумерологии ты опираешься (Классический Психоматрикс А. Ф. Александрова, Система «Идеал» Н. Сидоровой, Матрица Судьбы Н. Ладини / Джулии По, Западная Пифагорейская, Халдейская, Ведическая Санкхья-шастра).\n"
        "3. Если между школами есть различия в расчёте или трактовке — опирайся на наиболее авторитетный канон и ОБЯЗАТЕЛЬНО приводи вторую точку зрения как «Альтернативное мнение другой школы».\n"
        "4. Пиши живым, глубоким, уважительным и красиво структурированным языком на русском языке."
    )

    llm_answer = await call_llm(MATRIX_SYSTEM_PROMPT, prompt, temperature=0.35, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 80:
        return llm_answer.strip()

    return build_offline_numerology_synthesis(data, rag_passages)
