import sqlite3
import json
from datetime import datetime, date
from typing import List, Dict, Optional, Any

class EcosystemDB:
    def __init__(self, db_path: str = "data/ecosystem.db"):
        import os
        from pathlib import Path
        Path(db_path).resolve().parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Таблица проектов
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL, -- 'steam_myth', 'yandex_games', 'custom_business'
                status TEXT NOT NULL DEFAULT 'in_progress', -- 'ideation', 'in_progress', 'mvp', 'released', 'archived'
                owner TEXT NOT NULL, -- 'polina', 'husband', 'both'
                deadline TEXT,
                meta_info TEXT, -- JSON с доп. информацией
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)

            # Таблица расписания и задач
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedule_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_role TEXT NOT NULL, -- 'polina' or 'husband'
                title TEXT NOT NULL,
                category TEXT NOT NULL, -- 'academic', 'business', 'rest', 'deadline'
                project_id INTEGER REFERENCES projects(id),
                scheduled_date TEXT NOT NULL, -- YYYY-MM-DD
                time_slot TEXT, -- e.g. '14:00-16:00'
                status TEXT DEFAULT 'pending', -- 'pending', 'done', 'cancelled'
                created_at TEXT NOT NULL
            )
            """)

            # Таблица состояний пользователей (текущий выбранный режим)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                active_mode TEXT NOT NULL DEFAULT 'steam_myth', -- 'steam_myth', 'yandex_games', 'consulting', or 'project_<id>'
                active_project_id INTEGER,
                chat_history TEXT DEFAULT '[]' -- JSON с последними сообщениями
            )
            """)
                        # Таблица захвата сообщений для групповых чатов (предотвращение дублирования)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_message_claims (
                chat_id INTEGER,
                message_id INTEGER,
                bot_name TEXT NOT NULL,
                claimed_at TEXT NOT NULL,
                PRIMARY KEY (chat_id, message_id)
            )
            ''')
            conn.commit()

    # --- Методы для Проектов (Кайрос) ---
    def add_project(self, code: str, title: str, description: str, category: str, owner: str, deadline: Optional[str] = None, meta: Optional[Dict] = None) -> int:
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO projects (code, title, description, category, status, owner, deadline, meta_info, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'in_progress', ?, ?, ?, ?, ?)
            """, (code, title, description, category, owner, deadline, json.dumps(meta or {}, ensure_ascii=False), now, now))
            conn.commit()
            return cursor.lastrowid

    def get_active_projects(self, owner: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if owner:
                cursor.execute("SELECT * FROM projects WHERE status IN ('in_progress', 'mvp') AND (owner = ? OR owner = 'both') ORDER BY id DESC", (owner,))
            else:
                cursor.execute("SELECT * FROM projects WHERE status IN ('in_progress', 'mvp') ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_project_by_id(self, project_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_project_status(self, project_id: int, new_status: str):
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE projects SET status = ?, updated_at = ? WHERE id = ?", (new_status, now, project_id))
            conn.commit()

    # --- Методы для Расписания (Хрона) ---
    def add_schedule_item(self, user_role: str, title: str, category: str, scheduled_date: str, time_slot: Optional[str] = None, project_id: Optional[int] = None, user_id: Optional[int] = None) -> int:
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO schedule_items (user_id, user_role, title, category, project_id, scheduled_date, time_slot, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """, (user_id, user_role, title, category, project_id, scheduled_date, time_slot, now))
            conn.commit()
            return cursor.lastrowid

    def get_schedule_for_date(self, target_date: str, user_role: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_role:
                cursor.execute("SELECT s.*, p.title as project_title FROM schedule_items s LEFT JOIN projects p ON s.project_id = p.id WHERE s.scheduled_date = ? AND s.user_role = ? ORDER BY s.id ASC", (target_date, user_role))
            else:
                cursor.execute("SELECT s.*, p.title as project_title FROM schedule_items s LEFT JOIN projects p ON s.project_id = p.id WHERE s.scheduled_date = ? ORDER BY s.id ASC", (target_date,))
            return [dict(row) for row in cursor.fetchall()]

    def get_user_workload_summary(self, user_role: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """Возвращает сводку нагрузки: количество академических и бизнес задач за период"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT category, COUNT(*) as cnt 
            FROM schedule_items 
            WHERE user_role = ? AND scheduled_date BETWEEN ? AND ? 
            GROUP BY category
            """, (user_role, start_date, end_date))
            rows = cursor.fetchall()
            return {row["category"]: row["cnt"] for row in rows}

    # --- Состояния и Режимы ---
    def set_user_mode(self, user_id: int, mode: str, active_project_id: Optional[int] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO user_states (user_id, active_mode, active_project_id)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET active_mode = excluded.active_mode, active_project_id = excluded.active_project_id
            """, (user_id, mode, active_project_id))
            conn.commit()

    def get_user_mode(self, user_id: int) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_states WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {"active_mode": "steam_myth", "active_project_id": None}


    def try_claim_message(self, chat_id: int, message_id: int, bot_name: str) -> bool:
        """Атомарная попытка забрать сообщение себе. Возвращает True, если бот первый захватил сообщение."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                INSERT INTO group_message_claims (chat_id, message_id, bot_name, claimed_at)
                VALUES (?, ?, ?, ?)
                """, (chat_id, message_id, bot_name, now))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def is_message_claimed(self, chat_id: int, message_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT bot_name FROM group_message_claims WHERE chat_id = ? AND message_id = ?", (chat_id, message_id))
            return cursor.fetchone() is not None

    # --- История сообщений для памяти и контекста ---
    def add_chat_message(self, chat_id: int, user_id: int, role: str, content: str):
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TEXT
            )
            """)
            cursor.execute("""
            INSERT INTO messages (chat_id, user_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (chat_id, user_id, role, content, now))
            conn.commit()

    def get_chat_history(self, chat_id: int, limit: int = 15) -> List[Dict[str, str]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TEXT
            )
            """)
            cursor.execute("""
            SELECT role, content FROM messages
            WHERE chat_id = ?
            ORDER BY id DESC LIMIT ?
            """, (chat_id, limit))
            rows = cursor.fetchall()
            res = [dict(row) for row in rows]
            res.reverse()
            return res
