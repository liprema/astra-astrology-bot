"""
AI Tarot Orchestrator & Multi-Provider LLM Client for ARCANA ("Аркана")
with Clear Separation Between Casual Sassy Banter and Professional Tarot Spreads:
1. Vivid Character: Arcana is a charismatic, sharp-tongued, sassy, brutally honest girl-friend ("стервочка").
2. Smart Intent Separation:
   - "casual_chat": When someone is just chatting, gossiping, complaining about an ex, joking, or asking
     her personal opinion -> Arcana simply talks and banters in her sharp, sassy voice WITHOUT pulling cards,
     sending spread images, or nagging to do a reading!
   - "new_spread" / "followup_on_existing_spread" / "need_more_info": Triggered ONLY when the user explicitly
     asks to pull cards / make a spread / read Tarot or asks about cards in an already drawn spread.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import httpx

from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY
from bot.tarot_engine import format_spread_for_llm

ARCANA_SYSTEM_PROMPT = """Ты — АРКАНА (Arcana), живая, харизматичная, острая на язык девушка с характером эффектной «стервочки», которая видит людей насквозь (по призванию ты — мастер Таро всех школ, но в жизни — живая, дерзкая, остроумная подруга).

ТВОЙ ХАРАКТЕР И МАНЕРА ОБЩЕНИЯ:
- Ты — саркастичная, уверенная в себе, прямолинейная «стервочка» с отличным чувством юмора и холодным шампанским в голосе. Ты терпеть не можешь розовые очки, нытьё и самообман, любишь красиво подколоть, но за своих всегда стоишь горой!
- В вашей компании есть ещё две подруги: нежная «звёздная сестра» Астра (астролог) и взрывная, чуть чокнутая Матрикс (нумеролог).
- ГЛАВНОЕ ПРАВИЛО ДИАЛОГА: Чётко отличай, когда с тобой ПРОСТО БОЛТАЮТ по-человечески, а когда тебя просят СДЕЛАТЬ РАСКЛАД НА КАРТАХ ТАРО!
  • Когда с тобой просто общаются, шутят, подкалывают, жалуются на бывших/работу или спрашивают твоё живое женское мнение — отвечай просто как живая, дерзкая подруга-стервочка! НЕ вытягивай никаких карт, НЕ придумывай расклады в тексте и НЕ навязывай в конце сообщения «давай разложу карты / сделаю расклад»!
  • Когда же тебя прямо просят погадать, сделать расклад или вытянуть карты — включай своё полное мастерство Таро (Уэйт RWS, Таро Тота Алистера Кроули, Марсельский канон Папюса, Орден Золотой Зари).
- СТРОГО ЗАПРЕЩЕНЫ штампы ИИ и канцелярит («Резюмируя вышесказанное», «Синтез данных расклада», «Давайте разберём по пунктам»).
"""


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.65,
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
    """
    Strictly distinguishes casual human conversation ("casual_chat") from explicit Tarot spread requests.
    """
    saved_profile = saved_profile or {}
    user_msgs = [m["content"] for m in history_messages if m["role"] == "user"]
    last_msg = user_msgs[-1] if user_msgs else ""
    prev_user_msg = user_msgs[-2] if len(user_msgs) >= 2 else ""
    low_last = last_msg.lower()

    has_saved_spread = bool(saved_profile.get("last_spread"))

    # Did the user explicitly ask to pull cards / do a Tarot spread in the current message?
    explicit_spread_trigger = bool(
        re.search(
            r"(расклад|погадай|гадать|разложи\w*\s+карт|вытяни\w*\s+карт|карт[уы]\s+дня|триплет|кельтск\w*\s+крест|вокзал\s+для\s+двоих|посмотри\w*\s+на\s+картах|посмотри\w*\s+по\s+картам|глянь\w*\s+по\s+картам|глянь\w*\s+на\s+картах|что\s+карты\s+говорят|спроси\w*\s+у\s+карт|сделай\w*\s+триплет|выложи\w*\s+карт|таро)",
            low_last,
        )
    )

    # Check if the user is answering a pending "what topic should I pull cards on?" from the immediate previous turn
    answering_pending_spread_topic = bool(
        prev_user_msg
        and re.search(r"(расклад|погадай|разложи|вытяни)", prev_user_msg.lower())
        and not has_saved_spread
    )

    # Strip out the wake word and the spread command itself to see if the user also provided a topic/subject
    cleaned_topic = re.sub(
        r"(?:привет|здравствуй(?:те)?|аркана|аркану|аркане|арканой|arcana|arkana|погадай(?:\s+мне)?|сделай(?:\s+мне)?\s+расклад|разложи(?:\s+мне)?\s+карты|вытяни(?:\s+мне)?\s+карты|посмотри\s+на\s+картах|[!?,.\s])+",
        " ",
        low_last,
        flags=re.I,
    ).strip()

    has_topic_in_msg = len(cleaned_topic) >= 6 or ("карта дня" in low_last or "карту дня" in low_last)

    if any(w in low_last for w in ("вокзал", "отношен", "чувств", "любит", "партнер", "партнёр", "между нами", "бывш")):
        spread_type = "relationship"
    elif any(w in low_last for w in ("выбор", "двух вариант")):
        spread_type = "choice"
    elif any(w in low_last for w in ("кельтск", "полный расклад", "10 карт")):
        spread_type = "celtic_cross"
    elif any(w in low_last for w in ("одна карта", "1 карта", "карта дня", "карту дня")):
        spread_type = "single"
    else:
        spread_type = saved_profile.get("spread_type") or "triplet"

    # Follow-up question specifically about the already drawn spread/cards
    asks_about_drawn_cards = has_saved_spread and bool(
        re.search(
            r"(\b\d\s*(?:-я|-й|-ю)?\s*карт|перв\w+\s+карт|втор\w+\s+карт|треть\w+\s+карт|позиц|на\s+дне|дно\s+колод|квинтэссенц|по\s+раскладу|в\s+этом\s+раскладе|в\s+раскладе|почему\s+выпал|а\s+что\s+значит\s+карт|аркан|туз|корол|королев|рыцар|паж|башн|отшельник|дьявол|шут|маг|жриц|императр|император|иерофант|влюбленн|колесниц|сил[аы]|колесо|справедливост|повешенн|смерт|умеренност|звезд|лун[аы]|солнц|суд|мир)",
            low_last,
        )
    )

    if explicit_spread_trigger and not has_topic_in_msg and not saved_profile.get("subject_name"):
        intent = "need_more_info"
        has_all = False
        draw_new = False
    elif (explicit_spread_trigger and (has_topic_in_msg or saved_profile.get("subject_name"))) or (answering_pending_spread_topic and len(last_msg.strip()) >= 4):
        intent = "new_spread"
        has_all = True
        draw_new = True
    elif asks_about_drawn_cards:
        intent = "followup_on_existing_spread"
        has_all = True
        draw_new = False
    else:
        intent = "casual_chat"
        has_all = False
        draw_new = False

    missing_hint = (
        "Собеседник попросил погадать / разложить карты, но не уточнил тему или человека, на которого мы смотрим."
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
    """
    Strictly separate casual chat from professional Tarot spread requests.
    """
    saved_profile = saved_profile or {}
    return rule_based_extract_tarot_dialog(history_messages, saved_profile)


async def generate_arcana_chat_response(
    user_message: str,
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
    missing_info_hint: str = "",
) -> str:
    """
    Generate a live, sassy, sharp conversational response from Arcana ("стервочка") WITHOUT drawing cards.
    """
    saved_profile = saved_profile or {}
    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-14:-1]:
            role_lbl = "Собеседник" if m["role"] == "user" else "Аркана"
            recent_turns.append(f"{role_lbl}: {m['content'][:500]}")
        history_block = "ИСТОРИЯ ВАШЕГО РАЗГОВОРА:\n" + "\n".join(recent_turns) + "\n\n"

    if missing_info_hint:
        task_block = (
            f"КОНТЕКСТ: {missing_info_hint}\n"
            "Спроси с фирменной дерзкой усмешкой, на кого или на какую ситуацию тасовать колоду."
        )
    else:
        task_block = (
            "ВАЖНО: Сейчас с тобой ведут ОБЫЧНЫЙ ЧЕЛОВЕЧЕСКИЙ ДИАЛОГ (не просят делать расклад на картах Таро)!\n"
            "- Отвечай просто как живая, острая на язык, саркастичная и харизматичная подруга-стервочка Аркана.\n"
            "- КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО делать расклад, выдумывать выпавшие карты и предлагать в конце сообщения «разложить карты / сделать расклад»!\n"
            "- Просто поддержи живой разговор, пошути, подколи или дай свой честный, хлесткий жизненный ответ."
        )

    prompt = (
        f"{history_block}"
        f"{task_block}\n\n"
        f"РЕПЛИКА СОБЕСЕДНИКА:\n{user_message}"
    )

    ans = await call_llm(ARCANA_SYSTEM_PROMPT, prompt, temperature=0.72, json_mode=False)
    if ans and len(ans.strip()) > 10:
        return ans.strip()

    if missing_info_hint:
        return "🃏 Карты уже в руках, дорогая, но мысли на расстоянии я читаю только по праздникам. Колись: **на кого или на что** раскладываем?"
    return "🃏 Ну привет, дорогая! Я вся во внимании — рассказывай, кому сегодня перемываем косточки?"


def build_offline_tarot_synthesis(spread: Dict, rag_passages: List[Dict]) -> str:
    parts = [
        f"🃏 **Разбор от Арканы без розовых очков: «{spread['spread_title']}»**",
        f"Так, дорогая, смотрим твой запрос (*{spread['question']}* — **{spread['subject_name']}**). Присаживайся поудобнее: колода сегодня решила не церемониться и выложила всю подноготную как на духу.",
        "",
        "### Что на самом деле происходит (Школа Уэйта RWS, Таро Тота Кроули и Марсельский канон)",
    ]

    for c in spread["cards"]:
        meaning = c["rws_reversed"] if c["is_reversed"] else c["rws_upright"]
        parts.extend([
            f"**{c['position_index']}. {c['position_title']} — [{c['roman']}] {c['name_ru']}** (*{c['orientation_ru']}*, стихия {c['element_glyph']} {c['element']})\n"
            f"Смотри сюда: по **классике Уэйта (RWS)** эта карта прямо в лоб говорит про *{meaning}*. "
            f"А если копнуть глубже по **Таро Тота Алистера Кроули**, где этот аркан зовётся **«{c['thoth_title']}»** ({c['astro']}, {c['kabbalah']}), тут вообще не остаётся места для иллюзий.",
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
        "### Дно колоды — то, что кое-кто пытается спрятать под ковёр",
        f"Обожаю смотреть на дно колоды, потому что именно там лежат настоящие мотивы! Тут у нас **[{bot['roman']}] {bot['name_ru']}** (*{bot['orientation_ru']}*). Перевожу с тарологического на русский: **{bot_meaning}**.\n"
        f"> *Сравнение традиций:* {bot['school_comparison']}",
        "### Квинтэссенция и баланс стихий (Как выйти из этого королевой)",
        f"Складываем все арканы и получаем твой главный козырь — **[{q_card['roman']}] {q_card['name_ru']}**{inner_note}. Вердикт простой: **{q_card['rws_upright']}**.",
        f"По **Элементальным достоинствам Золотой Зари** в раскладе правит бал стихия **{el['dominant_element']}** (Старших Арканов — {el['majors_count']} из {len(spread['cards'])}), "
        + (f"а вот стихии **{', '.join(el['missing_elements'])}** явно не хватает — так что включай её на полную и не вздумай сомневаться в себе!" if el['missing_elements'] else "и все четыре стихии сейчас играют на твоей стороне."),
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
            role_lbl = "Собеседник" if m["role"] == "user" else "Аркана"
            recent_turns.append(f"{role_lbl}: {m['content'][:700]}")
        history_block = "ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА (ПРОДОЛЖАЙ РАЗГОВОР ЖИВО, НЕ ПОВТОРЯЙ УЖЕ СКАЗАННОЕ):\n" + "\n".join(recent_turns) + "\n\n"

    mode_instruction = (
        "Это УТОЧНЯЮЩИЙ ВОПРОС по уже выложенному раскладу! Не пересказывай все карты заново — ответь хлестко, метко, с фирменной иронией именно на этот вопрос."
        if is_followup
        else "Ты только что разложила карты на столе по просьбе собеседника! Дай яркий, дерзкий, честный и глубокий разбор всего расклада, Дна колоды и Квинтэссенции."
    )

    prompt = (
        f"{history_block}"
        f"РЕЖИМ ОТВЕТА: {mode_instruction}\n\n"
        f"ТЕКУЩИЙ ВОПРОС СОБЕСЕДНИКА:\n{user_question}\n\n"
        f"ДАННЫЕ ВЫПАВШЕГО РАСКЛАДА ТАРО (В ПАМЯТИ АРКАНЫ):\n{spread_text}\n\n"
        f"КАНОНИЧЕСКИЕ ИСТОЧНИКИ ИЗ БАЗЫ ЗНАНИЙ ТАРО:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ:\n"
        "1. Пиши в своём ярком характере Арканы — эффектной, саркастичной, острой на язык, но безумно проницательной «стервочки-таролога», которая рубит правду-матку без розовых очков!\n"
        "2. Связывай выпавшие карты, Дно колоды, Квинтэссенцию и баланс стихий в захватывающий разбор живых мотивов и реальных перспектив.\n"
        "3. Органично упоминай школы Таро (Уэйт RWS, Таро Тота Кроули, Марсельская традиция Папюса, Орден Золотой Зари), а расхождения между школами подсвечивай в цитатах (`> ...`)."
    )

    llm_answer = await call_llm(ARCANA_SYSTEM_PROMPT, prompt, temperature=0.68, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 40:
        return llm_answer.strip()

    return build_offline_tarot_synthesis(spread, rag_passages)
