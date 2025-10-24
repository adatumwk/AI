import aiosqlite
import logging
import sqlite3 # Импортируем для detect_types
from constants import DB_USERS

logger = logging.getLogger(__name__)

async def init_user_db():
    async with aiosqlite.connect(DB_USERS) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                language_code TEXT,
                is_premium BOOLEAN,
                zodiac_sign TEXT,
                timezone TEXT,
                notification_time TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                
                -- НОВЫЕ ПОЛЯ ДЛЯ НАТАЛЬНОЙ КАРТЫ --
                birth_date DATE,
                birth_time TIME,
                birth_city TEXT,
                birth_lat REAL, -- Широта
                birth_lon REAL   -- Долгота
            )
        ''')
        await db.commit()
    logger.info("База данных пользователей инициализирована.")

async def get_user_data(user_id: int):
    # Используем detect_types для авто-преобразования DATE/TIME
    async with aiosqlite.connect(DB_USERS, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def save_user_data(user_id: int, **kwargs):
    if not kwargs: return
    async with aiosqlite.connect(DB_USERS) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        
        # --- УЛУЧШЕНИЕ: Адаптивная проверка колонок ---
        cursor = await db.execute(f"PRAGMA table_info(users)")
        existing_columns = {row[1] for row in await cursor.fetchall()}
        
        # Фильтруем kwargs, оставляя только те, что есть в таблице
        valid_kwargs = {k: v for k, v in kwargs.items() if k in existing_columns}
        if not valid_kwargs:
            logger.warning(f"Нет валидных колонок для обновления у {user_id}")
            return
        # --- Конец улучшения ---

        set_clause = ', '.join([f"{key} = ?" for key in valid_kwargs])
        values = list(valid_kwargs.values()) + [user_id]
        
        await db.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", tuple(values))
        await db.commit()
        logger.info(f"Данные для {user_id} сохранены: {valid_kwargs}")

async def get_all_active_users():
    """Возвращает список ID всех активных пользователей."""
    user_ids = []
    async with aiosqlite.connect(DB_USERS) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT user_id FROM users WHERE is_active = TRUE")
        rows = await cursor.fetchall()
        if rows:
            user_ids = [row['user_id'] for row in rows]
    logger.info(f"Найдено {len(user_ids)} активных пользователей для рассылки.")
    return user_ids
