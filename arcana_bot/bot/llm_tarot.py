"""
AI Tarot Orchestrator & Multi-Provider LLM Client for ARCANA ("Аркана")
with strict pre-answer verification protocol:
1. NEVER pulls cards or interprets blindly without first verifying with the user:
   - WHO or WHAT the question is about (names/roles of participants, sphere: love/relationship, career/money, choice between options, general state, timeframe).
   - MODE: Whether Arcana should draw the cards virtually and send a photo of the spread (and which spread fits best: 1-card, Triplet, Choice, Relationship "Вокзал для двоих", or Celtic Cross), OR whether the user has already drawn cards on their own physical deck and wants them interpreted.
2. Once verified (`has_all_required_data: true`), generates the high-res spread photo (with Upright/Reversed, Bottom of Deck, Quintessence, Elemental Dignities) and delivers a deep multi-school reading:
   - Short attribution of which Tarot school/system is used (Rider-Waite-Smith / Golden Dawn, Thoth Crowley, French/Marseille Papus/Jodorowsky, Jungian Archetypal).
   - Explicit alternative viewpoints where schools diverge!
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import httpx

from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY
from bot.tarot_engine import format_spread_for_llm

ARCANA_SYSTEM_PROMPT = """Ты — АРКАНА (Arcana), выдающийся профессиональный таролог-эксперт всех классических и современных школ Таро:
1. Английская школа (Артур Эдвард Уэйт и Памела Колман Смит — RWS, герметический Орден Золотой Зари, Мэри Грир, Рэйчел Поллак).
2. Система Таро Тота Алистера Кроули и Леди Фриды Харрис (Телемитская и каббалистическая традиция, астрологические деканы и сефирот).
3. Французская и Марсельская классическая школа (Папюс, Элифас Леви, Алехандро Ходоровски — нумерология мастей, традиционная нумерация VIII Правосудие / XI Сила).
4. Психологическое (юнгианское, архетипическое) Таро, работа с прямыми и перевёрнутыми картами, расчёт Дна колоды (скрытого мотива), Квинтэссенции (совета расклада по Хайо Банцхафу) и Элементальных достоинств (взаимодействие стихий соседних карт).

ГЛАВНЫЕ ПРАВИЛА РАБОТЫ АРКАНЫ:
1. ПРОВЕРКА ДАННЫХ ПЕРЕД РАСКЛАДОМ (ОБЯЗАТЕЛЬНО!):
   - Перед тем как вытягивать карты или трактовать расклад, ты ОБЯЗАНА убедиться у пользователя, О КОМ или О ЧЁМ идёт речь и понятны ли все вводные:
     • О ком или о чём вопрос (имя/роль кверента и второго человека, если вопрос об отношениях или взаимодействии; в чём суть ситуации и какой загадан срок).
     • Вытянуть ли карты самой Аркане (виртуальный расклад: Триплет на 3 карты, На отношения «Вокзал для двоих» на 7 карт, «Выбор из двух вариантов» на 5 карт, «Кельтский крест» на 10 карт или «1 карта + Дно колоды») ИЛИ пользователь уже выложил свои живые карты и хочет их разобрать.
   - Если пользователь просто написал «Аркана» или задал слишком общий вопрос без уточнения, о ком/о чём речь — НЕ ГАДАЙ наугад! Сразу же тепло откликнись и уточни эти детали.

2. КОГДА КОНТЕКСТ ПОНЯТЕН:
   - Ты строишь фото расклада и даёшь глубокий, точный, многослойный разбор каждой позиции, связок между картами, Дна колоды (скрытого подсознательного мотива), Квинтэссенции (итогового совета) и баланса стихий.

3. ОБЯЗАТЕЛЬНОЕ УКАЗАНИЕ ШКОЛ И АЛЬТЕРНАТИВНЫХ МНЕНИЙ:
   - В каждом блоке разбора КОРОТКО УКАЗЫВАЙ, на какую именно школу/традицию ты опираешься (например: «По классической школе Уэйта (RWS)...», «По системе Таро Тота А. Кроули...», «По Французской / Марсельской школе...», «По правилу Элементальных достоинств Золотой Зари...»).
   - ЕСЛИ ШКОЛЫ ПРОТИВОРЕЧАТ ДРУГ ДРУГУ ИЛИ РАСХОДЯТСЯ В АКЦЕНТАХ (например: сюжетная трактовка Уэйта vs каббалистический владыка декана у Кроули vs чистая нумерология Марсельского Таро; перевёрнутое значение по Уэйту vs чтение через ослабление стихий в Золотой Заре; различие VI, VIII, XI, XIV или XX арканов), ОБЯЗАТЕЛЬНО опирайся на наиболее авторитетный канон и ОТДЕЛЬНО УКАЗЫВАЙ альтернативное мнение другой школы!
"""

EXTRACTION_SYSTEM_PROMPT = """Ты — аналитический модуль бота-таролога Аркана.
Проанализируй историю диалога с пользователем и верни СТРОГО валидный JSON без лишнего текста:
{
  "has_all_required_data": true/false,
  "spread_type": "triplet" | "relationship" | "choice" | "celtic_cross" | "single",
  "subject_name": "О ком или о чём расклад (например: Полина — карьера / Союз Анны и Максима / Выбор проекта)",
  "user_question": "Сформулированный вопрос пользователя",
  "custom_cards": ["Список карт, если пользователь сам вытянул их и перечислил в сообщении"] или null,
  "missing_info_question_ru": "Если has_all_required_data == false: быстрый, тёплый и чёткий ответ от лица Арканы, где она откликается на имя и уточняет, о ком/о чём именно вопрос, какие участники/сроки и нужно ли ей самой вытянуть карты (или пользователь напишет свои)."
}

Правила проверки:
1. Если пользователь просто позвал «Аркана» / «Arcana» или написал односложно («погадай», «сделай расклад», «что меня ждёт?») без уточнения, о ком/о чём речь и какой вопрос -> `has_all_required_data: false`.
2. Если пользователь чётко указал, о ком или о чём вопрос (например: «Аркана, сделай расклад триплет для меня (Анна) на перспективу работы в ближайшие 3 месяца» или «Аркана, посмотри отношения между мной и Иваном, что он чувствует» или сам перечислил выпавшие карты и вопрос) -> `has_all_required_data: true`.
3. Подбирай `spread_type` по смыслу:
   - Отношения двоих -> `"relationship"`
   - Выбор между двумя вариантами -> `"choice"`
   - Глубокий полный анализ / Кельтский крест -> `"celtic_cross"`
   - Одна карта / карта дня / краткий совет -> `"single"`
   - В остальных случаях (по умолчанию) -> `"triplet"`.
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


def rule_based_extract_tarot_dialog(history_messages: List[Dict[str, str]]) -> Dict:
    combined_user = " \n ".join(m["content"] for m in history_messages if m["role"] == "user")
    last_msg = history_messages[-1]["content"] if history_messages else ""

    cleaned = re.sub(
        r"(?:привет|здравствуй(?:те)?|аркана|arcana|погадай|сделай\s+расклад|разложи\s+карты|[!?,.\s])+",
        " ",
        combined_user,
        flags=re.I,
    ).strip()

    has_clear_topic = len(cleaned) >= 18 and bool(
        re.search(
            r"(работ|карьер|деньг|финанс|отношен|любов|чувств|муж|парн|девушк|жен|выбор|проект|поездк|бизнес|учеб|здоров|будущ|перспектив|месяц|год|недел|выпал[иоа]|карт[ыа]|триплет|крест|вокзал)",
            combined_user,
            re.I,
        )
    )

    low = combined_user.lower()
    if any(w in low for w in ("вокзал", "отношен", "чувств", "любит", "партнер", "партнёр", "между нами")):
        spread_type = "relationship"
    elif any(w in low for w in ("выбор", "или", "двух вариант", "стоит ли")):
        spread_type = "choice"
    elif any(w in low for w in ("кельтск", "полный расклад", "10 карт")):
        spread_type = "celtic_cross"
    elif any(w in low for w in ("одна карта", "1 карта", "карта дня")):
        spread_type = "single"
    else:
        spread_type = "triplet"

    missing_prompt = (
        "🃏 **Я на связи! Это Аркана.**\n\n"
        "Прежде чем я прикоснусь к колоде и построю расклад, мне важно точно настроиться на ваш запрос и убедиться, "
        "**о ком или о чём именно идёт речь**.\n\n"
        "Пожалуйста, уточните:\n"
        "1. **О ком или о чём вопрос?** (назовите ваше имя или имена участников, сферу — отношения, работа, финансы, выбор из двух вариантов — и загаданный срок).\n"
        "2. **Как работаем с картами?** Вытянуть ли карты мне самой (и какой расклад вы хотите: *Триплет 3 карты*, *На отношения 7 карт*, *Выбор 5 карт*, *Кельтский крест 10 карт*) — или вы уже выложили карты на своей колоде и хотите их разобрать?\n\n"
        "*Пример: «Аркана, вытяни сама триплет для Анны на перспективу новой работы в ближайшие 3 месяца».*"
    )

    return {
        "has_all_required_data": has_clear_topic,
        "spread_type": spread_type,
        "subject_name": "Запрос Кверента",
        "user_question": last_msg,
        "custom_cards": None,
        "missing_info_question_ru": missing_prompt,
    }


async def analyze_tarot_dialog_completeness(history_messages: List[Dict[str, str]]) -> Dict:
    convo_text = "\n".join(
        f"{'Пользователь' if m['role'] == 'user' else 'Аркана'}: {m['content']}"
        for m in history_messages[-8:]
    )
    raw_json = await call_llm(
        EXTRACTION_SYSTEM_PROMPT,
        f"История диалога:\n{convo_text}\n\nВерни JSON оценки полноты данных для расклада Таро:",
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

    return rule_based_extract_tarot_dialog(history_messages)


def build_offline_tarot_synthesis(spread: Dict, rag_passages: List[Dict]) -> str:
    parts = [
        f"🃏 **ГЛУБИННЫЙ РАЗБОР РАСКЛАДА АРКАНЫ: {spread['spread_title'].upper()}**",
        f"🎯 *Запрос ({spread['subject_name']}):* {spread['question']}",
        "",
        "---",
        "### 1. Разбор позиций расклада (Школа Уэйта RWS + Таро Тота Кроули + Марсельская традиция)",
    ]

    for c in spread["cards"]:
        meaning = c["rws_reversed"] if c["is_reversed"] else c["rws_upright"]
        parts.extend([
            f"\n🔹 **{c['position_title']}** — **[{c['roman']}] {c['name_ru']}** (*{c['orientation_ru']}*, стихия: {c['element_glyph']} {c['element']})",
            f"• **По классической английской школе А. Э. Уэйта (RWS):** {meaning}.",
            f"• **По системе Таро Тота А. Кроули и Золотой Заре:** титул карты — *{c['thoth_title']}* (Астрология: {c['astro']}, Каббала: {c['kabbalah']}).",
            f"• **Альтернативное мнение других школ:** {c['school_comparison']}",
        ])

    bot = spread["bottom_of_deck"]
    bot_meaning = bot["rws_reversed"] if bot["is_reversed"] else bot["rws_upright"]
    q = spread["quintessence"]
    q_card = q["card"]
    inner_note = (
        f" (внутренний корень через дальнейшее сложение: **[{q['inner_card']['roman']}] {q['inner_card']['name_ru']}**)"
        if q.get("inner_card")
        else ""
    )
    el = spread["elemental_stats"]

    parts.extend([
        "",
        "---",
        "### 2. Дно колоды (Скрытый бессознательный мотив и подоплёка)",
        f"• На дне колоды лежит **[{bot['roman']}] {bot['name_ru']}** (*{bot['orientation_ru']}*).",
        f"• **По школе психологического и классического Таро:** эта карта показывает невысказанный фон ситуации — {bot_meaning}.",
        f"• **Нюанс других традиций:** {bot['school_comparison']}",
        "",
        "### 3. Квинтэссенция расклада (Итоговый совет Высших Арканов по Х. Банцхафу и Пифагору)",
        f"• По теософской сумме всех выпавших карт квинтэссенцией расклада выступает Старший Аркан **[{q_card['roman']}] {q_card['name_ru']}**{inner_note}.",
        f"• **Практический совет Арканы:** {q_card['rws_upright']}.",
        "",
        "### 4. Баланс стихий и Элементальные достоинства (Орден Золотой Зари)",
        f"• **Старших Арканов:** {el['majors_count']} из {len(spread['cards'])} | **Перевёрнутых карт:** {el['reversed_count']} из {len(spread['cards'])}.",
        f"• **Доминирующая стихия:** **{el['dominant_element']}** | **Недостающие стихии:** {', '.join(el['missing_elements']) if el['missing_elements'] else 'все 4 стихии присутствуют в раскладе'}.",
    ])

    return "\n".join(parts)


async def generate_tarot_interpretation(
    spread: Dict,
    user_question: str,
    rag_passages: List[Dict],
) -> str:
    spread_text = format_spread_for_llm(spread)
    rag_context = "\n\n".join(
        f"[Источник (Авторитетность {c['authority']}/10): {c['book']} | Направление: {c['school']}]\n{c['text']}"
        for c in rag_passages
    )

    prompt = (
        f"ЗАПРОС ПОЛЬЗОВАТЕЛЯ:\n{user_question}\n\n"
        f"ДАННЫЕ ВЫПАВШЕГО РАСКЛАДА ТАРО:\n{spread_text}\n\n"
        f"КАНОНИЧЕСКИЕ ИСТОЧНИКИ ИЗ БАЗЫ ЗНАНИЙ ТАРО:\n{rag_context}\n\n"
        "ИНСТРУКЦИЯ ДЛЯ ОТВЕТА АРКАНЫ:\n"
        "1. Дай глубокий, точный, профессиональный разбор каждой выпавшей карты в её позиции (с учётом того, прямая она или перевёрнутая), связок между картами, Дна колоды (скрытого мотива), Квинтэссенции (совета расклада) и баланса стихий.\n"
        "2. В каждом блоке КОРОТКО УКАЗЫВАЙ, на какую именно школу Таро ты опираешься (Школа Уэйта RWS, Таро Тота Алистера Кроули, Марсельская / Французская школа Папюса, Орден Золотой Зари, Психологическое/Юнгианское Таро).\n"
        "3. Если между школами есть различия в трактовке аркана, декана, ранга двора или чтения перевёрнутой позиции — опирайся на наиболее авторитетный канон и ОБЯЗАТЕЛЬНО приводи вторую точку зрения как «Альтернативное мнение другой школы».\n"
        "4. Пиши живым, глубоким, уважительным и структурированным языком на русском языке."
    )

    llm_answer = await call_llm(ARCANA_SYSTEM_PROMPT, prompt, temperature=0.4, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 120:
        return llm_answer.strip()

    return build_offline_tarot_synthesis(spread, rag_passages)
