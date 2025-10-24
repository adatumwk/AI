from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from enum import StrEnum
from constants import RUSSIAN_SIGNS, ZODIAC_SIGNS_EN, TIMEZONES

class CbData(StrEnum):
    # Главное меню
    GET_NOW = "menu_get_now"
    SETTINGS = "menu_settings"
    HELP = "menu_help"
    # Настройки
    CHANGE_ZODIAC = "settings_change_zodiac"
    CHANGE_TIMEZONE = "settings_change_timezone"
    CHANGE_TIME = "settings_change_time"
    BACK_TO_MAIN = "settings_back_to_main"
    # Отмена
    CANCEL = "action_cancel"

def get_main_menu_keyboard():
    """Создает главное меню."""
    keyboard = [
        [InlineKeyboardButton("🔮 Получить гороскоп", callback_data=CbData.GET_NOW)],
        [InlineKeyboardButton("⚙️ Настройки", callback_data=CbData.SETTINGS)],
        [InlineKeyboardButton("❓ Помощь", callback_data=CbData.HELP)]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_menu_keyboard():
    """Создает меню настроек."""
    keyboard = [
        [InlineKeyboardButton("👤 Изменить знак зодиака", callback_data=CbData.CHANGE_ZODIAC)],
        [InlineKeyboardButton("🌍 Изменить часовой пояс", callback_data=CbData.CHANGE_TIMEZONE)],
        [InlineKeyboardButton("⏰ Изменить время уведомлений", callback_data=CbData.CHANGE_TIME)],
        [InlineKeyboardButton("⬅️ Назад в главное меню", callback_data=CbData.BACK_TO_MAIN)]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_zodiac_keyboard(is_settings=False):
    """is_settings=True добавляет кнопку 'Назад в настройки'."""
    keyboard = [
        [InlineKeyboardButton(RUSSIAN_SIGNS[sign], callback_data=f'zodiac_{sign}') for sign in ZODIAC_SIGNS_EN[i:i+3]]
        for i in range(0, len(ZODIAC_SIGNS_EN), 3)
    ]
    back_button = InlineKeyboardButton("⬅️ Назад", callback_data=CbData.SETTINGS) if is_settings else InlineKeyboardButton("❌ Отмена", callback_data=CbData.CANCEL)
    keyboard.append([back_button])
    return InlineKeyboardMarkup(keyboard)

def get_timezone_keyboard(is_settings=False):
    keyboard = [
        [InlineKeyboardButton(tz, callback_data=f'tz_{tz}') for tz in TIMEZONES[i:i+4]]
        for i in range(0, len(TIMEZONES), 4)
    ]
    back_button = InlineKeyboardButton("⬅️ Назад", callback_data=CbData.SETTINGS) if is_settings else InlineKeyboardButton("❌ Отмена", callback_data=CbData.CANCEL)
    keyboard.append([back_button])
    return InlineKeyboardMarkup(keyboard)

def get_time_keyboard(is_settings=False):
    keyboard = [
        [InlineKeyboardButton(f"{h:02d}:00", callback_data=f'time_{h:02d}:00') for h in range(i, i+4)]
        for i in range(0, 24, 4)
    ]
    back_button = InlineKeyboardButton("⬅️ Назад", callback_data=CbData.SETTINGS) if is_settings else InlineKeyboardButton("❌ Отмена", callback_data=CbData.CANCEL)
    keyboard.append([back_button])
    return InlineKeyboardMarkup(keyboard)

def get_horoscope_type_keyboard():
    keyboard = [
        [InlineKeyboardButton("Ежедневный", callback_data='h_type_daily')],
        [InlineKeyboardButton("Еженедельный", callback_data='h_type_weekly')],
        [InlineKeyboardButton("Ежемесячный", callback_data='h_type_monthly')],
        [InlineKeyboardButton("Годовой", callback_data='h_type_yearly')]
    ]
    return InlineKeyboardMarkup(keyboard)
