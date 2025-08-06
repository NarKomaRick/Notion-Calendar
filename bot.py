from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile
from database import Database
from calendar_generator import calendar_gen
from keyboards import *
from datetime import datetime
import config
import logging
import asyncio
import os
import re
import pytz
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()


user_last_messages: Dict[int, List[int]] = {}


class CalendarStates(StatesGroup):
    SELECT_TIMEZONE = State()
    MAIN_MENU = State()
    SELECT_MODE = State()
    CALENDAR_VIEW = State()
    DAY_SELECTED = State()
    TASK_NAME_INPUT = State()
    TASK_TIME_SELECT = State()
    TASK_REMINDER_SELECT = State()
    EDIT_TASKS_MODE = State()
    TASK_EDIT_MODE = State()
    DAY_TASKS_VIEW = State()
    GROUP_MODE = State()
    CONFIRM_RESET = State()
    SETTINGS_MODE = State()
    TIMEZONE_INPUT = State()
    DELETE_DAY_MODE = State()
    CONFIRM_DELETE_DAY = State()

async def cleanup_user_messages(chat_id: int):
    """Удаляет все сохраненные сообщения бота для пользователя"""
    if chat_id in user_last_messages:
        failed_deletions = []
        
        for msg_id in user_last_messages[chat_id]:
            try:
                await bot.delete_message(chat_id, msg_id)
            except Exception as e:
                logger.error(f"Ошибка при удалении сообщения {msg_id}: {e}")
                failed_deletions.append(msg_id)
        
        user_last_messages[chat_id] = failed_deletions
    else:
        user_last_messages[chat_id] = []

async def save_and_send(chat_id: int, **kwargs) -> types.Message:
    """Сохраняет сообщение перед отправкой и удаляет предыдущие"""
    await cleanup_user_messages(chat_id)
    message = await bot.send_message(chat_id, **kwargs)
    
    if chat_id not in user_last_messages:
        user_last_messages[chat_id] = []
    user_last_messages[chat_id].append(message.message_id)
    
    return message

async def save_and_send_photo(chat_id: int, **kwargs) -> types.Message:
    """Аналогично для фото"""
    await cleanup_user_messages(chat_id)
    message = await bot.send_photo(chat_id, **kwargs)
    
    if chat_id not in user_last_messages:
        user_last_messages[chat_id] = []
    user_last_messages[chat_id].append(message.message_id)
    
    return message

async def send_main_menu(chat_id, user_id):
    await cleanup_user_messages(chat_id)
    user_mode = await db.get_user_mode(user_id)
    text = "Главное меню:"
    await save_and_send(
        chat_id, 
        text=text, 
        reply_markup=create_main_reply_keyboard(user_mode)
    )


@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    if not await db.user_exists(user_id):
        await db.add_user(user_id, username, full_name)
        await state.set_state(CalendarStates.SELECT_TIMEZONE)
        await save_and_send(
            message.chat.id,
            text="⏰ Для корректной работы напоминаний выберите ваш часовой пояс:",
            reply_markup=create_timezone_keyboard()
        )
    else:
        await state.set_state(CalendarStates.MAIN_MENU)
        await send_main_menu(message.chat.id, user_id)

@dp.callback_query(CalendarStates.SELECT_TIMEZONE)
async def process_timezone_selection(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    if data.startswith('tz_'):
        tz = data[3:]
        user_id = callback_query.from_user.id
        
        if tz == 'other':
            await state.set_state(CalendarStates.TIMEZONE_INPUT)
            await save_and_send(
                callback_query.message.chat.id,
                text="🌍 Введите ваш часовой пояс в формате:\nПример: Europe/Moscow, Asia/Tokyo"
            )
        else:
            await db.set_user_timezone(user_id, tz)
            await bot.answer_callback_query(callback_query.id, f"Часовой пояс установлен: {tz}")
            await state.set_state(CalendarStates.SELECT_MODE)
            await save_and_send(
                callback_query.message.chat.id,
                text="👋 Выберите режим работы бота:",
                reply_markup=create_mode_selection_keyboard()
            )
    else:
        await bot.answer_callback_query(callback_query.id, "Неверный выбор часового пояса")

@dp.message(CalendarStates.TIMEZONE_INPUT)
async def process_custom_timezone(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    timezone = message.text.strip()
    
    try:
        pytz.timezone(timezone)
        await db.set_user_timezone(user_id, timezone)
        await state.set_state(CalendarStates.SELECT_MODE)
        await save_and_send(
            message.chat.id,
            text=f"✅ Часовой пояс установлен: {timezone}",
            reply_markup=create_mode_selection_keyboard()
        )
    except pytz.UnknownTimeZoneError:
        await save_and_send(
            message.chat.id,
            text="❌ Неизвестный часовой пояс. Попробуйте еще раз."
        )

@dp.callback_query(CalendarStates.SELECT_MODE)
async def process_mode_selection(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    mode = callback_query.data.split('_')[1]
    
    await db.set_user_mode(user_id, mode)
    await bot.answer_callback_query(callback_query.id, f"Режим установлен: {'встречи' if mode == 'meeting' else 'to-do'}")
    
    await state.set_state(CalendarStates.MAIN_MENU)
    await send_main_menu(callback_query.message.chat.id, user_id)

@dp.message(CalendarStates.MAIN_MENU)
async def process_main_menu_message(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text
    
    if text == "📅 Календарь":
        await show_calendar(message.chat.id, user_id)
        await state.set_state(CalendarStates.CALENDAR_VIEW)
    
    elif text == "✏️ Редактировать задачи":
        await state.set_state(CalendarStates.EDIT_TASKS_MODE)
        await show_calendar(message.chat.id, user_id, mode='edit')
    
    elif text == "🗑️ Удалить день":
        await state.set_state(CalendarStates.DELETE_DAY_MODE)
        await show_calendar(message.chat.id, user_id, mode='delete')
    
    elif text == "👥 Общие дни":
        await state.set_state(CalendarStates.GROUP_MODE)
        await save_and_send(
            message.chat.id,
            text="👥 Введите @usernames пользователей через пробел (макс. 20):\nПример: @user1 @user2",
            reply_markup=create_group_mode_keyboard()
        )
    
    elif text == "⚙️ Настройки":
        user_mode = await db.get_user_mode(user_id)
        current_reminder = await db.get_user_reminder(user_id)
        timezone = await db.get_user_timezone(user_id)
        theme = await db.get_user_theme(user_id)
        
        text = (
            f"⚙️ Настройки:\n"
            f"• Режим: {'встречи' if user_mode == 'meeting' else 'to-do'}\n"
            f"• Напоминание за: {current_reminder} мин\n"
            f"• Часовой пояс: {timezone}\n"
            f"• Тема: {theme}\n\n"
            "Выберите действие:"
        )
        
        await save_and_send(
            message.chat.id,
            text=text,
            reply_markup=create_settings_reply_keyboard()
        )
        await state.set_state(CalendarStates.SETTINGS_MODE)

async def show_calendar(chat_id, user_id, mode='normal'):
    current_date = datetime.now()
    year = current_date.year
    month = current_date.month
    theme = await db.get_user_theme(user_id)
    
    if mode == 'edit':
        calendar_data = await db.get_user_calendar(user_id, month, year)
        busy_days = {day: data for day, data in calendar_data.items() if data['status'] == 'busy' or data.get('task_count', 0) > 0}
        if not busy_days:
            # Создаем клавиатуру с кнопкой "Назад"
            builder = InlineKeyboardBuilder()
            builder.button(text="↩️ Назад", callback_data="back_to_calendar")
            await save_and_send(
                chat_id,
                text="В этом месяце нет дней с задачами.",
                reply_markup=builder.as_markup()
            )
            return
    elif mode == 'delete':
        calendar_data = await db.get_user_calendar(user_id, month, year)
        busy_days = {day: data for day, data in calendar_data.items() if data['status'] == 'busy' or data.get('task_count', 0) > 0}
        if not busy_days:
            # Создаем клавиатуру с кнопкой "Назад"
            builder = InlineKeyboardBuilder()
            builder.button(text="↩️ Назад", callback_data="back_to_calendar")
            await save_and_send(
                chat_id,
                text="В этом месяце нет дней с задачами для удаления.",
                reply_markup=builder.as_markup()
            )
            return
    else:
        calendar_data = await db.get_user_calendar(user_id, month, year)
        busy_days = {day: data for day, data in calendar_data.items() if data['status'] == 'busy' or data.get('task_count', 0) > 0}
    
    calendar_img = calendar_gen.generate_calendar(year, month, busy_days=busy_days, theme=theme)
    
    photo = FSInputFile(calendar_img)
    await save_and_send_photo(
        chat_id=chat_id,
        photo=photo,
        reply_markup=create_calendar_keyboard(year, month, busy_days, mode),
        caption="Выберите день:"
    )
    os.remove(calendar_img)

@dp.callback_query(CalendarStates.CALENDAR_VIEW)
async def process_calendar_interaction(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    user_id = callback_query.from_user.id
    current_date = datetime.now()
    
    if data == 'reset_all':
        await state.set_state(CalendarStates.CONFIRM_RESET)
        await save_and_send(
            callback_query.message.chat.id,
            text="⚠️ Вы уверены, что хотите сбросить ВЕСЬ календарь?",
            reply_markup=create_confirmation_keyboard()
        )
        return
    
    elif data == 'edit_tasks':
        await show_calendar(callback_query.message.chat.id, user_id, mode='edit')
        await state.set_state(CalendarStates.EDIT_TASKS_MODE)
        return
    
    elif data == 'delete_day_mode':
        await show_calendar(callback_query.message.chat.id, user_id, mode='delete')
        await state.set_state(CalendarStates.DELETE_DAY_MODE)
        return
    
    elif data == 'done':
        await state.set_state(CalendarStates.MAIN_MENU)
        await send_main_menu(callback_query.message.chat.id, user_id)
        return
    
    if data.startswith('select_day_'):
        day = int(data.split('_')[2])
        user_mode = await db.get_user_mode(user_id)
        
        if user_mode == 'meeting':
            await db.mark_day_busy(user_id, current_date.year, current_date.month, day)
            await bot.answer_callback_query(callback_query.id, f"День {day} отмечен как занятый")
            await show_calendar(callback_query.message.chat.id, user_id)
        else:
            await state.set_state(CalendarStates.TASK_NAME_INPUT)
            await state.update_data(day=day)
            await save_and_send(
                callback_query.message.chat.id,
                text=f"📝 Введите задачу для {day} числа (или пропустите):",
                reply_markup=create_skip_button()
            )

@dp.callback_query(CalendarStates.DELETE_DAY_MODE)
async def process_delete_day(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if data == 'back_to_calendar':
        await state.set_state(CalendarStates.CALENDAR_VIEW)
        await show_calendar(callback_query.message.chat.id, user_id)
        return
    
    if data.startswith('delete_day_'):
        day = int(data.split('_')[2])
        await state.update_data(day=day)
        await state.set_state(CalendarStates.CONFIRM_DELETE_DAY)
        await save_and_send(
            callback_query.message.chat.id,
            text=f"⚠️ Вы уверены, что хотите удалить ВСЕ задачи и пометки для {day} числа?",
            reply_markup=create_confirmation_keyboard()
        )

@dp.callback_query(CalendarStates.CONFIRM_DELETE_DAY)
async def process_confirm_delete_day(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    current_date = datetime.now()
    
    if callback_query.data == 'confirm_reset':
        data = await state.get_data()
        day = data['day']
        await db.mark_day_free(user_id, current_date.year, current_date.month, day)
        await bot.answer_callback_query(callback_query.id, f"✅ День {day} очищен")
    else:
        await bot.answer_callback_query(callback_query.id, "❌ Удаление отменено")
    
    await state.set_state(CalendarStates.CALENDAR_VIEW)
    await show_calendar(callback_query.message.chat.id, user_id)

@dp.callback_query(CalendarStates.TASK_NAME_INPUT)
async def process_task_skip(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == 'skip_task':
        data = await state.get_data()
        day = data['day']
        user_id = callback_query.from_user.id
        current_date = datetime.now()
        
        await db.mark_day_busy(user_id, current_date.year, current_date.month, day)
        await bot.answer_callback_query(callback_query.id, f"День {day} отмечен как занятый")
        await state.set_state(CalendarStates.CALENDAR_VIEW)
        await show_calendar(callback_query.message.chat.id, user_id)

@dp.message(CalendarStates.TASK_NAME_INPUT)
async def process_task_name(message: types.Message, state: FSMContext):
    task_name = message.text
    await state.update_data(task_name=task_name)
    await state.set_state(CalendarStates.TASK_TIME_SELECT)
    await save_and_send(
        message.chat.id,
        text="⏰ Выберите время для задачи:",
        reply_markup=create_time_selection_keyboard()
    )

@dp.callback_query(CalendarStates.TASK_TIME_SELECT)
async def process_task_time(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    
    if data.startswith('time_'):
        time_str = data.split('_')[1]
        await state.update_data(task_time=time_str)
        await state.set_state(CalendarStates.TASK_REMINDER_SELECT)
        await save_and_send(
            callback_query.message.chat.id,
            text="⏱ За сколько минут напомнить о задаче?",
            reply_markup=create_compact_reminder_keyboard()
        )
    
    elif data.startswith('time_page_'):
        page = int(data.split('_')[2])
        await bot.edit_message_reply_markup(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=create_time_selection_keyboard(page)
        )

@dp.callback_query(CalendarStates.TASK_REMINDER_SELECT)
async def process_task_reminder(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data.startswith('reminder_'):
        reminder = int(callback_query.data.split('_')[1])
        data = await state.get_data()
        user_id = callback_query.from_user.id
        current_date = datetime.now()
        
        await db.add_task(
            user_id,
            current_date.year,
            current_date.month,
            data['day'],
            data['task_name'],
            data['task_time'],
            reminder
        )
        
        await bot.answer_callback_query(callback_query.id, "✅ Задача добавлена!")
        await save_and_send(
            callback_query.message.chat.id,
            text="Хотите добавить еще одну задачу на этот день?",
            reply_markup=create_task_decision_keyboard()
        )
        await state.set_state(CalendarStates.DAY_SELECTED)

@dp.callback_query(CalendarStates.DAY_SELECTED)
async def process_task_decision(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == 'add_another_task':
        await state.set_state(CalendarStates.TASK_NAME_INPUT)
        await save_and_send(
            callback_query.message.chat.id,
            text="📝 Введите задачу:"
        )
    else:  # back_to_calendar
        data = await state.get_data()
        user_id = callback_query.from_user.id
        await state.set_state(CalendarStates.CALENDAR_VIEW)
        await show_calendar(callback_query.message.chat.id, user_id)

@dp.callback_query(CalendarStates.EDIT_TASKS_MODE)
async def process_edit_tasks(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if data == 'back_to_calendar':
        await state.set_state(CalendarStates.MAIN_MENU)
        await send_main_menu(callback_query.message.chat.id, user_id)
        return
    
    current_date = datetime.now()
    
    if data.startswith('edit_day_'):
        day = int(data.split('_')[2])
        tasks = await db.get_tasks_for_day(user_id, current_date.year, current_date.month, day)
        
        if not tasks:
            await bot.answer_callback_query(callback_query.id, "В этот день нет задач.")
            return
        
        await state.update_data(day=day)
        await state.set_state(CalendarStates.DAY_TASKS_VIEW)
        await show_day_tasks(callback_query.message.chat.id, day, tasks)

async def show_day_tasks(chat_id, day, tasks):
    text = f"Задачи на {day} число:\n"
    for idx, task in enumerate(tasks, 1):
        text += f"{idx}. {task['task']} ({task['time']})\n"
    
    await save_and_send(
        chat_id,
        text=text,
        reply_markup=create_tasks_list_keyboard(tasks)
    )

@dp.callback_query(CalendarStates.DAY_TASKS_VIEW)
async def process_task_actions(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    user_id = callback_query.from_user.id
    current_date = datetime.now()
    
    if data == 'back_to_days':
        await state.set_state(CalendarStates.EDIT_TASKS_MODE)
        await show_calendar(callback_query.message.chat.id, user_id, mode='edit')
        return
    
    if data.startswith('delete_task_'):
        task_id = int(data.split('_')[2])
        await db.delete_task(task_id)
        await bot.answer_callback_query(callback_query.id, "✅ Задача удалена")
        
        state_data = await state.get_data()
        day = state_data.get('day')
        tasks = await db.get_tasks_for_day(user_id, current_date.year, current_date.month, day)
        
        if tasks:
            await show_day_tasks(callback_query.message.chat.id, day, tasks)
        else:
            await save_and_send(callback_query.message.chat.id, text="Все задачи удалены")
            await state.set_state(CalendarStates.EDIT_TASKS_MODE)
            await show_calendar(callback_query.message.chat.id, user_id, mode='edit')
    
    elif data.startswith('edit_task_'):
        task_id = int(data.split('_')[2])
        task = await db.get_task_by_id(task_id)
        
        if task:
            await state.update_data(
                task_id=task_id,
                day=task['day']
            )
            await state.set_state(CalendarStates.TASK_NAME_INPUT)
            await save_and_send(
                callback_query.message.chat.id,
                text=f"✏️ Введите новую задачу для {task['day']} числа:"
            )

@dp.callback_query(CalendarStates.CONFIRM_RESET)
async def process_reset_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    current_date = datetime.now()
    
    if callback_query.data == 'confirm_reset':
        await db.reset_user_calendar(user_id, current_date.year, current_date.month)
        await bot.answer_callback_query(callback_query.id, "✅ Календарь сброшен")
    else:
        await bot.answer_callback_query(callback_query.id, "❌ Сброс отменен")
    
    await state.set_state(CalendarStates.MAIN_MENU)
    await send_main_menu(callback_query.message.chat.id, user_id)

@dp.message(CalendarStates.SETTINGS_MODE)
async def process_settings_message(message: types.Message, state: FSMContext):
    text = message.text
    user_id = message.from_user.id
    
    if text == "🔄 Сменить режим":
        await state.set_state(CalendarStates.SELECT_MODE)
        await save_and_send(
            message.chat.id,
            text="Выберите режим работы:",
            reply_markup=create_mode_selection_keyboard()
        )
    
    elif text == "⏱ Напоминание":
        # Получаем текущее значение напоминания
        current_reminder = await db.get_user_reminder(user_id)
        await save_and_send(
            message.chat.id,
            text=f"⏱ Текущее время напоминания: {current_reminder} мин\nВыберите новое значение:",
            reply_markup=create_compact_reminder_keyboard()
        )
    
    elif text == "🌍 Часовой пояс":
        await state.set_state(CalendarStates.SELECT_TIMEZONE)
        await save_and_send(
            message.chat.id,
            text="Выберите часовой пояс:",
            reply_markup=create_timezone_keyboard()
        )
    
    elif text == "🎨 Тема":
        await save_and_send(
            message.chat.id,
            text="Выберите тему оформления:",
            reply_markup=create_theme_selection_keyboard()
        )
    
    elif text == "↩️ Главное меню":
        await state.set_state(CalendarStates.MAIN_MENU)
        await send_main_menu(message.chat.id, user_id)

# Обновленный обработчик настроек
@dp.callback_query(CalendarStates.SETTINGS_MODE)
async def process_settings_callback(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if data.startswith('theme_'):
        theme = data.split('_')[1]
        await db.set_user_theme(user_id, theme)
        await bot.answer_callback_query(callback_query.id, f"✅ Тема установлена: {theme}")
        
        # Обновляем сообщение с настройками
        user_mode = await db.get_user_mode(user_id)
        current_reminder = await db.get_user_reminder(user_id)
        timezone = await db.get_user_timezone(user_id)
        theme = await db.get_user_theme(user_id)
        
        text = (
            f"⚙️ Настройки:\n"
            f"• Режим: {'встречи' if user_mode == 'meeting' else 'to-do'}\n"
            f"• Напоминание за: {current_reminder} мин\n"
            f"• Часовой пояс: {timezone}\n"
            f"• Тема: {theme}\n\n"
            "Выберите действие:"
        )
        
        try:
            await callback_query.message.edit_text(
                text=text,
                reply_markup=create_settings_reply_keyboard()
            )
        except:
            # Если не удалось отредактировать, отправляем новое
            await save_and_send(
                callback_query.message.chat.id,
                text=text,
                reply_markup=create_settings_reply_keyboard()
            )
    
    elif data.startswith('reminder_'):
        # Обработка выбора напоминания
        reminder = int(data.split('_')[1])
        await db.set_user_reminder(user_id, reminder)
        await bot.answer_callback_query(callback_query.id, f"⏱ Напоминание установлено: {reminder} мин")
        
        # Обновляем сообщение с настройками
        user_mode = await db.get_user_mode(user_id)
        current_reminder = reminder  # новое значение
        timezone = await db.get_user_timezone(user_id)
        theme = await db.get_user_theme(user_id)
        
        text = (
            f"⚙️ Настройки:\n"
            f"• Режим: {'встречи' if user_mode == 'meeting' else 'to-do'}\n"
            f"• Напоминание за: {current_reminder} мин\n"
            f"• Часовой пояс: {timezone}\n"
            f"• Тема: {theme}\n\n"
            "Выберите действие:"
        )
        
        try:
            await callback_query.message.edit_text(
                text=text,
                reply_markup=create_settings_reply_keyboard()
            )
        except:
            # Если не удалось отредактировать, отправляем новое
            await save_and_send(
                callback_query.message.chat.id,
                text=text,
                reply_markup=create_settings_reply_keyboard()
            )

@dp.callback_query(CalendarStates.SETTINGS_MODE)
async def process_theme_selection(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data.startswith('theme_'):
        theme = callback_query.data.split('_')[1]
        user_id = callback_query.from_user.id
        await db.set_user_theme(user_id, theme)
        await bot.answer_callback_query(callback_query.id, f"✅ Тема установлена: {theme}")
        await state.set_state(CalendarStates.SETTINGS_MODE)
        await save_and_send(
            callback_query.message.chat.id,
            text="Настройки обновлены. Что дальше?",
            reply_markup=create_settings_reply_keyboard()
        )

@dp.message(CalendarStates.GROUP_MODE)
async def process_group_usernames(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()
    
    if text == "↩️ Назад":
        await state.set_state(CalendarStates.MAIN_MENU)
        await send_main_menu(message.chat.id, user_id)
        return
    
    usernames = [username.strip() for username in text.split() if username.startswith('@')]
    
    if not usernames:
        builder = ReplyKeyboardBuilder()
        builder.button(text="↩️ Назад")
        builder.adjust(1)
        
        await save_and_send(
            message.chat.id,
            text="❌ Не найдено ни одного юзернейма. Попробуйте снова.\nПример: @user1 @user2",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )
        return
    
    if len(usernames) > 20:
        builder = ReplyKeyboardBuilder()
        builder.button(text="↩️ Назад")
        builder.adjust(1)
        
        await save_and_send(
            message.chat.id,
            text="❌ Превышен лимит пользователей (20).",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )
        return
    
    user_ids = await db.get_user_ids_by_usernames([u[1:] for u in usernames])
    
    if not user_ids:
        builder = ReplyKeyboardBuilder()
        builder.button(text="↩️ Назад")
        builder.adjust(1)
        
        await save_and_send(
            message.chat.id,
            text="❌ Не найдено пользователей по указанным юзернеймам.",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )
        return
    
    user_ids.append(user_id)
    current_date = datetime.now()
    free_days = await db.find_common_free_days(user_ids, current_date.year, current_date.month)
    
    if not free_days:
        builder = ReplyKeyboardBuilder()
        builder.button(text="↩️ Назад")
        builder.adjust(1)
        
        await save_and_send(
            message.chat.id,
            text="❌ Нет общих свободных дней в этом месяце.",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )
        return
    
    theme = await db.get_user_theme(user_id)
    calendar_img = calendar_gen.generate_calendar(
        current_date.year, 
        current_date.month, 
        common_free_days=free_days,
        theme=theme
    )
    
    photo = FSInputFile(calendar_img)
    sent_message = await bot.send_photo(
        chat_id=message.chat.id,
        photo=photo,
        caption=f"Общие свободные дни: {', '.join(map(str, free_days))}",
        reply_markup=create_group_mode_keyboard()
    )
    os.remove(calendar_img)
    
    await state.set_state(CalendarStates.MAIN_MENU)
    await send_main_menu(message.chat.id, user_id)

# Заглушки для состояний
@dp.message(CalendarStates.CALENDAR_VIEW)
async def handle_calendar_view_message(message: types.Message):
    await save_and_send(message.chat.id, text="ℹ️ Пожалуйста, используйте кнопки календаря для взаимодействия.")

@dp.message(CalendarStates.SELECT_MODE)
async def handle_mode_selection_message(message: types.Message):
    await save_and_send(message.chat.id, text="ℹ️ Пожалуйста, выберите режим работы с помощью кнопок ниже.")

@dp.message(CalendarStates.TASK_TIME_SELECT)
async def handle_time_selection_message(message: types.Message):
    await save_and_send(message.chat.id, text="ℹ️ Пожалуйста, выберите время с помощью кнопок ниже.")

@dp.message(CalendarStates.TASK_REMINDER_SELECT)
async def handle_reminder_selection_message(message: types.Message):
    await save_and_send(message.chat.id, text="ℹ️ Пожалуйста, выберите время напоминания с помощью кнопок ниже.")

@dp.message(CalendarStates.EDIT_TASKS_MODE)
async def handle_edit_tasks_message(message: types.Message):
    await save_and_send(message.chat.id, text="ℹ️ Пожалуйста, используйте кнопки календаря для выбора дня с задачами.")

@dp.message(CalendarStates.DAY_TASKS_VIEW)
async def handle_day_tasks_message(message: types.Message):
    await save_and_send(message.chat.id, text="ℹ️ Пожалуйста, используйте кнопки для управления задачами.")

@dp.message(CalendarStates.CONFIRM_RESET)
async def handle_reset_confirmation_message(message: types.Message):
    await save_and_send(message.chat.id, text="ℹ️ Пожалуйста, подтвердите или отмените сброс календаря с помощью кнопок.")

async def run_bot():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(run_bot())
