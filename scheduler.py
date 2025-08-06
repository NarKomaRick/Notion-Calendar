import asyncio
from datetime import datetime, timezone
from database import Database
from bot import bot
import logging

logger = logging.getLogger(__name__)

async def send_with_retry(chat_id, text, max_retries=3, delay=2):
    for attempt in range(max_retries):
        try:
            await bot.send_message(chat_id, text)
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания (попытка {attempt+1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
    return False

async def check_reminders():
    db = Database()
    while True:
        try:
            tasks = await db.get_tasks_for_reminders()
            
            logger.info(f"Найдено задач для напоминания: {len(tasks)}")
            
            for task in tasks:
                text = f"⏰ Напоминание!\nЗадача: {task['task']}"
                success = await send_with_retry(task['user_id'], text)
                
                if success:
                    await db.mark_reminder_sent(task['id'])
                    logger.info(f"Напоминание для задачи {task['id']} отправлено")
                else:
                    logger.error(f"Не удалось отправить напоминание для задачи {task['id']}")
        
        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")
        
        await asyncio.sleep(60)

async def start_scheduler():
    asyncio.create_task(check_reminders())