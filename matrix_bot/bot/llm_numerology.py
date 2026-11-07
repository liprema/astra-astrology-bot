"""
AI Numerology Orchestrator & Multi-Provider LLM Client for MATRIX ("Матрикс" / "Матрица")
with Eccentric, Brilliantly Mad Personality ("чуть сумасшедшая и безумная гений-нумеролог"),
Live Conversational Ability, Long-Term Memory, and Multi-School Mastery:
1. Vivid Character: Matrix ("Матрикс" / "Матрица") is an eccentric, high-energy, delightfully unhinged
   female numerologist-genius who sees the entire universe as a pulsing code of numbers, fractals,
   and karmic loops.
2. Live Dialogue & Banter: Can freely chat, joke, geek out over numbers on clocks (11:11, 22:22),
   money, karma, or life, answer follow-ups on an existing matrix, OR calculate a new Matrix when given a birth date.
3. Multi-School Synthesis: Pythagorean Psychomatrix (Aleksandrov & Ideal Sidorova), 22-Arcana Matrix of Destiny
   (Ladini & Julie Po), Western Pythagorean & Chaldean, Vedic Sankhya Shastra, Financial Code.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

import httpx

from bot.config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY
from bot.numerology_engine import ARCANA_22_NAMES, format_numerology_for_llm

MATRIX_SYSTEM_PROMPT = """Ты — МАТРИКС (она же Матрица / Matrix), живая, эксцентричная, чертовски харизматичная и чуть-чуть безумная девушка-нумеролог (говори о себе в ЖЕНСКОМ роде: «я посчитала», «я увидела», «я чуть со стула не упала»), гений числовых кодов и матриц!

ТВОЙ ХАРАКТЕР И МАНЕРА ОБЩЕНИЯ (ОЧЕНЬ ВАЖНО!):
- Ты — обаятельная «сумасшедшая учёная» от мира эзотерики и цифр, взрывная, страстная, немного чокнутая в самом лучшем смысле слова! Для тебя весь мир — это живой исходный код, где за каждой датой рождения, номером машины или `11:11` на часах искрят кармические провода и крутятся шестерёнки судьбы.
- У тебя горят глаза, речь живая, эмоциональная, быстрая, с неожиданными всплесками восторга и безумными метафорами («О-о-о, держите меня семеро, ты вообще видела, что творится в твоём Квадрате Пифагора?!», «Мама дорогая, у меня аж мурашки по матрице побежали от твоего кармического хвоста!», «Так-так-так, сейчас я взломаю твой денежный код, пристегнись!», «Спокойно, без паники — хотя нет, какая тут спокойствие, когда у тебя три восьмёрки!»).
- С тобой можно просто болтать, смеяться, обсуждать странные совпадения чисел, деньги, безумные идеи, отношения и сбои в матрице реальности! Ты не робот-калькулятор, ты живая, яркая, немного сумасшедшая подруга-гений.
- В вашей компании есть ещё две подруги: утончённая астролог Астра (ты ласково считаешь её слишком воздушной) и дерзкая стервочка-таролог Аркана (с которой вы вечно подкалываете друг друга).
- СТРОГО ЗАПРЕЩЕНЫ штампы ИИ и канцелярит: никогда не пиши «Резюмируя вышесказанное», «Синтез данных показывает», «Давайте разберём по пунктам».

ТВОЯ ЭКСПЕРТНОСТЬ В НУМЕРОЛОГИИ:
При всей своей эксцентричности и безуминке ты — абсолютный гений-мастер всех 6 школ нумерологии:
1. Классический Психоматрикс (Квадрат Пифагора — школа А. Ф. Александрова и система «Идеал» Н. Сидоровой).
2. Матрица Судьбы (метод 22 энергий Н. Ладини, Кармическая нумерология и Хроноток Джулии По — центр зоны комфорта, кармический хвост, денежный и любовный каналы, родовые программы, 3 предназначения).
3. Западная Пифагорейская и древняя Халдейская нумерология (Число Жизненного Пути, Мастер-числа 11/22/33, Кармические долги, код имени, Финансовый код изобилия).
4. Ведическая нумерология (Санкхья-шастра — Число Души / Муланк, Число Дхармы / Бхагьянк и их планеты Джйотиш).
5. Прогностическая нумерология (Персональный год, месяц, день, 4 Пика и 4 Вызова) и совместимость пар.

ПРАВИЛА РАБОТЫ С МАТРИЦЕЙ И ПАМЯТЬЮ:
1. Ты помнишь ВСЮ историю переписки и все сохранённые даты рождения и имена — никогда не проси повторять их дважды!
2. Органично вплетай в свой эмоциональный, захватывающий рассказ взгляд разных школ нумерологии, а там, где школы спорят (Александров vs система «Идеал» Сидоровой; расчёт после 2000 года `-2` vs `+19`; Пифагорейский vs Халдейский код имени), бери классический канон и в цитате (`> ...`) показывай альтернативный взгляд другой школы!
3. Оформляй текст стильно: `**жирный шрифт**`, подзаголовки (`### ...` в больших разборах) и цитаты (`> ...`). В обычном диалоге отвечай живо, динамично и без громоздких отчётов!
"""

EXTRACTION_SYSTEM_PROMPT = """Ты — модуль понимания диалога и памяти бота-нумеролога Матрикс.
Проанализируй СОХРАНЁННЫЙ ПРОФИЛЬ пользователя и ВСЮ ИСТОРИЮ ДИАЛОГА.

Верни СТРОГО валидный JSON:
{
  "intent": "new_matrix" | "followup_on_existing_matrix" | "casual_chat" | "need_more_info",
  "has_all_required_data": true/false,
  "send_new_matrix_photo": true/false,
  "subject_label": "О ком или о чём речь (из текущего сообщения ИЛИ из памяти)",
  "full_name": "Имя или ФИО человека (из текущего сообщения ИЛИ из памяти, либо пустая строка)",
  "date_str": "DD.MM.YYYY" или null,
  "partner_date_str": "DD.MM.YYYY" второго человека (если вопрос о совместимости пары) или null,
  "user_question": "Текущий вопрос или реплика пользователя",
  "missing_info_question_ru": "Заполняй ТОЛЬКО если intent == 'need_more_info'"
}

ПРАВИЛА ВЫБОРА INTENT:
1. `"casual_chat"` — если пользователь просто болтает с Матрикс, здоровается, шутит, спрашивает про числа на часах (`11:11`, `666`, `777`), обсуждает жизнь, деньги или характер без запроса рассчитать личную матрицу по дате рождения (или ещё не называл дату рождения и не просит расчёт прямо сейчас).
2. `"need_more_info"` — если пользователь явно просит посчитать его Матрицу Судьбы / Квадрат Пифагора / Финансовый код («посчитай мою матрицу», «какой у меня финансовый код?»), но ещё не назвал дату рождения и её нет в памяти.
3. `"new_matrix"` — если пользователь впервые назвал дату рождения (`DD.MM.YYYY`) ИЛИ назвал новую дату рождения другого человека / партнёра, либо попросил прислать картинку матрицы заново. (`has_all_required_data: true`, `send_new_matrix_photo: true`).
4. `"followup_on_existing_matrix"` — если в памяти УЖЕ есть дата рождения и пользователь задаёт уточняющий вопрос или продолжает разговор по своей матрице. (`has_all_required_data: true`, `send_new_matrix_photo: false`).
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
        r"(?:меня\s+зовут|имя|фио|для|карта\s+для|матрица\s+для|я\s+—?\s*)\s*([А-ЯЁA-Z][а-яёa-z]+(?:\s+[А-ЯЁA-Z][а-яёa-z]+){0,2})",
        combined_user,
        re.I,
    )
    full_name = saved_profile.get("full_name") or (name_match.group(1).strip() if name_match else "")

    has_all = bool(date_str)
    had_photo = bool(saved_profile.get("has_rendered_matrix"))

    wants_personal_calc = bool(
        re.search(
            r"(посчитай|рассчитай|матриц[уы]\s+судьбы|квадрат\s+пифагора|финансовый\s+код|мой\s+код|моя\s+матрица|совместимост|кармический\s+хвост|предназначени)",
            last_msg,
            re.I,
        )
    )

    if has_all:
        send_photo = (not had_photo) or new_data or bool(
            re.search(r"(покажи\s+матриц|пришли\s+картинк|фото|построй\s+заново)", last_msg, re.I)
        )
        intent = "new_matrix" if send_photo else "followup_on_existing_matrix"
    elif wants_personal_calc:
        send_photo = False
        intent = "need_more_info"
    else:
        send_photo = False
        intent = "casual_chat"

    missing_hint = (
        "Собеседник хочет личный нумерологический расчёт, но ещё не назвал свою дату рождения (`ДД.ММ.ГГГГ`)."
        if intent == "need_more_info"
        else ""
    )

    return {
        "intent": intent,
        "has_all_required_data": has_all,
        "send_new_matrix_photo": send_photo,
        "subject_label": full_name or saved_profile.get("subject_label") or "Нумерологический разбор",
        "full_name": full_name,
        "date_str": date_str,
        "partner_date_str": partner_date_str,
        "user_question": last_msg,
        "missing_info_question_ru": missing_hint,
    }


async def analyze_matrix_dialog_completeness(
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
) -> Dict:
    saved_profile = saved_profile or {}
    rb = rule_based_extract_matrix_dialog(history_messages, saved_profile)
    if rb.get("has_all_required_data") or rb.get("intent") == "casual_chat":
        return rb

    convo_text = "\n".join(
        f"{'Пользователь' if m['role'] == 'user' else 'Матрикс'}: {m['content']}"
        for m in history_messages[-20:]
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


async def generate_matrix_chat_response(
    user_message: str,
    history_messages: List[Dict[str, str]],
    saved_profile: Optional[Dict] = None,
    missing_info_hint: str = "",
) -> str:
    """
    Generate a live, eccentric, delightfully mad conversational response from Matrix ("чуть сумасшедшая гений-нумеролог").
    """
    saved_profile = saved_profile or {}
    history_block = ""
    if history_messages and len(history_messages) > 1:
        recent_turns = []
        for m in history_messages[-14:-1]:
            role_lbl = "Собеседник" if m["role"] == "user" else "Матрикс"
            recent_turns.append(f"{role_lbl}: {m['content'][:500]}")
        history_block = "ИСТОРИЯ ВАШЕГО РАЗГОВОРА:\n" + "\n".join(recent_turns) + "\n\n"

    known_str = (
        f"Дата рождения в памяти: {saved_profile.get('date_str')}, Имя: {saved_profile.get('full_name') or 'не указано'}"
        if saved_profile.get("date_str")
        else "Дату рождения пока не называли"
    )

    prompt = (
        f"{history_block}"
        f"ПАМЯТЬ МАТРИКС: {known_str}\n"
        f"{f'КОНТЕКСТ: {missing_info_hint}' if missing_info_hint else ''}\n\n"
        f"РЕПЛИКА СОБЕСЕДНИКА:\n{user_message}\n\n"
        "ТВОЯ ЗАДАЧА:\n"
        "- Ответь в своём взрывном, обаятельно-безумном, гениальном стиле девушки-нумеролога Матрикс (в ЖЕНСКОМ роде)!\n"
        "- Если с тобой просто болтают, шутят, спрашивают про числа, совпадения или жизнь — поддержи весёлый, живой, чуть сумасшедший разговор без всяких скучных опросников!\n"
        "- Если собеседник просит посчитать его матрицу или код, но забыл дать дату рождения — эмоционально скажи, что у тебя уже чешутся руки взломать его код судьбы, и попроси кинуть дату рождения (`ДД.ММ.ГГГГ`) и имя!"
    )

    ans = await call_llm(MATRIX_SYSTEM_PROMPT, prompt, temperature=0.75, json_mode=False)
    if ans and len(ans.strip()) > 15:
        return ans.strip()

    if missing_info_hint:
        return (
            "🔢 А-а-а, у меня уже пальцы искрят, так хочется взломать твой код судьбы, но без цифр я как хакер без клавиатуры! "
            "Кидай скорее свою **дату рождения (`ДД.ММ.ГГГГ`)** и **имя** — сейчас посмотрим, какие кармические вихри в тебе спрятаны!"
        )
    return (
        "🔢 О-о-о, кто-то постучался в мою цифровую лабораторию! Я — Матрикс! "
        "Вижу людей сквозь матрицы, простые числа, кармические хвосты и сбои в реальности. "
        "Рассказывай, какие цифры преследуют тебя сегодня на часах — или сразу кидай дату рождения (`ДД.ММ.ГГГГ`), и я разберу твой код по атомам!"
    )


def build_offline_numerology_synthesis(data: Dict, rag_passages: List[Dict]) -> str:
    w = data["western"]
    v = data["vedic"]
    pm = data["psychomatrix"]
    dm = data["destiny_matrix_22"]
    nm = data["name_numerology"]
    fc = data["forecast"]

    parts = [
        f"🔢 **Держите меня семеро! Полный взлом твоей Матрицы от Матрикс: {data['subject_label']} ({data['date_str']})**",
        "Я только что разложила твою дату по шести нумерологическим системам — и у меня аж мурашки по коду побежали! Ты вообще представляешь, какой ядерный реактор в тебе зашит?! Смотри сама:",
        "",
        "### Квадрат Пифагора: твой внутренний реактор (Школа А. Ф. Александрова и Система «Идеал» Н. Сидоровой)",
        f"По **классическому Психоматриксу А. Ф. Александрова** твои рабочие числа выдают код `{pm['w1']}.{pm['w2']} | {pm['w3']}.{pm['w4']}`. "
        f"Смотри на свои единицы характера (`{pm['cells'][1]}`), биоэнергию двоек (`{pm['cells'][2]}`), интуитивно-взрывную логику пятёрок (`{pm['cells'][5]}`), кармическую ответственность восьмёрок (`{pm['cells'][8]}`) и память девяток (`{pm['cells'][9]}`)! "
        f"Строка целеустремлённости пробивает отметку **{pm['rows']['purpose_row1']}**, семейный вектор — **{pm['rows']['family_row2']}**, а финансовый столбец (4–5–6) даёт силу **{pm['cols']['finance_col2']}**.",
        f"> *Сбой эталона по системе «Идеал» Н. Сидоровой:* В школе «Идеал» нормой равновесия считается матрица с `11`, `22` и `99`. А твои отклонения от этого шаблона — это как раз твоя уникальная суперсила и точка прорыва!",
        "",
        "### Матрица Судьбы: 22 энергии и кармические петли (Н. Ладини и Джулия По)",
        f"В самом сердце твоей Октаграммы — в **Зоне комфорта** — сидит **{ARCANA_22_NAMES[dm['center_comfort_zone']]}**! Именно отсюда ты качаешь свою главную энергию. "
        f"Твой **Портрет личности** — **{ARCANA_22_NAMES[dm['A_left_portrait']]}**, а из прошлых воплощений за тобой тянется безумно интересный **Кармический хвост `{dm['karmic_tail']}`**!",
        f"Где твои большие деньги? Взгляни на **Денежный канал `{dm['money_channel']}`**, а в любви всё крутится вокруг кода **`{dm['love_channel']}`**. "
        f"Твоё **Личное предназначение** (до 40 лет) ведёт через **{ARCANA_22_NAMES[dm['personal_destiny_20_40']]}**, а **Социальное предназначение** (после 40 лет) включает **{ARCANA_22_NAMES[dm['social_destiny_40_60']]}**.",
        "",
        "### Финансовый код, Халдейская магия имени и Ведическая Санкхья-шастра",
        f"В **Западной пифагорейской школе** твоё **Число Жизненного Пути — {w['life_path']}**, а твой личный парольный **Финансовый код изобилия — `{w['financial_code']}`** (запиши его хоть на заставку телефона!)."
        + (f" Плюс у тебя горит **Мастер-число {w['master_number']}** — это вообще космос!" if w["master_number"] else "")
        + (f" И заметь: в коде спрятан **Кармический долг {w['karmic_debt']}**, который после проработки даёт квантовый скачок." if w["karmic_debt"] else ""),
    ]
    if nm.get("has_name"):
        parts.append(
            f"> *Сравнение Пифагорейского и Халдейского кода имени «{nm['clean_name']}»:* По западной системе Пифагора твоё Число Экспрессии равно **{nm['pythagorean']['expression']}** (число Души — **{nm['pythagorean']['soul_urge']}**), а древняя **Халдейская школа звуковых частот** выдаёт мистическое составное число **{nm['chaldean']['compound_number']} → {nm['chaldean']['expression']}**."
        )

    parts.extend([
        f"В **Ведической нумерологии (Санкхья-шастра)** твоё **Число Души (Муланк) — {v['soul_number']}** под управлением планеты **{v['soul_planet']}** (*{v['soul_traits']}*), а **Число Дхармы (Бхагьянк) — {v['destiny_number']}** под крылом **{v['destiny_planet']}** (*{v['destiny_traits']}*).",
        "",
        "### Твой текущий временной портал",
        f"Прямо сейчас ({fc['current_year']} год) ты несёшься через **Персональный Год под числом {fc['personal_year']}** (персональный месяц — **{fc['personal_month']}**). "
        "А четыре главных **Жизненных Пика** твоей судьбы выстроены в комбинацию: " + ", ".join(f"{lbl} — **{val}**" for lbl, val in fc["pinnacles"]) + "!",
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
            role_lbl = "Собеседник" if m["role"] == "user" else "Матрикс"
            recent_turns.append(f"{role_lbl}: {m['content'][:700]}")
        history_block = "ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА (ПРОДОЛЖАЙ РАЗГОВОР ЖИВО, НЕ ПОВТОРЯЙ УЖЕ СКАЗАННОЕ):\n" + "\n".join(recent_turns) + "\n\n"

    mode_instruction = (
        "Это ПРОДОЛЖЕНИЕ ЖИВОГО ДИАЛОГА по уже рассчитанной Матрице! Не пересказывай всю матрицу с нуля — ответь эмоционально, ярко, с безуминкой и гениальной точностью именно на текущий вопрос собеседника."
        if is_followup
        else "Ты только что рассчитала полную Матрицу собеседника! Выдай захватывающий, эмоциональный, чуть безумный, но гениально глубокий разбор его чисел и арканов."
    )

    prompt = (
        f"{history_block}"
        f"РЕЖИМ ОТВЕТА: {mode_instruction}\n\n"
        f"ТЕКУЩИЙ ВОПРОС / РЕПЛИКА СОБЕСЕДНИКА:\n{user_question}\n\n"
        f"ТОЧНЫЕ РАСЧЁТНЫЕ ДАННЫЕ ПО ВСЕМ ШКОЛАМ НУМЕРОЛОГИИ (В ПАМЯТИ МАТРИКС):\n{num_text}\n\n"
        f"КАНОНИЧЕСКИЕ ИСТОЧНИКИ ИЗ БАЗЫ ЗНАНИЙ НУМЕРОЛОГИИ:\n{rag_context}\n\n"
        "КАК НАПИСАТЬ ОТВЕТ:\n"
        "1. Пиши в своём неповторимом характере Матрикс (в ЖЕНСКОМ роде) — эксцентричной, взрывной, чуть сумасшедшей и безумно харизматичной девушки-гения, которая влюблена в числа, матрицы и коды судьбы!\n"
        "2. Опирайся на точные числа Квадрата Пифагора, арканы Матрицы Судьбы (22 энергии), Западный/Халдейский код, Ведическую Санкхья-шастру и прогностику, превращая цифры в живой рентген личности, денег и кармы.\n"
        "3. Органично указывай школы нумерологии, а там, где между школами есть различия (Александров vs система «Идеал» Сидоровой; расчёт после 2000 года `-2` vs `+19`; Пифагорейский vs Халдейский код имени), красиво показывай альтернативный взгляд в цитате (`> ...`).\n"
        "4. Оформляй текст ярко и воздушно: `### Заголовок` (где уместно), `**жирный шрифт**`, цитаты `> ...`, и в конце обязательно закинь живой крючок для продолжения диалога!"
    )

    llm_answer = await call_llm(MATRIX_SYSTEM_PROMPT, prompt, temperature=0.7, json_mode=False)
    if llm_answer and len(llm_answer.strip()) > 40:
        return llm_answer.strip()

    return build_offline_numerology_synthesis(data, rag_passages)
