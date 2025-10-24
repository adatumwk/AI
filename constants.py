# URLs & Selectors for Parsers
DAILY_BASE_URL = 'https://www.globalmsk.ru/horoscope/tomorrow/'
WEEKLY_BASE_URL = 'https://www.globalmsk.ru/horoscope/week/'
MONTHLY_BASE_URL = 'https://www.globalmsk.ru/horoscope/month/'
YEARLY_BASE_URL = 'https://www.globalmsk.ru/horoscope/year/'

GENERAL_BLOCK_CLASS = "horoscope_text"
SUB_CONTAINER_CLASS = "horoscope_text_sub"
BUSINESS_BLOCK_CLASS = "business_block"
RATE_BLOCK_CLASS = "rate_block"
HOROSCOPE_ITEMS_CLASS = "horoscope_items"

# Zodiac Signs
ZODIAC_MAP = {
    'Aries': 3, 'Taurus': 5, 'Gemini': 7, 'Cancer': 8, 'Leo': 1,
    'Virgo': 2, 'Libra': 6, 'Scorpio': 4, 'Sagittarius': 12,
    'Capricorn': 9, 'Aquarius': 10, 'Pisces': 11
}
ZODIAC_SIGNS_EN = list(ZODIAC_MAP.keys())
RUSSIAN_SIGNS = {
    'Aries': 'Овен', 'Taurus': 'Телец', 'Gemini': 'Близнецы',
    'Cancer': 'Рак', 'Leo': 'Лев', 'Virgo': 'Дева', 'Libra': 'Весы',
    'Scorpio': 'Скорпион', 'Sagittarius': 'Стрелец',
    'Capricorn': 'Козерог', 'Aquarius': 'Водолей', 'Pisces': 'Рыбы'
}

# Timezones
TIMEZONES = [f"UTC{i:+d}" for i in range(-12, 15)]

# Database Paths
DB_USERS = 'data/users.db'
DB_HOROSCOPES = 'data/horoscopes.db'
DB_JOBS = 'sqlite:///data/jobs.db'
