import asyncio
import os
import random
from datetime import date, timedelta, datetime
import pytz
import aiohttp
from constants import DAILY_BASE_URL, ZODIAC_MAP
from parser_utils import setup_parser_logger, init_horoscope_db, parse_horoscope, insert_horoscope

logger = setup_parser_logger('DailyParser')

# Улучшенная функция для безопасного парсинга
async def safe_parse_and_insert(session, semaphore, sign_name, sign_id):
    # Ждем, пока семафор освободится
    async with semaphore:
        try:
            logger.info(f"Начинаю парсинг для знака: {sign_name}")
            data = await parse_horoscope(sign_id, DAILY_BASE_URL, session)
            if data and data.get('general_text'):
                # Устанавливаем часовой пояс (например, Москва, UTC+3)
                target_tz = pytz.timezone('Europe/Moscow')
                # Получаем текущую дату в этом часовом поясе
                today_in_target_tz = datetime.now(target_tz).date()
                # Рассчитываем дату для гороскопа на "завтра"
                horoscope_date = today_in_target_tz + timedelta(days=1)
                await insert_horoscope(sign_id, 'daily', horoscope_date, data)
                logger.info(f"Успешно сохранен гороскоп для {sign_name} на {horoscope_date}")
            else:
                logger.warning(f"Не удалось получить данные для {sign_name}")
        except Exception as e:
            logger.error(f"Ошибка при парсинге {sign_name}: {e}", exc_info=True)
        finally:
            # Добавляем случайную задержку после каждого запроса, чтобы имитировать человека
            delay = random.uniform(3, 7)
            logger.info(f"Пауза на {delay:.2f} секунд...")
            await asyncio.sleep(delay)

async def main():
    logger.info("Запуск парсинга ежедневных гороскопов")
    if not os.path.exists('data'):
        os.makedirs('data')
    await init_horoscope_db()
    
    # Ограничиваем количество одновременных запросов (например, не больше 2)
    semaphore = asyncio.Semaphore(2)
    
    async with aiohttp.ClientSession() as session:
        tasks = [safe_parse_and_insert(session, semaphore, name, sign_id) for name, sign_id in ZODIAC_MAP.items()]
        await asyncio.gather(*tasks)
    
    logger.info("Парсинг ежедневных гороскопов завершен")

if __name__ == "__main__":
    asyncio.run(main())
