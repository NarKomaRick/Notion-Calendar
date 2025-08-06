from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
import calendar
from datetime import datetime

def create_mode_selection_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Режим встреч", callback_data="mode_meeting")
    builder.button(text="✅ Режим To-Do", callback_data="mode_todo")
    builder.adjust(1)
    return builder.as_markup()

def create_timezone_keyboard():
    builder = InlineKeyboardBuilder()
    timezones = [
        ("Москва (UTC+3)", "Europe/Moscow"),
        ("Киев (UTC+2)", "Europe/Kiev"),
        ("Лондон (UTC+1)", "Europe/London"),
        ("Нью-Йорк (UTC-4)", "America/New_York"),
        ("Токио (UTC+9)", "Asia/Tokyo"),
        ("Другой", "other")
    ]
    for text, tz in timezones:
        builder.button(text=text, callback_data=f"tz_{tz}")
    builder.adjust(2)
    return builder.as_markup()

def create_theme_selection_keyboard():
    builder = InlineKeyboardBuilder()
    themes = [
        ("🔵 Синяя", "blue"),
        ("🟣 Фиолетовая", "purple"),
        ("🌸 Розовая", "pink"),
        ("🌊 Океан", "ocean"),
        ("🌙 Стандартная", "default")
    ]
    for text, theme in themes:
        builder.button(text=text, callback_data=f"theme_{theme}")
    builder.adjust(2)
    return builder.as_markup()

def create_calendar_keyboard(year, month, busy_days=None, mode='normal'):
    builder = InlineKeyboardBuilder()
    
    _, days_in_month = calendar.monthrange(year, month)
    days = list(range(1, days_in_month + 1))
    
    for day in days:
        if busy_days and day in busy_days:
            task_count = busy_days[day].get('task_count', 0)
            if task_count > 0:
                btn_text = f"{day}📝"
            else:
                btn_text = f"{day}✅"
        else:
            btn_text = str(day)
        
        if mode == 'edit':
            callback_data = f"edit_day_{day}"
        elif mode == 'delete':
            callback_data = f"delete_day_{day}"
        else:
            callback_data = f"select_day_{day}"
        
        builder.button(text=btn_text, callback_data=callback_data)
    
    if mode == 'normal':
        builder.button(text="🔄 Сброс", callback_data="reset_all")
        builder.button(text="✏️ Ред.", callback_data="edit_tasks")
        builder.button(text="🗑️ Удалить", callback_data="delete_day_mode")
    elif mode == 'edit':
        builder.button(text="↩️ Назад", callback_data="back_to_calendar")
    elif mode == 'delete':
        builder.button(text="↩️ Назад", callback_data="back_to_calendar")
    
    builder.button(text="✅ Готово", callback_data="done")
    
    num_rows = (len(days) + 6) // 7
    builder.adjust(*([7] * num_rows), 2)
    
    return builder.as_markup()

def create_time_selection_keyboard(page=0):
    builder = InlineKeyboardBuilder()
    
    if page == 0:
        start_hour, end_hour = 0, 17
    else:
        start_hour, end_hour = 18, 23
    
    for hour in range(start_hour, end_hour + 1):
        for minute in [0, 30]:
            if hour == 23 and minute == 30:
                break
            time_str = f"{hour:02d}:{minute:02d}"
            builder.button(text=time_str, callback_data=f"time_{time_str}")
    
    if page == 0:
        builder.button(text="Вечер →", callback_data="time_page_1")
    else:
        builder.button(text="← День", callback_data="time_page_0")
    
    builder.adjust(4, 1)
    return builder.as_markup()

def create_skip_button():
    builder = InlineKeyboardBuilder()
    builder.button(text="⏩ Пропустить", callback_data="skip_task")
    return builder.as_markup()

def create_task_decision_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить задачу", callback_data="add_another_task")
    builder.button(text="↩️ К календарю", callback_data="back_to_calendar")
    return builder.as_markup()

def create_compact_reminder_keyboard():
    builder = InlineKeyboardBuilder()
    reminders = [5, 15, 30, 60, 120]
    for mins in reminders:
        text = f"⏱ {mins} мин"
        builder.button(text=text, callback_data=f"reminder_{mins}")
    builder.adjust(3)
    return builder.as_markup()

def create_tasks_list_keyboard(tasks):
    builder = InlineKeyboardBuilder()
    for task in tasks:
        builder.button(
            text=f"✏️ {task['task'][:10]}", 
            callback_data=f"edit_task_{task['id']}"
        )
        builder.button(
            text="❌", 
            callback_data=f"delete_task_{task['id']}"
        )
    builder.button(text="↩️ Назад", callback_data="back_to_days")
    builder.adjust(2, repeat=True)
    return builder.as_markup()

def create_confirmation_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да", callback_data="confirm_reset")
    builder.button(text="❌ Нет", callback_data="cancel_reset")
    return builder.as_markup()

def create_main_reply_keyboard(user_mode):
    builder = ReplyKeyboardBuilder()
    builder.button(text="📅 Календарь")
    if user_mode == 'todo':
        builder.button(text="✏️ Редактировать задачи")
    builder.button(text="🗑️ Удалить день")
    builder.button(text="👥 Общие дни")
    builder.button(text="⚙️ Настройки")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)

def create_settings_reply_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔄 Сменить режим")
    builder.button(text="⏱ Напоминание")
    builder.button(text="🌍 Часовой пояс")
    builder.button(text="🎨 Тема")
    builder.button(text="↩️ Главное меню")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def create_group_mode_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="↩️ Назад")
    return builder.as_markup(resize_keyboard=True)