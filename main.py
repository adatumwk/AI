import logging
import asyncio
import nest_asyncio # ИСПРАВЛЕНИЕ: Возвращаем nest_asyncio
import os
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackContext,
    CallbackQueryHandler, ConversationHandler
)
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning

filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

nest_asyncio.apply() # ИСПРАВЛЕНИЕ: Возвращаем nest_asyncio.apply()

from config import BOT_TOKEN
from keyboards import *
from database import init_user_db, get_user_data, save_user_data
from scheduler import scheduler, update_user_jobs, format_horoscope_message
from horoscope_fetcher import get_horoscope_from_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Состояния для диалогов
SETUP_ZODIAC, SETUP_TIMEZONE, SETUP_TIME = range(3)
SETTINGS_ROOT, SETTINGS_ZODIAC, SETTINGS_TIMEZONE, SETTINGS_TIME = range(3, 7)

# === ОСНОВНЫЕ КОМАНДЫ И ГЛАВНОЕ МЕНЮ ===

async def start_command(update: Update, context: CallbackContext):
    """Начало диалога и сохранение основной информации о пользователе."""
    user = update.effective_user
    logger.info(f"Команда /start от {user.id} ({user.username})")

    # Собираем всю доступную информацию о пользователе
    user_info = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "language_code": user.language_code,
        "is_premium": getattr(user, 'is_premium', False) # getattr для совместимости
    }
    # Сразу сохраняем или обновляем основную информацию
    await save_user_data(user.id, **user_info)

    user_data_db = await get_user_data(user.id)
    # Проверяем, прошел ли пользователь полную настройку (выбрал знак зодиака)
    if user_data_db and user_data_db.get('zodiac_sign'):
        await update.message.reply_text("✨Главное меню:", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END
    
    await update.message.reply_html(f"Привет, {user.mention_html()}! Давайте настроим ваш гороскоп.")
    await update.message.reply_text("Шаг 1: Выберите ваш знак зодиака:", reply_markup=get_zodiac_keyboard())
    return SETUP_ZODIAC

async def show_main_menu(update: Update, context: CallbackContext, text: str = "Главное меню:"):
    """Универсальная функция для показа главного меню."""
    logger.info("Показ главного меню")
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=get_main_menu_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=get_main_menu_keyboard())
    return ConversationHandler.END

# Новое: Команды для управления подпиской
async def stop_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    await save_user_data(user_id, is_active=False)
    job_id = f'daily_{user_id}'
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    await update.message.reply_text("🛑 Уведомления отключены. Чтобы включить, используйте /subscribe.")
    
async def subscribe_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = await get_user_data(user_id)
    if user and user.get('timezone') and user.get('notification_time'):
        await save_user_data(user_id, is_active=True)
        update_user_jobs(user_id, user['timezone'], user['notification_time'])
        await update.message.reply_text("✅ Уведомления включены!")
    else:
        await update.message.reply_text("Сначала настройте бота через /start.")

# === ДИАЛОГ ПЕРВОНАЧАЛЬНОЙ НАСТРОЙКИ ===

async def setup_select_zodiac(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer()
    context.user_data['zodiac'] = query.data.split('_')[1]
    await query.edit_message_text("Шаг 2: Выберите ваш часовой пояс.", reply_markup=get_timezone_keyboard())
    return SETUP_TIMEZONE

async def setup_select_timezone(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer()
    context.user_data['timezone'] = query.data.split('_')[1]
    await query.edit_message_text("Шаг 3: Выберите время для уведомлений.", reply_markup=get_time_keyboard())
    return SETUP_TIME

async def setup_select_time(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer()
    time = query.data.split('_')[1]
    user_id = query.from_user.id
    user_choices = {"zodiac_sign": context.user_data.get('zodiac'), "timezone": context.user_data.get('timezone'), "notification_time": time}
    
    await save_user_data(user_id, **user_choices)
    update_user_jobs(user_id, user_choices["timezone"], time)
    
    await query.edit_message_text("🎉 Настройки успешно сохранены!")
    await show_main_menu(update, context, text="Ваше главное меню:")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_setup(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer()
    await query.edit_message_text("Настройка отменена.")
    context.user_data.clear()
    return ConversationHandler.END

# === ДИАЛОГ ИЗМЕНЕНИЯ НАСТРОЕК ===

async def settings_start(update: Update, context: CallbackContext):
    """Вход в меню настроек."""
    query = update.callback_query; await query.answer()
    logger.info("Вход в меню настроек")
    await query.edit_message_text("⚙️ Здесь вы можете изменить свои настройки:", reply_markup=get_settings_menu_keyboard())
    return SETTINGS_ROOT

async def settings_ask_zodiac(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer()
    await query.edit_message_text("Выберите ваш новый знак зодиака:", reply_markup=get_zodiac_keyboard(is_settings=True))
    return SETTINGS_ZODIAC

async def settings_save_zodiac(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer()
    zodiac_sign = query.data.split('_')[1]
    await save_user_data(query.from_user.id, zodiac_sign=zodiac_sign)
    await query.edit_message_text(f"✅ Знак изменен на {RUSSIAN_SIGNS[zodiac_sign]}.\n\n⚙️ Настройки:", reply_markup=get_settings_menu_keyboard())
    return SETTINGS_ROOT

async def settings_ask_timezone(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer()
    await query.edit_message_text("Выберите ваш новый часовой пояс:", reply_markup=get_timezone_keyboard(is_settings=True))
    return SETTINGS_TIMEZONE

async def settings_save_timezone(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer()
    timezone = query.data.split('_')[1]
    user_id = query.from_user.id
    await save_user_data(user_id, timezone=timezone)
    user = await get_user_data(user_id)
    if user and user.get('notification_time'):
        update_user_jobs(user_id, timezone, user['notification_time'])
    await query.edit_message_text(f"✅ Часовой пояс изменен на {timezone}.\n\n⚙️ Настройки:", reply_markup=get_settings_menu_keyboard())
    return SETTINGS_ROOT

async def settings_ask_time(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer()
    await query.edit_message_text("Выберите новое время уведомлений:", reply_markup=get_time_keyboard(is_settings=True))
    return SETTINGS_TIME

async def settings_save_time(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer()
    time = query.data.split('_')[1]
    user_id = query.from_user.id
    await save_user_data(user_id, notification_time=time)
    user = await get_user_data(user_id)
    if user and user.get('timezone'):
        update_user_jobs(user_id, user['timezone'], time)
    await query.edit_message_text(f"✅ Время уведомлений изменено на {time}.\n\n⚙️ Настройки:", reply_markup=get_settings_menu_keyboard())
    return SETTINGS_ROOT

# === ОБРАБОТЧИКИ ОСТАЛЬНЫХ КНОПОК ===

async def get_now_handler(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer()
    logger.info("Кнопка 'Получить гороскоп' нажата")
    user = await get_user_data(query.from_user.id)
    if not user or not user.get('zodiac_sign'):
        await query.message.reply_text("Сначала пройдите настройку через /start.")
        return
    await query.message.reply_text("Какой гороскоп хотите получить?", reply_markup=get_horoscope_type_keyboard())
    
async def help_handler(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer()
    logger.info("Кнопка 'Помощь' нажата")
    help_text = "Это бот для гороскопов. Команда /start начинает настройку."
    await query.edit_message_text(help_text, reply_markup=get_main_menu_keyboard())
    
async def horoscope_type_handler(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer()
    logger.info("Выбран тип гороскопа")
    horoscope_type = query.data.split('_')[2]
    user = await get_user_data(query.from_user.id)
    if not user: return
    
    await query.edit_message_text("🔮 Ищу ваш гороскоп, минутку...")
    horoscope_data = await get_horoscope_from_db(user['zodiac_sign'], horoscope_type)
    
    if not horoscope_data:
        await query.edit_message_text(f"😔 Гороскоп типа {horoscope_type} не найден. Попробуйте позже.")
        await context.bot.send_message(chat_id=query.from_user.id, text="Главное меню:", reply_markup=get_main_menu_keyboard())
        return
        
    h_type_rus = {
        "daily": "ежедневный", 
        "weekly": "еженедельный", 
        "monthly": "ежемесячный",
        "yearly": "годовой" 
    }.get(horoscope_type, "неизвестный")
    message = format_horoscope_message(horoscope_data, user['zodiac_sign'], h_type_rus)
    await query.edit_message_text(message, parse_mode='Markdown')
    await context.bot.send_message(chat_id=query.from_user.id, text="Главное меню:", reply_markup=get_main_menu_keyboard())

async def main():
    if not os.path.exists('data'): os.makedirs('data')
    await init_user_db()
    
    scheduler.start()

    application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()

    commands = [
        BotCommand("start", "🚀 Запустить/перезапустить бота"),
        BotCommand("menu", "📖 Открыть главное меню"),
        BotCommand("subscribe", "🔔 Включить ежедневные уведомления"),
        BotCommand("stop", "🔕 Отключить уведомления")
    ]
    await application.bot.set_my_commands(commands)

    setup_conv = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            SETUP_ZODIAC: [CallbackQueryHandler(setup_select_zodiac, pattern='^zodiac_')],
            SETUP_TIMEZONE: [CallbackQueryHandler(setup_select_timezone, pattern='^tz_')],
            SETUP_TIME: [CallbackQueryHandler(setup_select_time, pattern='^time_')]
        },
        fallbacks=[CallbackQueryHandler(cancel_setup, pattern=f'^{CbData.CANCEL}$')],
        per_message=False
    )
    
    settings_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(settings_start, pattern=f'^{CbData.SETTINGS}$')],
        states={
            SETTINGS_ROOT: [
                CallbackQueryHandler(settings_ask_zodiac, pattern=f'^{CbData.CHANGE_ZODIAC}$'),
                CallbackQueryHandler(settings_ask_timezone, pattern=f'^{CbData.CHANGE_TIMEZONE}$'),
                CallbackQueryHandler(settings_ask_time, pattern=f'^{CbData.CHANGE_TIME}$')
            ],
            SETTINGS_ZODIAC: [
                CallbackQueryHandler(settings_save_zodiac, pattern='^zodiac_'),
                CallbackQueryHandler(settings_start, pattern=f'^{CbData.SETTINGS}$')
            ],
            SETTINGS_TIMEZONE: [
                CallbackQueryHandler(settings_save_timezone, pattern='^tz_'),
                CallbackQueryHandler(settings_start, pattern=f'^{CbData.SETTINGS}$')
            ],
            SETTINGS_TIME: [
                CallbackQueryHandler(settings_save_time, pattern='^time_'),
                CallbackQueryHandler(settings_start, pattern=f'^{CbData.SETTINGS}$')
            ]
        },
        fallbacks=[CallbackQueryHandler(show_main_menu, pattern=f'^{CbData.BACK_TO_MAIN}$')],
        per_message=False
    )

    application.add_handler(setup_conv)
    application.add_handler(settings_conv)
    
    application.add_handler(CallbackQueryHandler(get_now_handler, pattern=f'^{CbData.GET_NOW}$'))
    application.add_handler(CallbackQueryHandler(help_handler, pattern=f'^{CbData.HELP}$'))
    
    application.add_handler(CallbackQueryHandler(horoscope_type_handler, pattern='^h_type_'))
    application.add_handler(CommandHandler('menu', lambda u, c: u.message.reply_text("Главное меню:", reply_markup=get_main_menu_keyboard())))
    
    # Новое: Добавляем обработчики для /stop и /subscribe
    application.add_handler(CommandHandler('stop', stop_command))
    application.add_handler(CommandHandler('subscribe', subscribe_command))

    logger.info("Бот запущен...")
    try:
        await application.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания. Остановка бота...")
    finally:
        # ИСПРАВЛЕНИЕ: Оборачиваем application.stop() в try/except,
        # чтобы избежать ошибки, если бот упал до полного запуска.
        try:
            await application.stop()
        except RuntimeError as e:
            logger.warning(f"Ошибка при вызове application.stop(): {e}")
            
        scheduler.shutdown()
        logger.info("Бот остановлен.")

if __name__ == "__main__":
    asyncio.run(main())
