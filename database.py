import aiosqlite
from datetime import datetime, timedelta, timezone
import logging
import json
import pytz

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path=None):
        from config import DB_PATH
        self.db_path = db_path or DB_PATH

    async def execute(self, query, params=(), commit=False):
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(query, params)
            if commit:
                await conn.commit()
            return await cursor.fetchall()

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as conn:
            # Таблица пользователей
            await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                mode TEXT DEFAULT 'meeting',
                reminder INTEGER DEFAULT 60,
                timezone TEXT DEFAULT 'Europe/Moscow',
                theme TEXT DEFAULT 'default',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ''')
            
            # Таблица дней календаря
            await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_calendar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                year INTEGER,
                month INTEGER,
                day INTEGER,
                status TEXT DEFAULT 'free',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );
            ''')
            
            # Таблица задач
            await conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                year INTEGER,
                month INTEGER,
                day INTEGER,
                task TEXT,
                time TEXT,
                reminder INTEGER,
                reminder_time DATETIME,
                reminder_sent BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );
            ''')
            
            # Таблица групповых запросов
            await conn.execute('''
            CREATE TABLE IF NOT EXISTS group_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_ids TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );
            ''')
            
            await conn.commit()

    async def user_exists(self, user_id):
        result = await self.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return bool(result)
    
    async def add_user(self, user_id, username, full_name):
        await self.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
            (user_id, username or '', full_name or ''),
            commit=True
        )
    
    async def set_user_mode(self, user_id, mode):
        await self.execute(
            "UPDATE users SET mode = ? WHERE user_id = ?",
            (mode, user_id),
            commit=True
        )
    
    async def get_user_mode(self, user_id):
        result = await self.execute("SELECT mode FROM users WHERE user_id = ?", (user_id,))
        return result[0][0] if result else 'meeting'
    
    async def set_user_reminder(self, user_id, reminder):
        await self.execute(
            "UPDATE users SET reminder = ? WHERE user_id = ?",
            (reminder, user_id),
            commit=True
        )
    
    async def get_user_reminder(self, user_id):
        result = await self.execute("SELECT reminder FROM users WHERE user_id = ?", (user_id,))
        return result[0][0] if result else 60
    
    async def set_user_timezone(self, user_id, timezone):
        await self.execute(
            "UPDATE users SET timezone = ? WHERE user_id = ?",
            (timezone, user_id),
            commit=True
        )
    
    async def get_user_timezone(self, user_id):
        result = await self.execute("SELECT timezone FROM users WHERE user_id = ?", (user_id,))
        return result[0][0] if result else 'Europe/Moscow'
    
    async def set_user_theme(self, user_id, theme):
        await self.execute(
            "UPDATE users SET theme = ? WHERE user_id = ?",
            (theme, user_id),
            commit=True
        )
    
    async def get_user_theme(self, user_id):
        result = await self.execute("SELECT theme FROM users WHERE user_id = ?", (user_id,))
        return result[0][0] if result else 'default'
    
    async def mark_day_busy(self, user_id, year, month, day):
        await self.execute(
            "INSERT OR REPLACE INTO user_calendar (user_id, year, month, day, status) "
            "VALUES (?, ?, ?, ?, 'busy')",
            (user_id, year, month, day),
            commit=True
        )
    
    async def mark_day_free(self, user_id, year, month, day):
        await self.execute(
            "DELETE FROM user_calendar "
            "WHERE user_id = ? AND year = ? AND month = ? AND day = ?",
            (user_id, year, month, day),
            commit=True
        )
        await self.execute(
            "DELETE FROM tasks "
            "WHERE user_id = ? AND year = ? AND month = ? AND day = ?",
            (user_id, year, month, day),
            commit=True
        )
    
    async def add_task(self, user_id, year, month, day, task_text, task_time, reminder):
        # Рассчитываем время напоминания в UTC
        user_timezone = await self.get_user_timezone(user_id)
        try:
            tz = pytz.timezone(user_timezone)
            task_datetime = tz.localize(datetime(
                year, month, day,
                int(task_time.split(':')[0]),
                int(task_time.split(':')[1])
            ))
            reminder_time = task_datetime - timedelta(minutes=reminder)
            reminder_time = reminder_time.astimezone(pytz.utc)
        except Exception as e:
            logger.error(f"Error calculating reminder time: {e}")
            # Fallback: текущее время + reminder минут
            reminder_time = datetime.now(timezone.utc) + timedelta(minutes=reminder)
        
        await self.execute(
            "INSERT INTO tasks (user_id, year, month, day, task, time, reminder, reminder_time) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, year, month, day, task_text, task_time, reminder, reminder_time),
            commit=True
        )
    
    async def get_tasks_for_day(self, user_id, year, month, day):
        result = await self.execute(
            "SELECT id, task, time FROM tasks "
            "WHERE user_id = ? AND year = ? AND month = ? AND day = ?",
            (user_id, year, month, day)
        )
        return [{'id': row[0], 'task': row[1], 'time': row[2]} for row in result]
    
    async def get_task_by_id(self, task_id):
        result = await self.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,)
        )
        if result:
            return {
                'id': result[0][0],
                'user_id': result[0][1],
                'year': result[0][2],
                'month': result[0][3],
                'day': result[0][4],
                'task': result[0][5],
                'time': result[0][6],
                'reminder': result[0][7],
                'reminder_time': result[0][8]
            }
        return None
    
    async def delete_task(self, task_id):
        task = await self.get_task_by_id(task_id)
        if not task:
            return False
        
        await self.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,),
            commit=True
        )
        
        remaining = await self.execute(
            "SELECT COUNT(*) FROM tasks "
            "WHERE user_id = ? AND year = ? AND month = ? AND day = ?",
            (task['user_id'], task['year'], task['month'], task['day'])
        )
        if remaining and remaining[0][0] == 0:
            await self.execute(
                "DELETE FROM user_calendar "
                "WHERE user_id = ? AND year = ? AND month = ? AND day = ?",
                (task['user_id'], task['year'], task['month'], task['day']),
                commit=True
            )
        
        return True
    
    async def get_user_calendar(self, user_id, month, year):
        days_result = await self.execute(
            "SELECT day, status FROM user_calendar "
            "WHERE user_id = ? AND year = ? AND month = ?",
            (user_id, year, month)
        )
        
        tasks_result = await self.execute(
            "SELECT day, COUNT(*) as count FROM tasks "
            "WHERE user_id = ? AND year = ? AND month = ? "
            "GROUP BY day",
            (user_id, year, month)
        )
        
        calendar_data = {}
        for row in days_result:
            day = row[0]
            calendar_data[day] = {
                'status': row[1],
                'task_count': 0
            }
        
        for row in tasks_result:
            day = row[0]
            if day in calendar_data:
                calendar_data[day]['task_count'] = row[1]
            else:
                calendar_data[day] = {'status': 'busy', 'task_count': row[1]}
        
        return calendar_data
    
    async def reset_user_calendar(self, user_id, year, month):
        await self.execute(
            "DELETE FROM user_calendar "
            "WHERE user_id = ? AND year = ? AND month = ?",
            (user_id, year, month),
            commit=True
        )
        await self.execute(
            "DELETE FROM tasks "
            "WHERE user_id = ? AND year = ? AND month = ?",
            (user_id, year, month),
            commit=True
        )
    
    async def get_user_ids_by_usernames(self, usernames):
        if not usernames:
            return []
        
        placeholders = ', '.join(['?'] * len(usernames))
        query = f"SELECT user_id FROM users WHERE username IN ({placeholders})"
        result = await self.execute(query, usernames)
        return [row[0] for row in result]
    
    async def find_common_free_days(self, user_ids, year, month):
        if not user_ids or len(user_ids) > 20:
            return []
        
        import calendar
        _, days_in_month = calendar.monthrange(year, month)
        all_days = set(range(1, days_in_month + 1))
        
        busy_days = set()
        for user_id in user_ids:
            result = await self.execute(
                "SELECT day FROM user_calendar "
                "WHERE user_id = ? AND year = ? AND month = ? AND status = 'busy'",
                (user_id, year, month)
            )
            calendar_busy = {row[0] for row in result}
            
            result = await self.execute(
                "SELECT DISTINCT day FROM tasks "
                "WHERE user_id = ? AND year = ? AND month = ?",
                (user_id, year, month))
            tasks_busy = {row[0] for row in result}
            
            user_busy_days = calendar_busy | tasks_busy
            busy_days |= user_busy_days
        
        free_days = all_days - busy_days
        return sorted(free_days)
    
    async def get_tasks_for_reminders(self):
        now_utc = datetime.now(timezone.utc)
        result = await self.execute(
            "SELECT id, user_id, task FROM tasks "
            "WHERE reminder_sent = 0 AND reminder_time <= ?",
            (now_utc,)
        )
        return [{'id': row[0], 'user_id': row[1], 'task': row[2]} for row in result]
    
    async def mark_reminder_sent(self, task_id):
        await self.execute(
            "UPDATE tasks SET reminder_sent = 1 WHERE id = ?",
            (task_id,),
            commit=True
        )
    
    async def cleanup_old_data(self):
        two_months_ago = datetime.now() - timedelta(days=60)
        await self.execute(
            "DELETE FROM user_calendar WHERE updated_at < ?",
            (two_months_ago,),
            commit=True
        )
        await self.execute(
            "DELETE FROM tasks WHERE created_at < ?",
            (two_months_ago,),
            commit=True
        )

async def init_db():
    db = Database()
    await db.init_db()
    return db