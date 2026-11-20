import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import aiohttp
from database import EcosystemDB

class BridgeService:
    def __init__(self, db: EcosystemDB, chrona_token: Optional[str] = None, kairos_token: Optional[str] = None):
        self.db = db
        self.chrona_token = chrona_token
        self.kairos_token = kairos_token

    async def send_tg_notification(self, bot_token: str, chat_id: int, text: str):
        """Отправка системного сообщения через Telegram Bot API"""
        if not bot_token or not chat_id:
            return
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, json=payload)
        except Exception as e:
            print(f"Failed to send notification: {e}")

    async def notify_chrona_about_new_project(self, project_id: int, user_chat_id: Optional[int] = None):
        """Кайрос сообщает Хроне о новом проекте в работе"""
        project = self.db.get_project_by_id(project_id)
        if not project:
            return

        # Создаем базовый дедлайн-слот в расписании Хроны
        deadline_date = project["deadline"]
        if not deadline_date:
            # По умолчанию ставим спринт на 14 дней вперед
            deadline_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

        self.db.add_schedule_item(
            user_role=project["owner"],
            title=f"🎯 Дедлайн/Майлстоун проекта: {project['title']}",
            category="business",
            project_id=project_id,
            scheduled_date=deadline_date,
            user_id=user_chat_id
        )

        message = (
            f"✨ <b>Хрона на связи!</b>\n\n"
            f"Кайрос только что зафиксировал новый проект в работе: <b>«{project['title']}»</b>!\n"
            f"📌 Категория: {project['category']}\n"
            f"📅 Предварительный дедлайн: {deadline_date}\n\n"
            f"Я уже занесла майлстоун в расписание и запланирую рабочие слоты, чтобы вы не перегружались учёбой."
        )

        if self.chrona_token and user_chat_id:
            await self.send_tg_notification(self.chrona_token, user_chat_id, message)

        return message

    def get_workload_status_for_kairos(self, user_role: str = "polina") -> str:
        """Кайрос проверяет у Хроны текущую загрузку на ближайшие 7 дней"""
        today = datetime.now().strftime("%Y-%m-%d")
        next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        summary = self.db.get_user_workload_summary(user_role, today, next_week)

        academic = summary.get("academic", 0)
        business = summary.get("business", 0)

        if academic > 4:
            return f"⚠️ Внимание: У тебя сейчас плотная академическая неделя ({academic} учебных слотов/задач). Не бери слишком большой скоуп по кодингу прямо сейчас!"
        elif academic + business == 0:
            return "🟢 График на неделю свободен! Отличное время для глубокого вайбкодинг-спринта."
        else:
            return f"ℹ️ Баланс на неделю: {academic} учебных задач, {business} проектных задач. Идём по графику."

def should_bot_handle_message(text: str, bot_name: str, bot_username: Optional[str] = None) -> bool:
    """
    Определяет, должен ли конкретный бот обрабатывать сообщение из группы:
    - Если есть явное обращение (@username или имя) -> обрабатывает только упомянутый бот.
    - Если упомянут другой бот -> текущий игнорирует.
    - Если обращение общее:
        * Тематика учёбы, расписания, дедлайнов, заботы -> Хрона
        * Тематика геймдева, Steam, Яндекс.Игр, кода, бизнеса -> Кайрос
        * Иначе (болтовня, нейтральное) -> доступно обоим (решает atomic claim в БД).
    """
    t = (text or "").lower().strip()
    if not t:
        return False

    chrona_direct = any(k in t for k in ["хрона", "chrona", "хроночк", "хроне", "хрону"])
    kairos_direct = any(k in t for k in ["кайрос", "kairos", "кайросу", "кайроса", "кайросом"])

    if bot_username:
        u = bot_username.lower().replace("@", "")
        if f"@{u}" in t:
            return True
        if bot_name == "kairos" and ("@chrona" in t or "chrona_bot" in t):
            return False
        if bot_name == "chrona" and ("@kairos" in t or "kairos_bot" in t):
            return False

    if bot_name == "chrona":
        if chrona_direct:
            return True
        if kairos_direct:
            return False
    elif bot_name == "kairos":
        if kairos_direct:
            return True
        if chrona_direct:
            return False

    chrona_keywords = [
        "расписани", "дедлайн", "учеб", "зачет", "зачёт", "экзамен", 
        "сесси", "пара", "пары", "календар", "устал", "отдохн", "план на", "баланс", "тайминг", "сон", "график"
    ]
    kairos_keywords = [
        "steam", "стим", "акаш", "миф", "бог", "богов", "лор", "механик",
        "яндекс", "игры", "игра", "геймдев", "бизнес", "стартап", "идея", "код", "вайбкодинг", "mvp", "питч", "фич"
    ]

    c_score = sum(1 for k in chrona_keywords if k in t)
    k_score = sum(1 for k in kairos_keywords if k in t)

    if c_score > k_score:
        return bot_name == "chrona"
    elif k_score > c_score:
        return bot_name == "kairos"

    return True
