# yearly_parser.py

import asyncio
import os
import random
from datetime import date
import aiohttp
from constants import YEARLY_BASE_URL, ZODIAC_MAP
from parser_utils import setup_parser_logger, init_horoscope_db, parse_horoscope, insert_horoscope

logger = setup_parser_logger('YearlyParser')

async def safe_parse_and_insert(session, semaphore, sign_name, sign_id):
    async with semaphore:
        try:
            logger.info(f"Начинаю парсинг годового гороскопа для знака: {sign_name}")
            data = await parse_horoscope(sign_id, YEARLY_BASE_URL, session)
            if data and data.get('general_text'):
                today = date.today()
                # Устанавливаем дату как 1 января текущего года
                horoscope_date = date(today.year, 1, 1)
                await insert_horoscope(sign_id, 'yearly', horoscope_date, data)
                logger.info(f"Успешно сохранен годовой гороскоп для {sign_name} на {horoscope_date.year} год")
            else:
                logger.warning(f"Не удалось получить данные для годового гороскопа {sign_name}")
        except Exception as e:
            logger.error(f"Ошибка при парсинге годового гороскопа для {sign_name}: {e}", exc_info=True)
        finally:
            delay = random.uniform(3, 7)
            logger.info(f"Пауза на {delay:.2f} секунд...")
            await asyncio.sleep(delay)

async def main():
    logger.info("Запуск парсинга годовых гороскопов")
    if not os.path.exists('data'):
        os.makedirs('data')
    await init_horoscope_db()
    
    semaphore = asyncio.Semaphore(2)
    
    async with aiohttp.ClientSession() as session:
        tasks = [safe_parse_and_insert(session, semaphore, name, sign_id) for name, sign_id in ZODIAC_MAP.items()]
        await asyncio.gather(*tasks)
    
    logger.info("Парсинг годовых гороскопов завершен")

if __name__ == "__main__":
    asyncio.run(main())
