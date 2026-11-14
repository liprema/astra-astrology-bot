"""
AI Tarot Orchestrator & Multi-Provider LLM Client for ARCANA ("Аркана")
— Smart, Natural & Memory-Persistent Tarot Master with Sassy Character ("стервочка"):
1. 2026/2027 Real-Time Awareness: Explicitly anchored in late 2026 (approaching New Year 2027).
2. Natural Conversation vs. Tarot Spreads:
   - Draws a Tarot spread ONLY when the user asks for a reading/cards or brings a new divinatory question
     before any spread is drawn.
   - Once a spread is drawn (or when the user is just chatting, bantering, or asking follow-up questions),
     Arcana responds naturally and wittily WITHOUT forcing every sentence through a formal card breakdown,
     while keeping the drawn spread and dialog history in active memory.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import re
from typing import Dict, List, Optional

import httpx
import pytz

from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY
from bot.tarot_engine import format_spread_for_llm

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


ARCANA_SYSTEM_PROMPT = """Ты — АРКАНА (Arcana), блестящий профессиональный таролог и харизматичная собеседница с ярким, дерзким характером эффектной «стервочки».

ТВОЙ ХАРАКТЕР И ЭКСПЕРТИЗА:
- Твой характер — острая на язык, ироничная, умная, прямолинейная «стервочка» с рентгеновским взглядом. Ты не сюсюкаешь, снимаешь розовые очки с первой секунды и называешь вещи своими именами.
- Когда ты делаешь расклад Таро, ты опираешься на классику Уэйта (RWS), Таро Тота Алистера Кроули, Марсельскую традицию и Орден Золотой Зари.

ГЛАВНОЕ ПРАВИЛО УМНОГО ОБЩЕНИЯ (НЕ ПРОГОНЯЙ КАЖДУЮ ФРАЗУ ЧЕРЕЗ КАРТЫ!):
- Ты — живая, остроумная, проницательная девушка, а не автомат по выдаче трактовок.
- Когда человек просто болтает с тобой, шутит, подкалывает, делится историей из жизни или обсуждает ситуацию в диалоге — ОБЩАЙСЯ ЕСТЕСТВЕННО, ЖИВО И ОСТРОУМНО, БЕЗ РАСКЛАДОВ И БЕЗ ПЕРЕСКАЗА КАРТ В КАЖДОЙ ФРАЗЕ!
- Если вы уже разложили карты и человек задаёт уточняющий вопрос по раскладу — у тебя в памяти лежит весь выпавший расклад: ответь конкретно, хлестко и по делу в живом диалоге, без громоздких шаблонов и подзаголовков `###`.
- Никогда не забывай, о чём вы говорили выше в диалоге и какие карты уже выпали.
- СТРОГО ЗАПРЕЩЕНЫ штампы ИИ («Резюмируя вышесказанное», «Синтез данных расклада», «Давайте разберём по пунктам»).
"""


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


def _wants_tarot_spread(text: str, has_saved_spread: bool) -> bool:
    """
    Determines whether the user wants Arcana to actually pull & render a new Tarot spread right now.
    - Explicit spread requests ("погадай", "сделай расклад", "разложи карты", "посмотри на картах", "карта дня") -> True.
    - If NO spread is saved yet, a direct divinatory question about feelings/future/outcome -> True.
    - If a spread IS already saved, normal follow-up questions or conversation do NOT draw a new spread
      unless the user explicitly asks to lay new cards!
    """
    low = text.lower()
    explicit_spread_cmd = bool(
        re.search(
            r"(сделай\w*\s+расклад|разложи\w*(?:\s+карт\w*)?|вытяни\w*\s+карт|кинь\w*\s+карт|погадай\w*|посмотри\w*\s+на\s+карт|посмотри\w*\s+по\s+карт|ещё\s+расклад|еще\s+расклад|новый\s+расклад|другой\s+расклад|триплет|кельтск\w*\s+крест|вокзал\s+для\s+двоих|карт[уыа]\s+дня)",
            low,
        )
    )
    if explicit_spread_cmd:
        return True

    if not has_saved_spread:
        divinatory_question = bool(
            re.search(
                r"(что\s+он\s+ко\s+мне|что\s+она\s+ко\s+мне|его\s+чувств|её\s+чувств|ее\s+чувств|что\s+между\s+нами|верн[её]тся\s+ли|напишет\s+ли|позвонит\s+ли|что\s+меня\s+жд[её]т|что\s+жд[её]т\s+в\s+202[678]|стоит\s+ли\s+мне|получится\s+ли|посмотри\w*\s+(?:отношен|ситуац|работ|деньг|финанс|бывш|его|её))",
                low,
            )
        )
        return divinatory_question

    return False


def rule_based_extract_tarot_dialog(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    """
    Smart Tarot Intent & Memory Extractor:
    - Draws a new visual spread ("new_spread") ONLY when explicitly requested or on an initial divinatory question.
    - Once a spread is drawn, all follow-up questions and normal conversation go through the Smart Conversational Brain
      ("casual_chat") which has the full drawn spread in memory, so Arcana never spams card readings on every message!
    """
    saved_profile = saved_profile or {}
    user_msgs = [m["content"] for m in history_messages if m["role"] == "user"]
    last_msg = user_msgs[-1] if user_msgs else ""
    low_last = last_msg.lower()

    has_saved_spread = bool(saved_profile.get("last_spread"))

    cleaned_topic = re.sub(
        r"(?:привет\w*|здравствуй\w*|аркана|аркану|аркане|арканой|arcana|arkana|погадай(?:\s+мне)?|сделай(?:\s+мне)?\s+расклад|разложи(?:\s+мне)?(?:\s+карты)?|вытяни(?:\s+мне)?\s+карты|посмотри(?:\s+мне)?\s+на\s+картах|[!?,.\s])+",
        " ",
        low_last,
        flags=re.I,
    ).strip()

    has_topic_in_msg = len(cleaned_topic) >= 2 or ("карта дня" in low_last or "карту дня" in low_last)

    if any(w in low_last for w in ("вокзал", "отношен", "чувств", "любит", "партнер", "партнёр", "между нами", "бывш", "думает", "напишет", "вернется", "вернётся")):
        spread_type = "relationship"
    elif any(w in low_last for w in ("выбор", "двух вариант", "или")):
        spread_type = "choice"
    elif any(w in low_last for w in ("кельтск", "полный расклад", "10 карт")):
        spread_type = "celtic_cross"
    elif any(w in low_last for w in ("одна карта", "1 карта", "карта дня", "карту дня")):
        spread_type = "single"
    else:
        spread_type = saved_profile.get("spread_type") or "triplet"

    wants_spread = _wants_tarot_spread(last_msg, has_saved_spread=has_saved_spread)

    # Also check if in the previous turn Arcana asked for the topic of the spread ("need_more_info")
    awaiting_topic = bool(saved_profile.get("awaiting_spread_topic"))

    if wants_spread and not has_topic_in_msg:
        intent = "need_more_info"
        has_all = False
        draw_new = False
    elif (wants_spread and has_topic_in_msg) or (awaiting_topic and has_topic_in_msg):
        intent = "new_spread"
        has_all = True
        draw_new = True
    else:
        # Either chatting, bantering, or discussing the already-drawn spread in memory!
        intent = "casual_chat"
        has_all = False
        draw_new = False

    missing_hint = (
        "Кверент попросил сделать расклад, но не назвал тему, сферу или человека, на которого нужно смотреть."
        if intent == "need_more_info"
        else ""
    )

    return {
        "intent": intent,
        "has_all_required_data": has_all,
        "draw_new_spread": draw_new,
        "awaiting_spread_topic": intent == "need_more_info",
        "spread_type": spread_type,
        "subject_name": saved_profile.get("subject_name") or "Запрос Кверента",
        "user_question": last_msg,
        "custom_cards": None,
        "missing_info_question_ru": missing_hint,
    }


async def analyze_tarot_dialog_completeness(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    saved_profile = saved_profile or {}
    return rule_based_extract_tarot_dialog(history_messages, saved_profile)


async def generate_arcana_chat_response(
    user_message: str,
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
    missing_info_hint: str = "",
) -> str:
    """
    Smart Unified Conversational & Follow-Up Brain for Arcana:
    - Has the full drawn Tarot spread (`spread_summary`) and full conversation history in memory.
    - Distinguishes between normal human banter/chatting (where it does NOT analyze cards)
      and follow-up questions about the drawn spread (where it answers sharply and naturally using the saved spread).
    """
    saved_profile = saved_profile or {}
    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-24:-1]:
            role_lbl = "Собеседник" if m["role"] == "user" else "Аркана"
            recent_turns.append(f"{role_lbl}: {m['content'][:900]}")
        history_block = "ИСТОРИЯ ВАШЕГО ДИАЛОГА (ПОМНИ ВСЁ, О ЧЁМ ГОВОРИЛИ):\n" + "\n".join(recent_turns) + "\n\n"

    spread_memory_block = ""
    if saved_profile.get("spread_summary"):
        spread_memory_block = (
            "ПАМЯТЬ АРКАНЫ — ПОСЛЕДНИЙ ВЫЛОЖЕННЫЙ РАСКЛАД ЭТОГО ЧЕЛОВЕКА (ИСПОЛЬЗУЙ ТОЛЬКО ЕСЛИ ОН СПРАШИВАЕТ О РАСКЛАДЕ ИЛИ СИТУАЦИИ ИЗ НЕГО):\n"
            f"{saved_profile['spread_summary'][:3000]}\n\n"
        )
    elif saved_profile.get("last_spread"):
        try:
            spread_memory_block = (
                "ПАМЯТЬ АРКАНЫ — ПОСЛЕДНИЙ ВЫЛОЖЕННЫЙ РАСКЛАД:\n"
                f"{format_spread_for_llm(saved_profile['last_spread'])[:3000]}\n\n"
            )
        except Exception:
            pass

    if missing_info_hint:
        task_block = (
            f"{missing_info_hint}\n"
            "СТРОГОЕ ПРАВИЛО: НЕ обещай «сейчас разложу и вернусь с ответом», пока кверент не назвал тему! "
            "Ответь коротко и с фирменной иронией Арканы: скажи, что колода уже в руках, и уточни, какую именно ситуацию, человека или сферу мы сейчас смотрим."
        )
    else:
        task_block = (
            "КАК ОТВЕТИТЬ НА СООБЩЕНИЕ СОБЕСЕДНИКА:\n"
            "1. Сначала пойми смысл сообщения:\n"
            "   • Если человек ПРОСТО БОЛТАЕТ с тобой, шутит, спорит, делится историей, обсуждает жизнь или реагирует на твои слова — "
            "ОТВЕТЬ КАК ЖИВАЯ, ОСТРОУМНАЯ, ДЕРЗКАЯ «СТЕРВОЧКА» АРКАНА В ОБЫЧНОМ ДИАЛОГЕ (2–5 предложений)! КАТЕГОРИЧЕСКИ НЕ ДЕЛАЙ расклад и НЕ приплетай карты Таро к каждой обычной фразе!\n"
            "   • Если же человек задаёт КОНКРЕТНЫЙ УТОЧНЯЮЩИЙ ВОПРОС по уже выложенному раскладу или разбираемой ситуации — "
            "ответь хлестко, умно и по делу, опираясь на расклад из блока ПАМЯТЬ АРКАНЫ (но живым разговорным языком, без громоздких шаблонов и подзаголовков `###`).\n"
            "2. Помни, что сейчас конец 2026 года (ноябрь 2026) и впереди 2027 год."
        )

    prompt = f"{spread_memory_block}{history_block}{task_block}\n\nНОВОЕ СООБЩЕНИЕ СОБЕСЕДНИКА:\n{user_message}"

    ans = await call_llm(ARCANA_SYSTEM_PROMPT, prompt, temperature=0.65, json_mode=False)
    if ans and len(ans.strip()) > 6:
        clean_ans = ans.strip()
        if missing_info_hint and re.search(r"(сейчас\s+(?:разложу|вытяну|посмотрю|вернусь)|вернусь\s+с\s+ответом|минутку)", clean_ans, re.I):
            return "🃏 Колода уже у меня в руках, дорогая. Формулируй запрос чётко: **на кого или на какую ситуацию** раскладываем?"
        return clean_ans

    if missing_info_hint:
        return "🃏 Колода уже у меня в руках, дорогая. Формулируй запрос чётко: **на кого или на какую ситуацию** раскладываем?"
    return "🃏 Ну давай без розовых очков, дорогая — рассказывай, что там у тебя происходит?"


def build_offline_tarot_synthesis(spread: Dict, rag_passages: List[Dict]) -> str:
    parts = [
        f"🃏 **Разбор расклада от Арканы: «{spread['spread_title']}»**",
        f"Смотрим твой запрос (*{spread['question']}* — **{spread['subject_name']}**). Снимаем розовые очки и разбираем по позициям, что здесь происходит на самом деле.",
        "",
        "### Позиции расклада (Школа Уэйта RWS, Таро Тота Кроули и Марсельский канон)",
    ]

    for c in spread["cards"]:
        meaning = c["rws_reversed"] if c["is_reversed"] else c["rws_upright"]
        parts.extend([
            f"**{c['position_index']}. {c['position_title']} — [{c['roman']}] {c['name_ru']}** (*{c['orientation_ru']}*, стихия {c['element_glyph']} {c['element']})\n"
            f"По **классике Уэйта (RWS)** карта прямо указывает на *{meaning}*. "
            f"А в системе **Таро Тота Алистера Кроули** этот аркан носит титул **«{c['thoth_title']}»** ({c['astro']}, {c['kabbalah']}), вскрывая истинную подоплёку позиции.",
            f"> *Нюанс школ Таро:* {c['school_comparison']}",
        ])

    bot = spread["bottom_of_deck"]
    bot_meaning = bot["rws_reversed"] if bot["is_reversed"] else bot["rws_upright"]
    q = spread["quintessence"]
    q_card = q["card"]
    inner_note = (
        f" (с переходом во внутренний корень **[{q['inner_card']['roman']}] {q['inner_card']['name_ru']}**)"
        if q.get("inner_card")
        else ""
    )
    el = spread["elemental_stats"]

    parts.extend([
        "### Дно колоды — скрытый мотив и теневой фон",
        f"На дне колоды лежит **[{bot['roman']}] {bot['name_ru']}** (*{bot['orientation_ru']}*). Это то, что пытаются спрятать под ковёр: **{bot_meaning}**.\n"
        f"> *Сравнение традиций:* {bot['school_comparison']}",
        "### Квинтэссенция и баланс стихий (Главный совет и стратегия)",
        f"По сумме всех арканов твоя Квинтэссенция — **[{q_card['roman']}] {q_card['name_ru']}**{inner_note}. Главный вектор действий: **{q_card['rws_upright']}**.",
        f"По **Элементальным достоинствам Золотой Зари** в раскладе доминирует стихия **{el['dominant_element']}** (Старших Арканов — {el['majors_count']} из {len(spread['cards'])}), "
        + (f"при дефиците стихии **{', '.join(el['missing_elements'])}** — именно её трезвости сейчас нужно добавить." if el['missing_elements'] else "и все четыре стихии сбалансированы."),
    ])

    return "\n\n".join(parts)


async def generate_tarot_interpretation(
    spread: Dict,
    user_question: str,
    rag_passages: List[Dict],
    history_messages: Optional[List[Dict[str, str]]] = None,
    is_followup: bool = False,
) -> str:
    spread_text = format_spread_for_llm(spread)
    rag_context = "\n\n".join(
        f"[Источник (Авторитетность {c['authority']}/10): {c['book']} | Направление: {c['school']}]\n{c['text']}"
        for c in rag_passages
    )

    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-16:-1]:
            role_lbl = "Кверент" if m["role"] == "user" else "Аркана"
            recent_turns.append(f"{role_lbl}: {m['content'][:700]}")
        history_block = "ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА:\n" + "\n".join(recent_turns) + "\n\n"

    prompt = (
        f"{history_block}"
        f"ВОПРОС КВЕРЕНТА:\n{user_question}\n\n"
        f"ДАННЫЕ ВЫПАВШЕГО РАСКЛАДА ТАРО:\n{spread_text}\n\n"
        f"КАНОНИЧЕСКИЕ ИСТОЧНИКИ ИЗ БАЗЫ ЗНАНИЙ ТАРО:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ:\n"
        "1. Ты только что выложила расклад Таро! Дай глубокий, детальный, острый и честный профессиональный разбор каждой позиции, Дна колоды, Квинтэссенции и баланса стихий в своём фирменном стиле «стервочки» Арканы (помни, что сейчас конец 2026 года, впереди 2027 год).\n"
        "2. Обязательно связывай выпавшие карты, Дно колоды и Квинтэссенцию со школами Таро (Уэйт RWS, Таро Тота Кроули, Марсельская традиция Папюса, Орден Золотой Зари), а расхождения между школами выноси в цитату (`> ...`).\n"
        "3. Используй чёткое форматирование: подзаголовки `### Заголовок`, акценты `**жирным шрифтом**`, цитаты `> ...`."
    )

    llm_answer = await call_llm(ARCANA_SYSTEM_PROMPT, prompt, temperature=0.58, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 40:
        return llm_answer.strip()

    return build_offline_tarot_synthesis(spread, rag_passages)
