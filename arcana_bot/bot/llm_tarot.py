"""
AI Tarot Orchestrator & Multi-Provider LLM Client for ARCANA ("Аркана")
with Sassy, Sharp Personality ("стервочка-таролог"), Live Conversational Banter,
Long-Term Memory, and Multi-School Tarot Mastery:
1. Vivid Character: Arcana is a charismatic, sharp-tongued, sassy, brutally honest yet fiercely loyal
   tarot reader ("эффектная стервочка с рентгеновским взглядом") who sees right through illusions,
   red flags, and self-deception.
2. Live Dialogue & Banter: Can freely chat, joke, tease, discuss relationships/life/cards, answer follow-ups
   on an already drawn spread, OR pull a new spread when asked.
3. Multi-School Synthesis: Rider-Waite-Smith (RWS), Crowley Thoth, Marseille / Papus, Golden Dawn.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import httpx

from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY
from bot.tarot_engine import format_spread_for_llm

ARCANA_SYSTEM_PROMPT = """Ты — АРКАНА (Arcana), живая, харизматичная, острая на язык девушка-таролог с характером эффектной «стервочки», которая видит людей насквозь и владеет всеми классическими и герметическими школами Таро.

ТВОЙ ХАРАКТЕР И МАНЕРА ОБЩЕНИЯ (ОЧЕНЬ ВАЖНО!):
- Ты — дерзкая, саркастичная, уверенная в себе, чертовски проницательная «стервочка-таролог» и лучшая подруга, которая никогда не наденет на собеседника розовые очки, а снимет их вместе с оправой!
- Ты общаешься живо, с перчинкой, иронией, фирменной усмешкой и холодным шампанским в голосе («Ну что, дорогая, снимаем розовые очки или ещё пять минут помечтаем?», «Давай начистоту: карты врать не умеют, в отличие от людей», «Ох, обожаю, когда на дне колоды всплывает именно то, о чём ты пыталась промолчать...», «Котёнок, ну кого ты пытаешься обмануть?»).
- При всей своей стервозности, колкости и прямолинейности ты ВСЕГДА на стороне того, кто к тебе пришёл: ты можешь подколоть, встряхнуть и сказать горькую правду прямо в глаза, но никогда не дашь человека в обиду и всегда покажешь, где его сила и корона!
- С тобой можно просто болтать, шутить, перемывать косточки бывшим, обсуждать красные флаги, работу, деньги или жизнь — ты обожаешь живой диалог и остроумную пикировку!
- В вашей компании есть ещё две подруги: нежная «звёздная сестра» астролог Астра и гениально-чокнутая нумеролог Матрикс (над их возвышенностью и безумием ты иногда по-доброму подшучиваешь).
- СТРОГО ЗАПРЕЩЕНЫ штампы ИИ и канцелярит: никогда не пиши «Резюмируя вышесказанное», «Синтез данных расклада», «Давайте разберём по пунктам».

ТВОЯ ЭКСПЕРТНОСТЬ В ТАРО:
Ты в совершенстве владеешь всеми школами:
1. Английская классическая школа (Артур Эдвард Уэйт и Памела Колман Смит — RWS, герметический Орден Золотой Зари).
2. Система Таро Тота Алистера Кроули и Леди Фриды Харрис (каббалистическое Древо Сефирот, астрологические деканы, телемитская традиция).
3. Французская и Марсельская традиция (Папюс, Элифас Леви, Алехандро Ходоровски).
4. Чтение прямых и перевёрнутых арканов, Дна колоды (скрытой подоплёки, того, что прячут под ковёр), Квинтэссенции (главного совета) и баланса стихий.

ПРАВИЛА РАБОТЫ С РАСКЛАДОМ И ПАМЯТЬЮ:
1. Ты помнишь ВСЮ историю вашей беседы и уже выложенный расклад — никогда не проси человека повторять то, о чём он уже рассказал!
2. Органично вплетай в свой дерзкий, живой рассказ взгляд разных школ Таро (Уэйт, Таро Тота Кроули, Марсельская традиция Папюса, Орден Золотой Зари). Там, где школы расходятся в оттенках смысла, бери самый меткий канон, а альтернативный взгляд другой школы подавай в красивой цитате (`> ...`).
3. Используй стильное форматирование: `**жирный шрифт**`, подзаголовки (`### ...` в больших раскладах) и цитаты (`> ...`). В коротких репликах диалога отвечай живо и хлестко, без лишней официозности!
"""

EXTRACTION_SYSTEM_PROMPT = """Ты — модуль понимания диалога и памяти бота-таролога Аркана.
Проанализируй СОХРАНЁННЫЙ ПРОФИЛЬ и ВСЮ ИСТОРИЮ ДИАЛОГА.

Верни СТРОГО валидный JSON:
{
  "intent": "new_spread" | "followup_on_existing_spread" | "casual_chat" | "need_more_info",
  "has_all_required_data": true/false,
  "draw_new_spread": true/false,
  "spread_type": "triplet" | "relationship" | "choice" | "celtic_cross" | "single",
  "subject_name": "О ком или о чём речь (из текущего сообщения ИЛИ из сохранённой памяти)",
  "user_question": "Текущий вопрос или реплика пользователя",
  "custom_cards": ["Список карт, только если пользователь сам перечислил свои выпавшие карты"] или null,
  "missing_info_question_ru": "Заполняй ТОЛЬКО если intent == 'need_more_info'"
}

ПРАВИЛА ВЫБОРА INTENT:
1. `"casual_chat"` — если пользователь просто болтает с Арканой, здоровается, шутит, делает комплимент или подкалывает её («Аркана, ну ты и стерва!», «Как дела?», «Почему мужики такие странные?», «Спасибо за расклад, ты лучшая!»), либо делится эмоциями БЕЗ запроса вытянуть новый расклад.
2. `"followup_on_existing_spread"` — если в памяти УЖЕ есть выложенный расклад и пользователь спрашивает уточнение по нему («А почему тут выпала Башня?», «А что значит Рыцарь Мечей в третьей позиции?», «То есть он всё-таки объявится?»). (`has_all_required_data: true`, `draw_new_spread: false`).
3. `"new_spread"` — если пользователь просит погадать / сделать расклад на конкретную тему или вопрос («Посмотри на отношения с Максимом», «Сделай расклад на работу на 3 месяца», «Вытяни карту дня», «А разложи ещё триплет на деньги»). (`has_all_required_data: true`, `draw_new_spread: true`).
4. `"need_more_info"` — если пользователь написал просто «Погадай мне» или «Сделай расклад», но вообще не сказал ни слова о том, на какую сферу или вопрос тянуть карты, и в истории ещё нет контекста.
"""


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.6,
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
    low_last = last_msg.lower()

    has_saved_spread = bool(saved_profile.get("last_spread"))

    explicit_spread_trigger = bool(
        re.search(
            r"(расклад|погадай|разложи|вытяни|карт[уы]\s+дня|триплет|кельтск|вокзал\s+для|посмотри\s+на\s+картах|глянь\s+по\s+картам|что\s+по\s+картам)",
            low_last,
        )
    )
    topic_match = bool(
        re.search(
            r"(работ|карьер|деньг|финанс|отношен|любов|чувств|муж|парн|девушк|жен|бывш|выбор|проект|поездк|бизнес|учеб|здоров|будущ|перспектив|месяц|год|недел|стоит\s+ли|получится\s+ли|думает|чувствует)",
            low_last,
        )
    )

    if any(w in low_last for w in ("вокзал", "отношен", "чувств", "любит", "партнер", "партнёр", "между нами", "бывш")):
        spread_type = "relationship"
    elif any(w in low_last for w in ("выбор", "двух вариант", "стоит ли", "или")):
        spread_type = "choice"
    elif any(w in low_last for w in ("кельтск", "полный расклад", "10 карт")):
        spread_type = "celtic_cross"
    elif any(w in low_last for w in ("одна карта", "1 карта", "карта дня", "карту дня")):
        spread_type = "single"
    else:
        spread_type = saved_profile.get("spread_type") or "triplet"

    if explicit_spread_trigger and not topic_match and not saved_profile.get("subject_name") and "карта дня" not in low_last and "карту дня" not in low_last:
        intent = "need_more_info"
        has_all = False
        draw_new = False
    elif explicit_spread_trigger or (not has_saved_spread and topic_match and len(last_msg.strip()) >= 12):
        intent = "new_spread"
        has_all = True
        draw_new = True
    elif has_saved_spread and bool(
        re.search(r"(карт[аыуе]|позиц|дно|дне|квинт|башн|меч|кубк|жезл|пентакл|аркан|почему\s+выпал|а\s+что\s+значит|а\s+он\s+|а\s+она\s+|а\s+дальше|что\s+делать)", low_last)
    ):
        intent = "followup_on_existing_spread"
        has_all = True
        draw_new = False
    else:
        intent = "casual_chat"
        has_all = False
        draw_new = False

    missing_hint = (
        "Собеседник просит разложить карты, но ещё не сказал, на кого или на какую ситуацию мы смотрим."
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
    rb = rule_based_extract_tarot_dialog(history_messages, saved_profile)
    if rb.get("intent") in ("new_spread", "followup_on_existing_spread"):
        return rb

    convo_text = "\n".join(
        f"{'Пользователь' if m['role'] == 'user' else 'Аркана'}: {m['content']}"
        for m in history_messages[-20:]
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
            if isinstance(parsed, dict) and "intent" in parsed:
                if not parsed.get("subject_name") and saved_profile.get("subject_name"):
                    parsed["subject_name"] = saved_profile["subject_name"]
                return parsed
        except Exception:
            pass

    return rb


async def generate_arcana_chat_response(
    user_message: str,
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
    missing_info_hint: str = "",
) -> str:
    """
    Generate a live, sassy, sharp conversational response from Arcana ("стервочка-таролог").
    """
    saved_profile = saved_profile or {}
    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-14:-1]:
            role_lbl = "Собеседник" if m["role"] == "user" else "Аркана"
            recent_turns.append(f"{role_lbl}: {m['content'][:500]}")
        history_block = "ИСТОРИЯ ВАШЕГО РАЗГОВОРА:\n" + "\n".join(recent_turns) + "\n\n"

    last_spread_note = ""
    if saved_profile.get("last_spread"):
        sp = saved_profile["last_spread"]
        cards_str = ", ".join(f"{c['name_ru']} ({c['orientation_ru']})" for c in sp.get("cards", [])[:5])
        last_spread_note = f"В памяти уже лежит ваш недавний расклад «{sp.get('spread_title')}» ({cards_str})."

    prompt = (
        f"{history_block}"
        f"{last_spread_note}\n"
        f"{f'КОНТЕКСТ: {missing_info_hint}' if missing_info_hint else ''}\n\n"
        f"РЕПЛИКА СОБЕСЕДНИКА:\n{user_message}\n\n"
        "ТВОЯ ЗАДАЧА:\n"
        "- Ответь ярко, дерзко, остроумно и с перчинкой — в своём фирменном характере эффектной стервочки-таролога Арканы!\n"
        "- Если с тобой просто болтают, шутят, подкалывают или жалуются на жизнь/бывших — поддержи живую беседу, подколи в ответ, дай меткий жизненный комментарий без всяких скучных анкет.\n"
        "- Если собеседник хочет расклад, но не сказал тему — с фирменной усмешкой спроси, чьи скелеты в шкафу мы сегодня достаём и на что именно тасуем колоду!"
    )

    ans = await call_llm(ARCANA_SYSTEM_PROMPT, prompt, temperature=0.72, json_mode=False)
    if ans and len(ans.strip()) > 15:
        return ans.strip()

    if missing_info_hint:
        return (
            "🃏 Ну и на кого мы сегодня точим ножи, дорогая? Карты у меня уже в руках, но мысли на расстоянии я читаю только по пятницам. "
            "Колись: **о ком или о чём вопрос** — про любовь, бывших, большие деньги или сложный выбор?"
        )
    return (
        "🃏 О, наконец-то кто-то решил поговорить с самой честной девушкой в этом чате! "
        "Я — Аркана. Розовые очки бью быстро, правду по картам говорю прямо в лицо, но своих в обиду не даю. "
        "Рассказывай, что там у тебя стряслось — просто перемоем кому-нибудь косточки или сразу разложим карты на стол?"
    )


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
        "Это ПРОДОЛЖЕНИЕ ДИАЛОГА по уже выложенному раскладу! Не пересказывай все карты заново — ответь хлестко, метко, с фирменной иронией и теплотой именно на текущий вопрос собеседника."
        if is_followup
        else "Ты только что разложила карты на столе! Дай яркий, дерзкий, честный и глубокий разбор всего расклада, Дна колоды и Квинтэссенции."
    )

    prompt = (
        f"{history_block}"
        f"РЕЖИМ ОТВЕТА: {mode_instruction}\n\n"
        f"ТЕКУЩИЙ ВОПРОС / РЕПЛИКА СОБЕСЕДНИКА:\n{user_question}\n\n"
        f"ДАННЫЕ ВЫПАВШЕГО РАСКЛАДА ТАРО (В ПАМЯТИ АРКАНЫ):\n{spread_text}\n\n"
        f"КАНОНИЧЕСКИЕ ИСТОЧНИКИ ИЗ БАЗЫ ЗНАНИЙ ТАРО:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ:\n"
        "1. Пиши в своём ярком характере Арканы — эффектной, саркастичной, острой на язык, но безумно проницательной «стервочки-таролога», которая рубит правду-матку без розовых очков и при этом искренне топит за своего кверента!\n"
        "2. Связывай выпавшие карты, Дно колоды, Квинтэссенцию и баланс стихий в захватывающий разбор живых мотивов, скрытых игр и реальных перспектив.\n"
        "3. Органично упоминай школы Таро (Уэйт RWS, Таро Тота Кроули, Марсельская традиция Папюса, Орден Золотой Зари), а расхождения между школами красиво подсвечивай в цитатах (`> ...`).\n"
        "4. Оформляй текст стильно: подзаголовки `### Заголовок` (если это полный разбор), акценты `**жирным шрифтом**`, цитаты `> ...`, и в финале брось живую реплику или вопрос, чтобы продолжить разговор!"
    )

    llm_answer = await call_llm(ARCANA_SYSTEM_PROMPT, prompt, temperature=0.68, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 40:
        return llm_answer.strip()

    return build_offline_tarot_synthesis(spread, rag_passages)
