import aiosqlite
import logging
import sqlite3
from constants import DB_HOROSCOPES, ZODIAC_MAP

logger = logging.getLogger(__name__)

async def get_horoscope_from_db(sign_name: str, horoscope_type: str):
    sign_id = ZODIAC_MAP.get(sign_name)
    if not sign_id:
        logger.error(f"Неверное имя знака: {sign_name}")
        return None
    try:
        async with aiosqlite.connect(DB_HOROSCOPES, detect_types=sqlite3.PARSE_DECLTYPES) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM horoscopes WHERE sign_id = ? AND type = ? ORDER BY date DESC LIMIT 1',
                (sign_id, horoscope_type)
            )
            data = await cursor.fetchone()
            if data:
                return dict(data)
            else:
                logger.warning(f"Гороскоп типа {horoscope_type} для {sign_name} не найден в БД.")
                return None
    except aiosqlite.Error as e:
        logger.error(f"Ошибка БД при получении гороскопа для {sign_name}: {e}")
        return None
