import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# Системный промпт для отеля
SYSTEM_INSTRUCTION = """
Ты — вежливый и гостеприимный ИИ-администратор отеля.
Твоя задача — консультировать гостей по услугам, номерам, бронированию и правилам проживания.
Отвечай четко, коротко и доброжелательно.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Здравствуйте! Я ИИ-администратор отеля. Чем могу вам помочь?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    try:
        # Запрос к Gemini 2.5 Flash
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_text,
            config={'system_instruction': SYSTEM_INSTRUCTION}
        )
        bot_reply = response.text
    except Exception as e:
        logger.error(f"Ошибка Gemini: {e}")
        bot_reply = "Извините, возникла временная ошибка при обработке запроса."

    await update.message.reply_text(bot_reply)

if __name__ == '__main__':
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
    
    # Запуск бота в режиме Polling (не нужны никакие Webhook и публичные URL!)
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот запущен...")
    app.run_polling()
