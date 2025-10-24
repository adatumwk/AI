import logging
import pytz
import json
import aiosqlite
from datetime import date, timedelta
from telegram import Bot
from telegram.error import Forbidden
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

# --- CORRECT IMPORTS (v5.0.2) ---
# We ONLY need the factory for calculations
from kerykeion.chart_data_factory import ChartDataFactory
# We don't need AstrologicalSubjectModel here, the factory returns it.
# --- END CORRECTION ---

from config import BOT_TOKEN
from constants import DB_JOBS, RUSSIAN_SIGNS, DB_HOROSCOPES
from database import get_user_data, save_user_data
from horoscope_fetcher import get_horoscope_from_db

logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN)
scheduler = AsyncIOScheduler(jobstores={'default': SQLAlchemyJobStore(url=DB_JOBS)})

# --- UPDATED CACHING FUNCTION (Using ChartDataFactory correctly) ---
async def cache_daily_transits():
    """
    Calculates tomorrow's transits and saves them to the cache DB.
    Uses kerykeion (v5.0.2).
    """
    try:
        logger.info("[CACHER]: Starting transit caching for tomorrow...")

        # 1. Get tomorrow's date
        tomorrow_date = date.today() + timedelta(days=1)

        # --- CORRECT LOGIC (v5.0.2 API) ---

        # 2. Create the ChartDataFactory directly with raw data
        # The factory handles geocoding and timezone internally.
        factory = ChartDataFactory(
            name="Transits", # Name is just a label
            day=tomorrow_date.day,
            month=tomorrow_date.month,
            year=tomorrow_date.year,
            hour=12, # Use noon UTC as standard for transits
            minute=0,
            city="London", # Location used for timezone lookup (UTC)
            nation="UK"
        )

        # 3. Get the calculated subject object from the .subject property
        subject = factory.subject # This IS the AstrologicalSubjectModel instance

        # --- END CORRECTION ---

        # 4. Extract planet data into a dictionary
        planet_data = {}
        planets = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']
        for p_name in planets:
            planet_obj = getattr(subject, p_name)
            planet_data[p_name.capitalize()] = { # Store with capitalized keys (Sun, Moon)
                "sign": planet_obj.sign,       # e.g., 'Aries'
                "lon": round(planet_obj.lon, 2) # Degree within the sign
            }

        # 5. Convert to JSON and save to the database
        data_json = json.dumps(planet_data)

        async with aiosqlite.connect(DB_HOROSCOPES) as db:
            await db.execute(
                "INSERT OR REPLACE INTO transits_cache (transit_date, planet_data) VALUES (?, ?)",
                (tomorrow_date, data_json)
            )
            await db.commit()

        logger.info(f"[CACHER]: Transits for {tomorrow_date} successfully cached (kerykeion v5+).")

    except Exception as e:
        logger.error(f"[CACHER]: Error during transit caching: {e}", exc_info=True)
# --- END UPDATED FUNCTION ---


def get_pytz_timezone(tz_str: str):
    """More reliable conversion from UTC string to pytz object."""
    if tz_str == "UTC+0":
        return pytz.timezone("Etc/GMT")

    sign = tz_str[3]
    offset = int(tz_str[4:])
    # Etc/GMT has reversed signs: Etc/GMT-3 is UTC+3
    flipped_sign = '-' if sign == '+' else '+'
    return pytz.timezone(f"Etc/GMT{flipped_sign}{offset}")

def format_horoscope_message(horoscope_data, sign_name, h_type_rus):
    """Creates a formatted message for Telegram."""
    sign_name_rus = RUSSIAN_SIGNS.get(sign_name, sign_name)

    if not horoscope_data or not horoscope_data.get('general_text'):
        return f"Sorry, the {h_type_rus} horoscope for {sign_name_rus} isn't ready yet. Please try later."

    horoscope_date = horoscope_data['date']

    if h_type_rus == 'daily':
        date_display = horoscope_date.strftime('%d.%m.%Y')
    elif h_type_rus == 'weekly':
        date_display = f"the week starting {horoscope_date.strftime('%d.%m.%Y')}"
    elif h_type_rus == 'monthly':
        date_display = horoscope_date.strftime('%Y-%m')
    elif h_type_rus == 'yearly':
        date_display = f"{horoscope_date.year}"
    else:
        date_display = horoscope_date.strftime('%Y-%m-%d')

    message_parts = [
        f"🔮 *{h_type_rus.capitalize()} horoscope for {sign_name_rus} on {date_display}*\n",
        f"*{horoscope_data.get('general_text', 'No data.')}*\n"
    ]

    sections = {
        "business": f"💼 *Business ({horoscope_data.get('business_rating', '-')})*",
        "health": f"💪 *Health ({horoscope_data.get('health_rating', '-')})*",
        "love": f"❤️ *Love ({horoscope_data.get('love_rating', '-')})*",
        "lunar": f"🌙 *Lunar Calendar ({horoscope_data.get('lunar_rating', '-')})*"
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
        message = format_horoscope_message(horoscope, user['zodiac_sign'], 'daily')

        await bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
        logger.info(f"Sent daily horoscope to {user_id}")
    except Forbidden:
        logger.warning(f"User {user_id} blocked the bot. Deactivating.")
        await save_user_data(user_id, is_active=False)
    except Exception as e:
        logger.error(f"Error sending horoscope to {user_id}: {e}", exc_info=True)

def update_user_jobs(user_id: int, tz: str, time: str):
    job_id = f'daily_{user_id}'
    hour, minute = map(int, time.split(':'))
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        send_daily_horoscope_job, 'cron', hour=hour, minute=minute,
        timezone=get_pytz_timezone(tz), id=job_id, args=[user_id]
    )
    logger.info(f"Updated job for {user_id}: {tz} {time}")
