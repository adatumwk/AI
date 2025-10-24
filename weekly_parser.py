import asyncio
import os
import random
from datetime import date, timedelta
import aiohttp
# ИЗМЕНЕНИЕ: Используем WEEKLY_BASE_URL
from constants import WEEKLY_BASE_URL, ZODIAC_MAP
from parser_utils import setup_parser_logger, init_horoscope_db, parse_horoscope, insert_horoscope

logger = setup_parser_logger('WeeklyParser')

async def safe_parse_and_insert(session, semaphore, sign_name, sign_id):
    async with semaphore:
        try:
            logger.info(f"Начинаю парсинг для знака: {sign_name}")
            # ИЗМЕНЕНИЕ: Используем WEEKLY_BASE_URL
            data = await parse_horoscope(sign_id, WEEKLY_BASE_URL, session)
            if data and data.get('general_text'):
                # ИЗМЕНЕНИЕ: Правильный расчет даты для еженедельного гороскопа
                today = date.today()
                horoscope_date = today - timedelta(days=today.weekday())
                await insert_horoscope(sign_id, 'weekly', horoscope_date, data)
                logger.info(f"Успешно сохранен гороскоп для {sign_name} на неделю, начиная с {horoscope_date}")
            else:
                logger.warning(f"Не удалось получить данные для {sign_name}")
        except Exception as e:
            logger.error(f"Ошибка при парсинге {sign_name}: {e}", exc_info=True)
        finally:
            delay = random.uniform(3, 7)
            logger.info(f"Пауза на {delay:.2f} секунд...")
            await asyncio.sleep(delay)

async def main():
    logger.info("Запуск парсинга еженедельных гороскопов")
    if not os.path.exists('data'):
        os.makedirs('data')
    await init_horoscope_db()
    
    semaphore = asyncio.Semaphore(2)
    
    async with aiohttp.ClientSession() as session:
        tasks = [safe_parse_and_insert(session, semaphore, name, sign_id) for name, sign_id in ZODIAC_MAP.items()]
        await asyncio.gather(*tasks)
    
    logger.info("Парсинг еженедельных гороскопов завершен")

if __name__ == "__main__":
    asyncio.run(main())
