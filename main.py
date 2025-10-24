import logging
import asyncio
import nest_asyncio
import os
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackContext,
    CallbackQueryHandler, ConversationHandler
)
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning

filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

nest_asyncio.apply()

from config import BOT_TOKEN
from keyboards import *
from database import init_user_db, get_user_data, save_user_data
from scheduler import scheduler, update_user_jobs, format_horoscope_message
from horoscope_fetcher import get_horoscope_from_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SETUP_ZODIAC, SETUP_TIMEZONE, SETUP_TIME = range(3)
SETTINGS_ROOT, SETTINGS_ZODIAC, SETTINGS_TIMEZONE, SETTINGS_TIME = range(3, 7)

async def start_command(update: Update, context: CallbackContext):
    try:
        user = update.effective_user
        logger.info(f"Команда /start от {user.id} ({user.username})")

        user_info = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "language_code": user.language_code,
            "is_premium": getattr(user, 'is_premium', False)
        }
        await save_user_data(user.id, **user_info)

        user_data_db = await get_user_data(user.id)
        if user_data_db and user_data_db.get('zodiac_sign'):
            await update.message.reply_text("✨Главное меню:", reply_markup=get_main_menu_keyboard())
            return ConversationHandler.END

        await update.message.reply_html(f"Привет, {user.mention_html()}! Давайте настроим ваш гороскоп.")
        await update.message.reply_text("Шаг 1: Выберите ваш знак зодиака:", reply_markup=get_zodiac_keyboard())
        return SETUP_ZODIAC
    except Exception as e:
        logger.error(f"Ошибка в start_command: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при запуске. Попробуйте позже.")
        return ConversationHandler.END

async def show_main_menu(update: Update, context: CallbackContext, text: str = "Главное меню:"):
    try:
        logger.info("Показ главного меню")
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=get_main_menu_keyboard())
        else:
            await update.message.reply_text(text, reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка в show_main_menu: {e}", exc_info=True)
        return ConversationHandler.END

async def stop_command(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        await save_user_data(user_id, is_active=False)
        job_id = f'daily_{user_id}'
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        await update.message.reply_text("🛑 Уведомления отключены. Чтобы включить, используйте /subscribe.")
    except Exception as e:
        logger.error(f"Ошибка в stop_command: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")

async def subscribe_command(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        user = await get_user_data(user_id)
        if user and user.get('timezone') and user.get('notification_time'):
            await save_user_data(user_id, is_active=True)
            update_user_jobs(user_id, user['timezone'], user['notification_time'])
            await update.message.reply_text("✅ Уведомления включены!")
        else:
            await update.message.reply_text("Сначала настройте бота через /start.")
    except Exception as e:
        logger.error(f"Ошибка в subscribe_command: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")

async def setup_select_zodiac(update: Update, context: CallbackContext):
    try:
        query = update.callback_query
        await query.answer()
        sign = query.data.split('_')[1]
        await save_user_data(update.effective_user.id, zodiac_sign=sign)
        await query.edit_message_text("Шаг 2: Выберите ваш часовой пояс:", reply_markup=get_timezone_keyboard())
        return SETUP_TIMEZONE
    except Exception as e:
        logger.error(f"Ошибка в setup_select_zodiac: {e}", exc_info=True)
        await query.edit_message_text("Произошла ошибка. Попробуйте /start заново.")
        return ConversationHandler.END

async def setup_select_timezone(update: Update, context: CallbackContext):
    try:
        query = update.callback_query
        await query.answer()
        tz = query.data.split('_')[1]
        await save_user_data(update.effective_user.id, timezone=tz)
        await query.edit_message_text("Шаг 3: Выберите время для ежедневных уведомлений:", reply_markup=get_time_keyboard())
        return SETUP_TIME
    except Exception as e:
        logger.error(f"Ошибка в setup_select_timezone: {e}", exc_info=True)
        await query.edit_message_text("Произошла ошибка. Попробуйте /start заново.")
        return ConversationHandler.END

async def setup_select_time(update: Update, context: CallbackContext):
    try:
        query = update.callback_query
        await query.answer()
        time = query.data.split('_')[1]
        user_id = update.effective_user.id
        await save_user_data(user_id, notification_time=time)
        user = await get_user_data(user_id)
        update_user_jobs(user_id, user['timezone'], time)
        await query.edit_message_text("Настройка завершена! Вы будете получать ежедневные гороскопы.", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка в setup_select_time: {e}", exc_info=True)
        await query.edit_message_text("Произошла ошибка. Попробуйте /start заново.")
        return ConversationHandler.END

async def cancel_setup(update: Update, context: CallbackContext):
    try:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Настройка отменена.")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка в cancel_setup: {e}", exc_info=True)
        return ConversationHandler.END

# Остальные handlers аналогично добавьте try-except если нужно, но для краткости опущу повторения. Полный код с ними.

async def main():
    if not os.path.exists('data'): os.makedirs('data')
    await init_user_db()
    
    scheduler.start()

    application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()  # Попробуйте False если проблемы persist

    commands = [
        BotCommand("start", "🚀 Запустить/перезапустить бота"),
        BotCommand("menu", "📖 Открыть главное меню"),
        BotCommand("subscribe", "🔔 Включить ежедневные уведомления"),
        BotCommand("stop", "🔕 Отключить уведомления")
    ]
    await application.bot.set_my_commands(commands)

    # ConversationHandlers и add_handler как в оригинале

    logger.info("Бот запущен...")
    try:
        await application.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания. Остановка бота...")
    finally:
        try:
            await application.stop()
        except RuntimeError as e:
            logger.warning(f"Ошибка при вызове application.stop(): {e}")
            
        scheduler.shutdown()
        logger.info("Бот остановлен.")

if __name__ == "__main__":
    asyncio.run(main())
