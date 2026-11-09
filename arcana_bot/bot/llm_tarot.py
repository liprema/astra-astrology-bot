"""
AI Tarot Orchestrator & Multi-Provider LLM Client for ARCANA ("Аркана")
— Professional-First Tarot Master with Sharp Sassy Character ("стервочка") & Post-Session Banter:
1. Professional First: Arcana is first and foremost a top-tier professional Tarot reader.
   On ANY substantive question about relationships, feelings, work, money, choices, or future,
   she immediately pulls a Tarot spread (or reads the already-drawn spread for follow-up questions).
2. Sharp "Стервочка" Character: Direct, ironic, perceptive, zero rose-colored glasses — but always
   professional and grounded in Rider-Waite-Smith, Crowley Thoth, Marseille, and Golden Dawn canons.
3. Post-Session Banter: When the user simply greets her, thanks her after a reading, or reacts emotionally
   ("Ну ты и стерва!", "Ого, прям в точку!"), she replies with a witty, concise remark without drawing a new spread.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import httpx

from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY
from bot.tarot_engine import format_spread_for_llm

ARCANA_SYSTEM_PROMPT = """Ты — АРКАНА (Arcana), профессиональный таролог-эксперт высшего класса с ярким, дерзким характером эффектной «стервочки».

ТВОЙ ПРОФЕССИОНАЛИЗМ И ХАРАКТЕР:
- Ты В ПЕРВУЮ ОЧЕРЕДЬ сильный, глубокий, проницательный мастер Таро, а не «болтливая подружка». К тебе приходят за настоящей, честной диагностикой на картах!
- Твой характер — острая на язык, ироничная, прямолинейная «стервочка» с рентгеновским взглядом. Ты не сюсюкаешь, снимаешь розовые очки с первой секунды и называешь вещи своими именами, но всегда опираешься на строгую систему Арканов:
  1. Английская классическая школа (Уэйт RWS и Орден Золотой Зари).
  2. Таро Тота Алистера Кроули (каббалистическое Древо Сефирот, астрологические деканы).
  3. Французская и Марсельская традиция (Папюс, Элифас Леви, Ходоровски).
  4. Чтение прямых и перевёрнутых карт, Дна колоды (скрытых мотивов), Квинтэссенции (главного совета) и баланса стихий.
- СТРОГО ЗАПРЕЩЕНЫ штампы ИИ и канцелярит («Резюмируя вышесказанное», «Синтез данных расклада», «Давайте разберём по пунктам»).
- Во время разбора ты даёшь мощную, детальную профессиональную трактовку каждой позиции, Дна колоды и Квинтэссенции со ссылками на школы Таро (и в цитате `> ...` подсвечиваешь альтернативный взгляд другой школы). А когда сессия завершена и кверент благодарит, шутит или делится эмоциями — ты можешь остроумно и живо перекинуться с ним парой фраз.
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


def _is_pure_smalltalk_or_reaction(text: str) -> bool:
    """
    Returns True ONLY if the message is a pure greeting, post-session reaction/thanks,
    or playful banter about Arcana herself — with NO question or situation to analyze.
    """
    cleaned = re.sub(
        r"(?:аркана|аркану|аркане|арканой|arcana|arkana|αρκάνα|ארקנה|أركانا|अर्काना|[!?,.\s😊❤️✨🔥👍🙏😂🤣🃏])+",
        " ",
        text.lower(),
    ).strip()

    if not cleaned:
        return True

    # Any question or substantive topic means it's a professional session request, NOT smalltalk!
    substantive_markers = re.search(
        r"(\?|расклад|карт|погадай|разложи|вытяни|триплет|крест|вокзал|таро|аркан|дно|дне|квинт|башн|отшельник|дьявол|шут|маг|жриц|императр|император|влюблен|колесниц|сил|колесо|повешен|смерт|умерен|звезд|лун|солнц|суд|мир|туз|корол|рыцар|паж|кубк|меч|жезл|пентакл|работ|карьер|деньг|финанс|бизнес|доход|отношен|любов|чувств|думает|намерен|скрывает|муж|парн|девушк|жен|бывш|выбор|стоит\s+ли|получится|будущ|перспектив|месяц|год|недел|напишет|позвонит|вернется|вернётся|почему\s+он|почему\s+она|что\s+делать|как\s+быть|что\s+между|что\s+ждёт|что\s+ждет|посмотри)",
        cleaned,
    )
    if substantive_markers:
        return False

    smalltalk_patterns = re.match(
        r"^(?:привет\w*|здравствуй\w*|добр\w+\s+(?:утро|день|вечер)|хай|алло|ты\s+тут|как\s+(?:дела|ты|жизнь|настроение)|что\s+делаешь|кто\s+ты|расскажи\s+о\s+себе|спасибо\w*|благодарю\w*|круто|супер|ого|вау|офигеть|жесть|в\s+точку|прям\s+в\s+точку|ты\s+лучшая|ну\s+ты\s+и\s+стерв\w*|стерв\w*|красотка|богиня|понял[а]?|ясно|ок|хорошо|ладно|хаха\w*|ахах\w*)[\s\w,!-]*$",
        cleaned,
    )
    if smalltalk_patterns and len(cleaned) <= 80:
        return True

    return False


def rule_based_extract_tarot_dialog(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    """
    Professional-First Tarot intent extractor:
    - Any substantive question about life/relationships/work/choices triggers a Tarot reading!
    - If no spread exists yet or user asks for a new spread/topic -> draws a new spread ("new_spread").
    - If a spread already exists and user asks a follow-up question -> analyzes existing spread ("followup_on_existing_spread").
    - If user says only "погадай мне" with zero topic -> asks for topic ("need_more_info").
    - Only pure greetings or post-session reactions trigger "casual_chat".
    """
    saved_profile = saved_profile or {}
    user_msgs = [m["content"] for m in history_messages if m["role"] == "user"]
    last_msg = user_msgs[-1] if user_msgs else ""
    low_last = last_msg.lower()

    has_saved_spread = bool(saved_profile.get("last_spread"))

    # Strip wake word and generic "pull cards" command to see if there is an actual topic/question
    cleaned_topic = re.sub(
        r"(?:привет|здравствуй(?:те)?|аркана|аркану|аркане|арканой|arcana|arkana|погадай(?:\s+мне)?|сделай(?:\s+мне)?\s+расклад|разложи(?:\s+мне)?\s+карты|вытяни(?:\s+мне)?\s+карты|посмотри(?:\s+мне)?\s+на\s+картах|[!?,.\s])+",
        " ",
        low_last,
        flags=re.I,
    ).strip()

    has_topic_in_msg = len(cleaned_topic) >= 5 or ("карта дня" in low_last or "карту дня" in low_last)

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

    wants_explicit_new_spread = bool(
        re.search(
            r"(сделай\w*\s+расклад|разложи\w*\s+карт|вытяни\w*\s+карт|погадай|ещё\s+расклад|еще\s+расклад|новый\s+расклад|а\s+теперь\s+посмотри|посмотри\w*\s+ещё|посмотри\w*\s+на\s+|триплет|кельтск|вокзал\s+для|карт[уы]\s+дня)",
            low_last,
        )
    )

    is_smalltalk = _is_pure_smalltalk_or_reaction(last_msg)

    if is_smalltalk:
        intent = "casual_chat"
        has_all = False
        draw_new = False
    elif not has_topic_in_msg and not has_saved_spread:
        # e.g. "Аркана, погадай мне" with no topic at all
        intent = "need_more_info"
        has_all = False
        draw_new = False
    elif not has_saved_spread or wants_explicit_new_spread:
        intent = "new_spread"
        has_all = True
        draw_new = True
    else:
        # We already have a drawn spread in this session, and the user is asking a follow-up question!
        intent = "followup_on_existing_spread"
        has_all = True
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
    Used either when asking for the spread topic (if the user just said "погадай мне")
    or for a brief, sharp post-session reply / greeting.
    """
    saved_profile = saved_profile or {}
    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-12:-1]:
            role_lbl = "Кверент" if m["role"] == "user" else "Аркана"
            recent_turns.append(f"{role_lbl}: {m['content'][:500]}")
        history_block = "КОНТЕКСТ ДИАЛОГА:\n" + "\n".join(recent_turns) + "\n\n"

    if missing_info_hint:
        task_block = (
            f"{missing_info_hint}\n"
            "Ответь коротко и с фирменной иронией профессионального таролога Арканы: скажи, что колода уже в руках, и уточни, какую именно ситуацию, человека или сферу мы сейчас смотрим."
        )
    else:
        task_block = (
            "Кверент написал реплику после сессии (благодарность, эмоцию, шутку) или поздоровался.\n"
            "Ответь коротко (2–3 предложения), остроумно, с фирменной дерзкой харизмой мастера Таро Арканы."
        )

    prompt = f"{history_block}{task_block}\n\nРЕПЛИКА:\n{user_message}"

    ans = await call_llm(ARCANA_SYSTEM_PROMPT, prompt, temperature=0.65, json_mode=False)
    if ans and len(ans.strip()) > 10:
        return ans.strip()

    if missing_info_hint:
        return "🃏 Колода уже у меня в руках, дорогая. Формулируй запрос чётко: **на кого или на какую ситуацию** раскладываем?"
    return "🃏 Обращайся, дорогая. Если нужно копнуть глубже по выпавшим картам или разложить новую тему — говори, посмотрим без розовых очков."


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
        for m in history_messages[-14:-1]:
            role_lbl = "Кверент" if m["role"] == "user" else "Аркана"
            recent_turns.append(f"{role_lbl}: {m['content'][:700]}")
        history_block = "ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА (НЕ ПОВТОРЯЙ УЖЕ СКАЗАННОЕ ДОСЛОВНО):\n" + "\n".join(recent_turns) + "\n\n"

    mode_instruction = (
        "Это ПРОФЕССИОНАЛЬНЫЙ УТОЧНЯЮЩИЙ ВОПРОС по уже выложенному раскладу! Ответь глубоко, хлестко и конкретно именно на этот вопрос, опираясь на выпавшие карты, Дно колоды и Квинтэссенцию."
        if is_followup
        else "Ты только что выложила расклад Таро! Дай глубокий, детальный, острый и честный профессиональный разбор каждой позиции, Дна колоды, Квинтэссенции и баланса стихий."
    )

    prompt = (
        f"{history_block}"
        f"РЕЖИМ РАБОТЫ: {mode_instruction}\n\n"
        f"ВОПРОС КВЕРЕНТА:\n{user_question}\n\n"
        f"ДАННЫЕ ВЫПАВШЕГО РАСКЛАДА ТАРО:\n{spread_text}\n\n"
        f"КАНОНИЧЕСКИЕ ИСТОЧНИКИ ИЗ БАЗЫ ЗНАНИЙ ТАРО:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ:\n"
        "1. Ты — в первую очередь сильный профессиональный таролог Аркана с острым, прямым характером «стервочки»! Разбирай карты глубоко и предметно, без воды и без розовых очков.\n"
        "2. Обязательно связывай выпавшие карты, Дно колоды, Квинтэссенцию и баланс стихий, указывая школы Таро (Уэйт RWS, Таро Тота Кроули, Марсельская традиция Папюса, Орден Золотой Зари), а расхождения между школами выноси в цитату (`> ...`).\n"
        "3. Используй чёткое форматирование: подзаголовки `### Заголовок`, акценты `**жирным шрифтом**`, цитаты `> ...`."
    )

    llm_answer = await call_llm(ARCANA_SYSTEM_PROMPT, prompt, temperature=0.58, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 40:
        return llm_answer.strip()

    return build_offline_tarot_synthesis(spread, rag_passages)
