import asyncio
import os
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.enums import ChatAction
from dotenv import load_dotenv

# 1. Загружаем переменные окружения (наши ключи)
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 2. Конфигурация Gemini
genai.configure(api_key=GEMINI_API_KEY)
# Выбираем модель. 'gemini-1.5-flash' - быстрая и бесплатная
model = genai.GenerativeModel('gemini-2.5-flash')

# 3. Конфигурация Aiogram (Telegram Bot)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# 4. Обработчики (Хэндлеры)

# Хэндлер на команду /start
@dp.message(CommandStart())
async def send_welcome(message: types.Message):
    await message.reply("Привет! Я твой личный ассистент с Gemini AI. 🤖\n"
                        "Просто задай мне любой вопрос.")

# Хэндлер на любые текстовые сообщения (кроме команд)
@dp.message(F.text)
async def handle_message(message: types.Message):
    user_text = message.text
    
    # Показываем "Печатает..." в чате
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    try:
        # 5. Обращение к API Gemini
        # Используем .generate_content_async для асинхронного вызова
        response = await model.generate_content_async(user_text)
        
        # 6. Отправка ответа пользователю
        await message.reply(response.text)

    except Exception as e:
        # Обработка ошибок, если Gemini не ответил
        print(f"Ошибка при обращении к Gemini: {e}")
        await message.reply("Извините, произошла ошибка при обработке вашего запроса. 😥"
                            "Попробуйте еще раз.")

# 7. Функция запуска бота
async def main():
    print("Бот запускается...")
    # Запускаем polling (постоянный опрос Telegram на новые сообщения)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
