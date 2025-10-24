import logging
import pytz
import json
import aiosqlite
from datetime import date, timedelta
from telegram import Bot
from telegram.error import Forbidden
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

# --- ИСПРАВЛЕННЫЙ ИМПОРТ (ПОПЫТКА 5, ФИНАЛЬНАЯ) ---
# Мы импортируем "фабрику" для создания объектов
from kerykeion.factory import AstrologicalSubjectFactory

from config import BOT_TOKEN
from constants import DB_JOBS, RUSSIAN_SIGNS, DB_HOROSCOPES
from database import get_user_data, save_user_data
from horoscope_fetcher import get_horoscope_from_db

logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN)
scheduler = AsyncIOScheduler(jobstores={'default': SQLAlchemyJobStore(url=DB_JOBS)})

# --- НОВАЯ ФУНКЦИЯ КЭШИРОВАНИЯ (НА AstrologicalSubjectFactory) ---
async def cache_daily_transits():
    """
    Рассчитывает транзиты на завтра и сохраняет их в кэш (БД).
    Использует kerykeion (v1.0.0+).
    """
    try:
        logger.info("[КЭШЕР]: Начинаю кэширование транзитов на завтра...")
        
        # 1. Получаем дату "завтра"
        tomorrow_date = date.today() + timedelta(days=1)
        
        # 2. Создаем "фабрику" для расчета транзитов.
        # Используем Лондон (UTC) и 12:00 дня как стандарт.
        factory = AstrologicalSubjectFactory(
            name="Transits", 
            day=tomorrow_date.day, 
            month=tomorrow_date.month, 
            year=tomorrow_date.year, 
            hour=12, 
            minute=0, 
            city="London", 
            nation="UK"
        )
        
        # 3. Получаем рассчитанный объект ("субъект")
        subject = factory.get_subject()

        # 4. Собираем данные в словарь
        planet_data = {}
        
        # Собираем положения 10 основных планет
        planets = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']
        for p_name in planets:
            # Используем getattr, чтобы получить subject.sun, subject.moon и т.д.
            planet_obj = getattr(subject, p_name) 
            planet_data[p_name.capitalize()] = { # Сохраняем с большой буквы (Sun, Moon)
                "sign": planet_obj.sign,       # Знак (напр., 'Aries')
                "lon": round(planet_obj.lon, 2) # Градус в знаке
            }
            
        # 5. Превращаем в JSON и сохраняем в БД
        data_json = json.dumps(planet_data)
        
        async with aiosqlite.connect(DB_HOROSCOPES) as db:
            await db.execute(
                "INSERT OR REPLACE INTO transits_cache (transit_date, planet_data) VALUES (?, ?)",
                (tomorrow_date, data_json)
            )
            await db.commit()
            
        logger.info(f"[КЭШЕР]: Транзиты на {tomorrow_date} успешно закэшированы (kerykeion v1+).")
        
    except Exception as e:
        logger.error(f"[КЭШЕР]: Ошибка при кэшировании транзитов: {e}", exc_info=True)
# --- КОНЕЦ НОВОЙ ФУНКЦИИ ---


def get_pytz_timezone(tz_str: str):
    """УЛУЧШЕНИЕ: Более надежная конвертация строки UTC в объект pytz."""
    if tz_str == "UTC+0":
        return pytz.timezone("Etc/GMT")
    
    sign = tz_str[3]
    offset = int(tz_str[4:])
    # Etc/GMT имеет обратный знак: Etc/GMT-3 это UTC+3
    flipped_sign = '-' if sign == '+' else '+'
    return pytz.timezone(f"Etc/GMT{flipped_sign}{offset}")

def format_horoscope_message(horoscope_data, sign_name, h_type_rus):
    """Создает красивое форматированное сообщение для отправки в Telegram."""
    sign_name_rus = RUSSIAN_SIGNS.get(sign_name, sign_name)
    
    if not horoscope_data or not horoscope_data.get('general_text'):
        return f"К сожалению, {h_type_rus} гороскоп для знака {sign_name_rus} еще не готов. Попробуйте позже."

    horoscope_date = horoscope_data['date']
    
    if h_type_rus == 'ежедневный':
        date_display = horoscope_date.strftime('%d.%m.%Y')
    elif h_type_rus == 'еженедельный':
        date_display = f"неделю с {horoscope_date.strftime('%d.%m.%Y')}"
    elif h_type_rus == 'ежемесячный':
        date_display = horoscope_date.strftime('%Y-%m')
    elif h_type_rus == 'годовой':
        date_display = f"{horoscope_date.year} год"
    else:
        date_display = horoscope_date.strftime('%Y-%m-%d')
        
    message_parts = [
        f"🔮 *{h_type_rus.capitalize()} гороскоп для знака {sign_name_rus} на {date_display}*\n",
        f"*{horoscope_data.get('general_text', 'Нет данных.')}*\n"
    ]

    sections = {
        "business": f"💼 *Бизнес ({horoscope_data.get('business_rating', '-')})*",
        "health": f"💪 *Здоровье ({horoscope_data.get('health_rating', '-')})*",
        "love": f"❤️ *Любовь ({horoscope_data.get('love_rating', '-')})*",
        "lunar": f"🌙 *Лунный календарь ({horoscope_data.get('lunar_rating', '-')})*"
    }

    for key, title in sections.items():
        text_key = f"{key}_text"
        if horoscope_data.get(text_key):
            message_parts.append(f"{title}\n{horoscope_data[text_key]}\n")
            
    return "\n".join(message_parts)

async def send_daily_horoscope_job(user_id: int):
    try:
        user = await get_user_data(user_id)
        if not user or not user.get('is_active') or not user.get('zodiac_sign'): return
        
        horoscope = await get_horoscope_from_db(user['zodiac_sign'], 'daily')
        message = format_horoscope_message(horoscope, user['zodiac_sign'], 'ежедневный')
        
        await bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
        logger.info(f"Отправлен ежедневный гороскоп для {user_id}")
    except Forbidden:
        logger.warning(f"Пользователь {user_id} заблокировал бота. Деактивация.")
        await save_user_data(user_id, is_active=False)
    except Exception as e:
        logger.error(f"Ошибка отправки гороскопа для {user_id}: {e}", exc_info=True)

def update_user_jobs(user_id: int, tz: str, time: str):
    job_id = f'daily_{user_id}'
    hour, minute = map(int, time.split(':'))
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        send_daily_horoscope_job, 'cron', hour=hour, minute=minute,
        timezone=get_pytz_timezone(tz), id=job_id, args=[user_id]
    )
    logger.info(f"Задача для {user_id} обновлена: {tz} {time}")
