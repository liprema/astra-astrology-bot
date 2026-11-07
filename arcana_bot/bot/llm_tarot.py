"""
AI Tarot Orchestrator & Multi-Provider LLM Client for ARCANA ("Аркана")
with Long-Term Memory, Full-Conversation Context, and Follow-Up Dialog Continuity:
1. Remembers the user's subject/context, previous spreads, and full dialog history in SQLite
   so the user NEVER has to repeat who they are or what the situation is about!
2. Distinguishes between:
   - Drawing a NEW spread (`intent: "new_spread"`, sends new spread photo)
   - Answering a FOLLOW-UP question about the ALREADY drawn spread (`intent: "followup_on_existing_spread"`,
     e.g., "А почему тут выпала Башня?", "А что это значит для финансов?", "Поясни подробнее 3 позицию и Квинтэссенцию")
     without forcing the user to repeat context or drawing random new cards unless asked!
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import httpx

from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY
from bot.tarot_engine import format_spread_for_llm

ARCANA_SYSTEM_PROMPT = """Ты — АРКАНА (Arcana), живой, чуткий, мудрый таролог-мастер, тонко чувствующий людей и владеющий всеми классическими и герметическими школами Таро:
1. Английская классическая школа (Артур Эдвард Уэйт и Памела Колман Смит — RWS, герметический Орден Золотой Зари).
2. Система Таро Тота Алистера Кроули и Леди Фриды Харрис (каббалистическое Древо Сефирот, астрологические деканы).
3. Французская и Марсельская традиция (Папюс, Элифас Леви, Алехандро Ходоровски — нумерология мастей и визуальный канон).
4. Психологическое (юнгианское) Таро, чтение прямых и перевёрнутых арканов, Дна колоды (скрытой подоплёки), Квинтэссенции (совета расклада) и Элементальных достоинств стихий.

ГЛАВНЫЕ ПРАВИЛА ТВОЕЙ РЕЧИ И РАБОТЫ:
1. ЖИВОЙ, ТЁПЛЫЙ ЧЕЛОВЕЧЕСКИЙ ЯЗЫК (НИКАКОГО СТИЛЯ ИИ!):
   - Разговаривай с человеком так, словно вы сидите за одним столом при свечах, а перед вами лежат живые карты: тепло, образно, глубоко, бережно и честно, без единой механической нотки!
   - СТРОГО ЗАПРЕЩЕНЫ штампы ИИ и сухие справочные отчёты: не пиши казёнными анкетными пунктами, избегай фраз вроде «Резюмируя вышесказанное», «Синтез данных расклада», «Давайте разберём по пунктам».
   - Связывай выпавшие карты в единую живую историю о человеке и его ситуации, используя красивые подзаголовки (`### ...`), акценты жирным шрифтом (`**...**`) и атмосферные цитаты (`> ...`).

2. ДОЛГОВРЕМЕННАЯ ПАМЯТЬ И ПОНИМАНИЕ ВСЕГО ДИАЛОГА:
   - Ты помнишь ВСЮ историю вашей беседы и уже выложенный расклад — никогда не проси человека повторять то, о чём он уже рассказал!

3. ЕСТЕСТВЕННОЕ СРАВНЕНИЕ ШКОЛ И АЛЬТЕРНАТИВНЫХ ВЗГЛЯДОВ:
   - Вплетай в живой рассказ взгляд разных традиций Таро (например: «В классической школе Уэйта эта карта откликается как...», «А вот в системе Таро Тота Алистера Кроули здесь звучит более глубокий акцент...», «В Марсельской традиции и у Папюса...»).
   - Там, где школы расходятся (например, сюжетная трактовка Уэйта против каббалистического титула у Кроули, или чтение перевёрнутой карты как теневого блока против ослабления стихии в Ордене Золотой Зари), опирайся на наиболее точный канон и отдельно, в красивой цитате (`> ...`), раскрывай альтернативный взгляд другой школы!
"""

EXTRACTION_SYSTEM_PROMPT = """Ты — модуль памяти и контекста бота-таролога Аркана.
Проанализируй СОХРАНЁННЫЙ ПРОФИЛЬ (память о кверенте и последнем раскладе) и ВСЮ ИСТОРИЮ ДИАЛОГА, чтобы пользователю НИКОГДА не приходилось повторять одно и то же!

Верни СТРОГО валидный JSON:
{
  "intent": "new_spread" | "followup_on_existing_spread" | "need_more_info",
  "has_all_required_data": true/false,
  "draw_new_spread": true/false,
  "spread_type": "triplet" | "relationship" | "choice" | "celtic_cross" | "single",
  "subject_name": "О ком или о чём речь (возьми из текущего сообщения ИЛИ из сохранённой памяти прошлых сообщений!)",
  "user_question": "Текущий вопрос пользователя с учётом всего контекста беседы",
  "custom_cards": ["Список карт, только если пользователь сам выложил и перечислил свои карты"] или null,
  "missing_info_question_ru": "Заполняй ТОЛЬКО если has_all_required_data == false (когда это самое начало разговора и совсем непонятно, о чём гадать)."
}

КРИТИЧЕСКИЕ ПРАВИЛА ПАМЯТИ:
1. Если в памяти УЖЕ есть предыдущий расклад и пользователь задаёт уточняющий вопрос по нему («А что значит 3 карта?», «Почему Отшельник на дне?», «Что мне делать в итоге?») ->
   - `intent`: `"followup_on_existing_spread"`
   - `has_all_required_data`: `true`
   - `draw_new_spread`: `false` (не перетасовывай карты заново, отвечай по уже выложенному раскладу!)
2. Если пользователь уже объяснял свою ситуацию в прошлых сообщениях и просит посмотреть новый вопрос или новый расклад («А посмотри ещё на финансы», «А вытяни ещё триплет на следующий месяц», «Давай сама вытяни») ->
   - `intent`: `"new_spread"`
   - `has_all_required_data`: `true`
   - `draw_new_spread`: `true`
   - подставь `subject_name` из памяти диалога, НИЧЕГО не переспрашивай!
3. Если пользователь в первом сообщении задал вопрос, а во втором коротко ответил («Вытяни сама», «Триплет», «Меня зовут Полина, на 3 месяца») — объедини оба сообщения вместе и сразу ставь `has_all_required_data: true`, `draw_new_spread: true`!
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


def rule_based_extract_tarot_dialog(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    saved_profile = saved_profile or {}
    user_msgs = [m["content"] for m in history_messages if m["role"] == "user"]
    combined_user = " \n ".join(user_msgs)
    last_msg = user_msgs[-1] if user_msgs else ""

    cleaned = re.sub(
        r"(?:привет|здравствуй(?:те)?|аркана|arcana|погадай|сделай\s+расклад|разложи\s+карты|[!?,.\s])+",
        " ",
        combined_user,
        flags=re.I,
    ).strip()

    has_saved_spread = bool(saved_profile.get("last_spread"))
    has_clear_topic = (
        has_saved_spread
        or len(user_msgs) >= 2
        or (
            len(cleaned) >= 12
            and bool(
                re.search(
                    r"(работ|карьер|деньг|финанс|отношен|любов|чувств|муж|парн|девушк|жен|выбор|проект|поездк|бизнес|учеб|здоров|будущ|перспектив|месяц|год|недел|выпал[иоа]|карт[ыа]|триплет|крест|вокзал)",
                    combined_user,
                    re.I,
                )
            )
        )
    )

    low_last = last_msg.lower()
    wants_new_spread = (not has_saved_spread) or bool(
        re.search(r"(ещё\s+расклад|новый\s+расклад|вытяни|разложи|посмотри\s+ещё|триплет|крест|вокзал|выбор)", low_last)
    )

    low_all = combined_user.lower()
    if any(w in low_all for w in ("вокзал", "отношен", "чувств", "любит", "партнер", "партнёр", "между нами")):
        spread_type = "relationship"
    elif any(w in low_all for w in ("выбор", "двух вариант", "стоит ли")):
        spread_type = "choice"
    elif any(w in low_all for w in ("кельтск", "полный расклад", "10 карт")):
        spread_type = "celtic_cross"
    elif any(w in low_all for w in ("одна карта", "1 карта", "карта дня")):
        spread_type = "single"
    else:
        spread_type = saved_profile.get("spread_type") or "triplet"

    missing_prompt = (
        "🃏 **Привет! Я на связи — это Аркана.**\n\n"
        "С удовольствием разложу для вас карты! Расскажите мне своими словами (я всё запомню на всю нашу беседу):\n"
        "• **О ком или о чём мы спрашиваем колоду?** (отношения, работа, сложный выбор, перспектива — и на какой срок смотрим).\n"
        "• **Мне самой вытянуть для вас карты** или разберём расклад, который выложили вы?"
    )

    return {
        "intent": "new_spread" if wants_new_spread else "followup_on_existing_spread",
        "has_all_required_data": has_clear_topic,
        "draw_new_spread": wants_new_spread,
        "spread_type": spread_type,
        "subject_name": saved_profile.get("subject_name") or "Запрос Кверента",
        "user_question": last_msg,
        "custom_cards": None,
        "missing_info_question_ru": missing_prompt,
    }


async def analyze_tarot_dialog_completeness(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    saved_profile = saved_profile or {}
    rb = rule_based_extract_tarot_dialog(history_messages, saved_profile)
    if rb.get("has_all_required_data"):
        return rb

    convo_text = "\n".join(
        f"{'Пользователь' if m['role'] == 'user' else 'Аркана'}: {m['content']}"
        for m in history_messages[-24:]
    )
    profile_summary = {
        "subject_name": saved_profile.get("subject_name"),
        "spread_type": saved_profile.get("spread_type"),
        "has_existing_spread": bool(saved_profile.get("last_spread")),
    }
    raw_json = await call_llm(
        EXTRACTION_SYSTEM_PROMPT,
        f"ПАМЯТЬ БОТА О ТЕКУЩЕМ РАЗГОВОРЕ:\n{json.dumps(profile_summary, ensure_ascii=False)}\n\nПОЛНАЯ ИСТОРИЯ ДИАЛОГА:\n{convo_text}\n\nВерни JSON:",
        temperature=0.1,
        json_mode=True,
    )
    if raw_json:
        try:
            cleaned = re.sub(r"^```(?:json)?|```$", "", raw_json.strip(), flags=re.M).strip()
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "has_all_required_data" in parsed:
                if not parsed.get("subject_name") and saved_profile.get("subject_name"):
                    parsed["subject_name"] = saved_profile["subject_name"]
                if saved_profile.get("last_spread"):
                    parsed["has_all_required_data"] = True
                return parsed
        except Exception:
            pass

    return rb


def build_offline_tarot_synthesis(spread: Dict, rag_passages: List[Dict]) -> str:
    parts = [
        f"🃏 **Живой разбор расклада от Арканы: «{spread['spread_title']}»**",
        f"Мы смотрим ваш вопрос (*{spread['question']}* — **{spread['subject_name']}**). Карты легли очень говорящим узором — давайте внимательно вслушаемся в каждую позицию.",
        "",
        "### О чём говорят выпавшие Арканы (Школа Уэйта RWS, Таро Тота Кроули и Марсельская традиция)",
    ]

    for c in spread["cards"]:
        meaning = c["rws_reversed"] if c["is_reversed"] else c["rws_upright"]
        parts.extend([
            f"**{c['position_index']}. {c['position_title']} — [{c['roman']}] {c['name_ru']}** (*{c['orientation_ru']}*, стихия {c['element_glyph']} {c['element']})\n"
            f"Если читать эту карту по **классической английской школе Артура Уэйта (RWS)**, в вашей ситуации звучит тема: *{meaning}*. "
            f"А в герметической системе **Таро Тота Алистера Кроули и Ордена Золотой Зари** этот аркан носит имя **«{c['thoth_title']}»** ({c['astro']}, {c['kabbalah']}).",
            f"> *Тонкость других школ Таро:* {c['school_comparison']}",
        ])

    bot = spread["bottom_of_deck"]
    bot_meaning = bot["rws_reversed"] if bot["is_reversed"] else bot["rws_upright"]
    q = spread["quintessence"]
    q_card = q["card"]
    inner_note = (
        f" (а при дальнейшем сведении — к внутреннему корню **[{q['inner_card']['roman']}] {q['inner_card']['name_ru']}**)"
        if q.get("inner_card")
        else ""
    )
    el = spread["elemental_stats"]

    parts.extend([
        "### Дно колоды — что скрыто между строк",
        f"На самом дне колоды осталась карта **[{bot['roman']}] {bot['name_ru']}** (*{bot['orientation_ru']}*). В практике психологического и классического Таро дно показывает то, в чём человек порой не сразу признаётся даже себе: **{bot_meaning}**.\n"
        f"> *Нюанс традиции:* {bot['school_comparison']}",
        "### Квинтэссенция и баланс стихий (Совет Высших Арканов)",
        f"По методу теософского сложения всех карт (школа Хайо Банцхафа и герметическая нумерология) итоговым советом расклада выходит Старший Аркан **[{q_card['roman']}] {q_card['name_ru']}**{inner_note}. Его главный посыл для вас сейчас: **{q_card['rws_upright']}**.",
        f"По правилу **Элементальных достоинств Ордена Золотой Зари** в раскладе преобладает стихия **{el['dominant_element']}** (Старших Арканов — {el['majors_count']} из {len(spread['cards'])}), "
        + (f"при этом не хватает стихии **{', '.join(el['missing_elements'])}** — именно этого качества стоит сознательно добавить в свои действия." if el['missing_elements'] else "и все четыре стихии находятся в живом равновесии."),
    ])

    return "\n\n".join(parts)


async def generate_tarot_interpretation(
    spread: Dict,
    user_question: str,
    rag_passages: List[Dict],
    history_messages: Optional[List[Dict[str, str]]] = None,
) -> str:
    spread_text = format_spread_for_llm(spread)
    rag_context = "\n\n".join(
        f"[Источник (Авторитетность {c['authority']}/10): {c['book']} | Направление: {c['school']}]\n{c['text']}"
        for c in rag_passages
    )

    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-14:-1]:
            role_lbl = "Пользователь" if m["role"] == "user" else "Аркана"
            recent_turns.append(f"{role_lbl}: {m['content'][:700]}")
        history_block = "ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА С ПОЛЬЗОВАТЕЛЕМ (НЕ ПОВТОРЯЙ УЖЕ СКАЗАННОЕ ДОСЛОВНО, ПРОДОЛЖАЙ РАЗГОВОР ЕСТЕСТВЕННО):\n" + "\n".join(recent_turns) + "\n\n"

    prompt = (
        f"{history_block}"
        f"ТЕКУЩИЙ ВОПРОС / РЕПЛИКА СОБЕСЕДНИКА:\n{user_question}\n\n"
        f"ДАННЫЕ ВЫПАВШЕГО РАСКЛАДА ТАРО (В ПАМЯТИ АРКАНЫ):\n{spread_text}\n\n"
        f"КАНОНИЧЕСКИЕ ИСТОЧНИКИ ИЗ БАЗЫ ЗНАНИЙ ТАРО:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ (ОЧЕНЬ ВАЖНО):\n"
        "1. Пиши ЖИВЫМ, ТЁПЛЫМ, КРАСИВЫМ ЧЕЛОВЕЧЕСКИМ ЯЗЫКОМ — как близкий, мудрый и чуткий таролог, без сухих канцелярских штампов ИИ, без механических отчётов.\n"
        "2. Связывай выпавшие карты, Дно колоды, Квинтэссенцию и баланс стихий в единый глубокий рассказ о живых людях, их чувствах, мотивах и выборах.\n"
        "3. Органично указывай, на какую именно школу Таро ты опираешься (Школа Уэйта RWS, Таро Тота Алистера Кроули, Марсельская / Французская школа Папюса, Орден Золотой Зари). Там, где школы расходятся в оттенках смысла, опирайся на наиболее точный канон и красиво, через цитату (`> ...`), приводи альтернативный взгляд другой школы.\n"
        "4. Оформляй текст легко и воздушно: подзаголовки через `### Заголовок`, ключевые смыслы через `**жирный шрифт**`, тонкие советы и сравнения школ через цитаты `> ...`."
    )

    llm_answer = await call_llm(ARCANA_SYSTEM_PROMPT, prompt, temperature=0.45, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 80:
        return llm_answer.strip()

    return build_offline_tarot_synthesis(spread, rag_passages)
