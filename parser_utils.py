import aiosqlite
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import aiohttp
import random
from bs4 import BeautifulSoup
from constants import DB_HOROSCOPES, GENERAL_BLOCK_CLASS, SUB_CONTAINER_CLASS, BUSINESS_BLOCK_CLASS, RATE_BLOCK_CLASS, HOROSCOPE_ITEMS_CLASS

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59'
]

def setup_parser_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, 'parsers.log')

        fh = TimedRotatingFileHandler(log_file_path, when='midnight', backupCount=7)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger

async def init_horoscope_db():
    async with aiosqlite.connect(DB_HOROSCOPES) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS horoscopes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sign_id INTEGER,
                type TEXT,
                date DATE,
                general_text TEXT,
                business_text TEXT, business_rating TEXT,
                health_text TEXT, health_rating TEXT,
                love_text TEXT, love_rating TEXT,
                lunar_text TEXT, lunar_rating TEXT
            )
        ''')
        await db.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_horoscope
            ON horoscopes (sign_id, type, date)
        ''')
        
        # --- НОВАЯ ТАБЛИЦА ДЛЯ КЭША ТРАНЗИТОВ ---
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transits_cache (
                transit_date DATE PRIMARY KEY,
                planet_data TEXT
            )
        ''')
        # --- КОНЕЦ НОВОГО КОДА ---
        
        await db.commit()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=30), retry=retry_if_exception_type(aiohttp.ClientError))
async def parse_horoscope(sign_id: int, base_url: str, session: aiohttp.ClientSession):
    url = base_url + str(sign_id)
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    async with session.get(url, headers=headers, timeout=120) as response:
        response.raise_for_status()
        text = await response.text()
    
    soup = BeautifulSoup(text, 'html.parser')
    
    result = {
        "general_text": None, "business_text": None, "business_rating": None,
        "health_text": None, "health_rating": None, "love_text": None,
        "love_rating": None, "lunar_text": None, "lunar_rating": None,
    }

    general_block = soup.find("div", class_=GENERAL_BLOCK_CLASS)
    if general_block:
        result["general_text"] = general_block.get_text(" ", strip=True)

    container = soup.find("div", class_=SUB_CONTAINER_CLASS)
    if container:
        blocks = container.find_all("div", class_=BUSINESS_BLOCK_CLASS)
        for block in blocks:
            title_elem = block.find("h2")
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True).lower()

            items_block = block.find("div", class_=HOROSCOPE_ITEMS_CLASS)
            text_parts = []
            if items_block:
                paragraphs = items_block.find_all("p")
                for p in paragraphs:
                    p_text = p.get_text(strip=True)
                    if "лун" in title and p_text.startswith('Сегодня'):
                        break
                    text_parts.append(p_text)
            text = " ".join(text_parts)

            rate_block = block.find("div", class_=RATE_BLOCK_CLASS)
            rating = None
            if rate_block:
                rate_parts = [r.get_text(strip=True) for r in rate_block.find_all("div") if r.get_text(strip=True)]
                rating = '/'.join(rate_parts)

            if "бизнес" in title:
                result["business_text"] = text
                result["business_rating"] = rating
            elif "здоров" in title:
                result["health_text"] = text
                result["health_rating"] = rating
            elif "любов" in title:
                result["love_text"] = text
                result["love_rating"] = rating
            elif "лун" in title:
                result["lunar_text"] = text
                result["lunar_rating"] = rating
                
    return result

async def insert_horoscope(sign_id: int, horoscope_type: str, horoscope_date, data: dict):
    async with aiosqlite.connect(DB_HOROSCOPES) as db:
        await db.execute(
            """INSERT OR REPLACE INTO horoscopes 
               (sign_id, type, date, general_text, business_text, business_rating, 
                health_text, health_rating, love_text, love_rating, lunar_text, lunar_rating) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sign_id, horoscope_type, horoscope_date,
                data.get('general_text'), data.get('business_text'), data.get('business_rating'),
                data.get('health_text'), data.get('health_rating'), data.get('love_text'),
                data.get('love_rating'), data.get('lunar_text'), data.get('lunar_rating')
            )
        )
        await db.commit()
