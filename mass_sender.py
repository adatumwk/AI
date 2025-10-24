import asyncio
import logging
from telegram import Bot
from telegram.error import Forbidden

# Импортируем нужные компоненты из вашего проекта
from config import BOT_TOKEN
from database import get_all_active_users, save_user_data

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Текст вашего сообщения
MESSAGE_TEXT = """
Мы обновили нашего бота — теперь он стал еще удобнее и полезнее 🎉

Чтобы продолжить получать рассылку, отправьте команду /start.
(Или нажмите «Меню» → «🚀Запустить/перезапустить бота»).

Спасибо, что остаетесь с нами ✨
"""

async def main():
    """
    Основная функция для выполнения рассылки.
    """
    bot = Bot(token=BOT_TOKEN)
    logger.info("Начинаем рассылку...")

    user_ids = await get_all_active_users()
    if not user_ids:
        logger.info("Активных пользователей для рассылки не найдено.")
        return

    total_users = len(user_ids)
    sent_count = 0
    blocked_count = 0

    for user_id in user_ids:
        try:
            await bot.send_message(chat_id=user_id, text=MESSAGE_TEXT)
            sent_count += 1
            logger.info(f"Сообщение успешно отправлено пользователю {user_id}")
        except Forbidden:
            # Если пользователь заблокировал бота
            blocked_count += 1
            logger.warning(f"Пользователь {user_id} заблокировал бота. Деактивируем.")
            await save_user_data(user_id, is_active=False)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
        
        # Печатаем прогресс в консоль
        progress = f"Прогресс: {sent_count + blocked_count}/{total_users} (Отправлено: {sent_count}, Заблокировали: {blocked_count})"
        print(progress)

        # САМАЯ ВАЖНАЯ ЧАСТЬ: задержка для защиты от бана
        # 1 секунда — безопасная задержка. Не делайте ее меньше.
        await asyncio.sleep(1)

    logger.info("Рассылка завершена.")
    logger.info(f"Всего отправлено: {sent_count}. Пользователей заблокировало бота: {blocked_count}.")


if __name__ == "__main__":
    # Запускаем асинхронную функцию
    asyncio.run(main())
