import os
import aiohttp
from typing import Optional
from datetime import datetime, timedelta
from database import EcosystemDB

class BridgeService:
    def __init__(self, db: EcosystemDB, chrona_token: Optional[str] = None, kairos_token: Optional[str] = None):
        self.db = db
        self.chrona_token = chrona_token
        self.kairos_token = kairos_token

    async def send_tg_notification(self, bot_token: str, chat_id: int, text: str):
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
        project = self.db.get_project_by_id(project_id)
        if not project:
            return
        deadline_date = project["deadline"] or (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        self.db.add_schedule_item(
            user_role=project["owner"],
            title=f"🎯 Дедлайн проекта: {project['title']}",
            category="business",
            project_id=project_id,
            scheduled_date=deadline_date,
            user_id=user_chat_id
        )
        msg = f"✨ <b>Хрона на связи!</b>\nКайрос зафиксировал проект: <b>«{project['title']}»</b> (дедлайн: {deadline_date})!"
        if self.chrona_token and user_chat_id:
            await self.send_tg_notification(self.chrona_token, user_chat_id, msg)
        return msg

    def get_workload_status_for_kairos(self, user_role: str = "polina") -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        summary = self.db.get_user_workload_summary(user_role, today, next_week)
        academic = summary.get("academic", 0)
        business = summary.get("business", 0)
        if academic > 4:
            return f"⚠️ Плотная неделя по учёбе ({academic} задач). Не перегружайся кодингом!"
        elif academic + business == 0:
            return "🟢 График свободен! Отличное время для вайбкодинга."
        return f"ℹ️ Баланс: {academic} учебных, {business} проектных задач."

def should_bot_handle_message(message, bot_name: str, bot_info) -> bool:
    """
    Проверка, должен ли бот отвечать в группе:
    1. Ответ реплаем (reply_to_message) на сообщение этого бота -> 100% ДА!
    2. Упоминание по @username бота -> 100% ДА!
    3. Упоминание имени бота (Хрона / Кайрос) в тексте сообщения -> ДА!
    4. Если реплай на ДРУГОГО бота, а имя этого не названо -> НЕТ.
    5. Ключевые слова (только если нет реплая на другого бота).
    """
    text = (message.text or message.caption or "").lower().strip()
    reply = message.reply_to_message

    # 1. Проверяем реплай
    if reply and reply.from_user:
        if bot_info and reply.from_user.id == bot_info.id:
            return True
        # Если реплай сделан именно на ДРУГОГО БОТА (is_bot == True)
        if getattr(reply.from_user, "is_bot", False):
            replied_to_other = True
        else:
            # Реплай на обычного человека не блокирует триггеры
            replied_to_other = False
    else:
        replied_to_other = False

    if not text:
        return False

    chrona_direct = any(k in text for k in ["хрона", "chrona", "хроночк", "хроне", "хрону", "хроной"])
    kairos_direct = any(k in text for k in ["кайрос", "kairos", "кайросу", "кайроса", "кайросом", "кайросе"])

    if bot_info and bot_info.username:
        u = bot_info.username.lower().replace("@", "")
        if f"@{u}" in text:
            return True

    if bot_name == "kairos":
        if kairos_direct:
            return True
        if chrona_direct or replied_to_other:
            return False
    elif bot_name == "chrona":
        if chrona_direct:
            return True
        if kairos_direct or replied_to_other:
            return False

    # Тематические ключевые слова (срабатывают, только если не реплай чужому)
    if not replied_to_other:
        chrona_keywords = ["расписани", "дедлайн", "учеб", "зачет", "зачёт", "экзамен", "сесси", "пара", "пары", "календар", "тайминг"]
        kairos_keywords = ["steam", "стим", "акаш", "миф", "бог", "лор", "яндекс", "игры", "игра", "геймдев", "бизнес", "код", "вайбкодинг"]

        if any(k in text for k in chrona_keywords) and bot_name == "chrona":
            return True
        if any(k in text for k in kairos_keywords) and bot_name == "kairos":
            return True

    return False
