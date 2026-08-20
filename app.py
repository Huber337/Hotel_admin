import os
import re
import logging
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application
from google import genai
from google.genai import types
from groq import Groq
from whatsapp_api_client_python import API

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Flask
web_app = Flask(__name__)

# Токены и Переменные Окружения
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://hotel-whatsapp-bot-tfhs.onrender.com")

# Переменные GREEN-API для WhatsApp
GREEN_ID_INSTANCE = os.environ.get("GREEN_ID_INSTANCE")
GREEN_API_TOKEN = os.environ.get("GREEN_API_TOKEN")

# Инициализация клиента GREEN-API
green_api = None
if GREEN_ID_INSTANCE and GREEN_API_TOKEN:
    green_api = API.GreenApi(GREEN_ID_INSTANCE, GREEN_API_TOKEN)

# ID администратора
ADMIN_CHAT_ID_ENV = os.environ.get("ADMIN_CHAT_ID")
ADMIN_CHAT_ID = int(ADMIN_CHAT_ID_ENV) if ADMIN_CHAT_ID_ENV else None

# Инициализация Telegram Application
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build() if TELEGRAM_TOKEN else None

# Инициализация клиентов ИИ
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Системный промпт
SYSTEM_INSTRUCTION = """
Ты — профессиональный, гостеприимный и вежливый ИИ-администратор зоны отдыха "Эдем".

ТВОЯ РОЛЬ И ЦЕЛЬ:
Консультировать гостей по услугам зоны отдыха "Эдем" (отель, гостиница, бассейн, кафе, тапчаны), помогать с выбором номеров и услуг, отвечать на вопросы по ценам и правилам, а также поэтапно собирать данные для бронирования.

КРИТИЧЕСКИЕ ПРАВИЛА ВЕДЕНИЯ ДИАЛОГА (СТРОГО):
1.Никогда не высылай базу знаний целиком за один раз!
2. ПОШАГОВЫЙ ДИАЛОГ: Давай ответ строго на тот вопрос, который задал гость, и задавай встречный вопрос только если это требуется по контексту.
3. Общайся доброжелательно, вежливо и гостеприимно.
4. Отвечай лаконично и структурировано. Используй форматирование (списки, жирный шрифт), чтобы текст легко читался в мессенджерах (WhatsApp/Telegram).
5. Применяй техники продаж: после ответа на вопрос гостя мягко подводи его к выбору или бронированию (например: «Желаете забронировать номер на определенные даты?» или «Подсказать вам по наличию свободного тапчана?»).
6. Никогда не выдумывай несуществующие акции, скидки, номерной фонд или услуги, кроме указанных в базе знаний.
7. ПРАВИЛО ПРИВЕТСТВИЯ: Никогда НЕ здоровайся повторно («Здравствуйте», «Добрый день» и т.д.) в процессе диалога. Приветствие уже отправлено пользователю при старте. Сразу переходи к ответу или следующему вопросу.
8. РАБОТА С ДАТАМИ: В каждом запросе тебе передается текущая дата. Если гость говорит «сегодня», «завтра», «в эту субботу» — самостоятельно высчитывай точную дату в формате ДД.ММ.ГГГГ и уточняй её у гостя для подтверждения.

==================================================
БАЗА ЗНАНИЙ И ПРАЙС-ЛИСТ ЗОНЫ ОТДЫХА "ЭДЕМ"
==================================================

1. ЛОКАЦИЯ И АДРЕС:
- Адрес: улица Сайрамская, 192/1 (напротив 5 поликлиники).
- Инструкция: Если гость спрашивает адрес, расположение или маршрут — отдавай чёткую текстовую метку с адресом и ориентиром, а также предоставляй ссылку на 2GIS: https://2gis.kz/shymkent/firm/70000001026712814

2. ТЕРРИТОРИЯ И БАССЕЙН:
- Возрастные категории:
  * Дети: от 4 до 13 лет включительно.
  * Взрослые: с 14 лет.
  * Дети до 4 лет — бесплатно.

- Стоимость входа на территорию бассейна:
  * Будние дни:
    - Детский: 4 000 тг
    - Взрослый: 6 000 тг
  * Выходные дни:
    - Детский: 5 000 тг
    - Взрослый: 7 000 тг

- Акции на территории бассейна:
  * Для многодетных семей (от 5 человек): скидка 20% (при предъявлении подтверждающих документов).
  * Именинникам: бесплатный вход в день рождения (при предъявлении документа).
  * Вечерняя скидка: после 18:00 скидка 20% на вход.

- Правила посещения бассейна:
  1. Дети до 14 лет допускаются только в сопровождении родителей или совершеннолетних сопровождающих.
  2. С 14 до 18 лет посетители допускаются самостоятельно, но ответственность за их безопасность и поведение несут родители.
  3. Администрация не осуществляет присмотр за несовершеннолетними и не несёт ответственности за детей, оставленных без присмотра.

3. ЕДА, НАПИТКИ И КАФЕ:
- Вход со своей едой и напитками на территорию бассейна ЗАПРЕЩЕН.
- На территории работает кафе. Время работы: с 10:00 до 22:00.
- Кухня: европейская и национальная.
- Доставка к тапчану/бассейну: Заказывать еду и напитки прямо к тапчану или к бассейну разрешено из нашего кафе. Приносить свои продукты запрещено.

4. ВНУТРЕННИЙ РЕГЛАМЕНТ И ОГРАНИЧЕНИЯ:
- Домашние животные: Проживание с питомцами строжайше ЗАПРЕЩЕНО.
- Курение: Курение в номерах категорически ЗАПРЕЩЕНО (разрешено только в специально отведённых зонах для курения на территории).

5. АРЕНДА ТАПЧАНОВ:
* ВНИМАНИЕ: В стоимость аренды тапчана ВХОДНЫЕ БИЛЕТЫ НА БАССЕЙН НЕ ВКЛЮЧЕНЫ (оплачиваются отдельно за каждого человека). Всегда предупреждай об этом гостей при вопросах про тапчаны!
* Администрация оставляет за собой право бронирования тапчанов заранее.

- Стоимость:
  * На полный день:
    - VIP тапчан: 20 000 тг
    - Стандартный тапчан: 15 000 тг
    - Малый тапчан: 10 000 тг
  * На полдня:
    - VIP тапчан: 12 000 тг
    - Стандартный тапчан: 8 000 тг
    - Малый тапчан: 6 000 тг

6. ПРОЖИВАНИЕ В ОТЕЛЕ:
- Стандартный заезд — с 14:00, выезд — до 12:00.
- Ранний заезд и поздний выезд: Если гость спрашивает про заезд раньше 14:00 или выезд после 12:00, отвечай строго: «Ранний заезд и поздний выезд возможны по предварительному согласованию и при наличии свободных номеров (уточняется у администратора на ресепшен)».
- Завтрак ВКЛЮЧЕН в стоимость всех номеров отеля.

- Категории и цены номеров в отеле (за 1 ночь):
  1. Люкс (35 000 тг/ночь):
     - Вместимость: до 2 человек.
     - Удобства: 1 большая двуспальная кровать, балкон с видом на бассейн, ванна, кондиционер, холодильник, электрический чайник.
  2. Делюкс (40 000 тг/ночь):
     - Вместимость: до 2 человек.
     - Удобства: 1 большая двуспальная кровать, балкон с видом на бассейн, ванна, кондиционер, холодильник, электрический чайник.
  3. Люкс повышенной комфортности (50 000 тг/ночь):
     - Вместимость: до 2 человек.
     - Удобства: 1 большая двуспальная кровать, балкон с видом на бассейн, ванна, кондиционер, холодильник, электрический чайник.
  4. Апартаменты с 2 спальнями (65 000 тг/ночь):
     - Площадь: 150 кв.м, апартаменты целиком.
     - Спальня 1: 2 односпальные кровати.
     - Спальня 2: 1 очень большая двуспальная кровать.
     - Гостиная: 1 диван-кровать.
     - Удобства: вид на бассейн, кондиционер, ковровое покрытие, телевизор с плоским экраном, холодильник.

7. ВТОРОЙ КОРПУС / ГОСТИНИЦА:
- В зоне отдыха "Эдем" также есть корпус Гостиницы.
- Цены на номера в корпусе Гостиницы уточняются индивидуально у администратора.

==================================================
СЦЕНАРИИ ВЗАИМОДЕЙСТВИЯ И ПОШАГОВЫЙ СБОР ДАННЫХ
==================================================

1. ПРАВИЛА ВЕДЕНИЯ ДИАЛОГА И ВАЛИДАЦИИ:
- Пошаговый запрос (ОБЯЗАТЕЛЬНО): Никогда не запрашивай все 5 параметров одновременно единым списком! Бери данные поэтапно в ходе естественной беседы (по 1–2 вопроса за раз).
- Уточнение дат: Если гость пишет абстрактно («завтра», «на эти выходные»), высчитай даты на основе системного контекста, переспроси и уточни конкретную дату и ориентировочное время заезда/выезда.
- Формат телефона: Если гость передал некорректный или неполный номер телефона, вежливо попроси перепроверить и указать правильный номер для связи.
- Предварительный расчет: Перед финализацией брони озвучь гостю итоговую ориентировочную стоимость выбранных услуг/номера.

2. СПИСОК ОБЯЗАТЕЛЬНЫХ ПАРАМЕТРОВ ДЛЯ БРОНИ:
1. Имя
2. Даты и точное время заезда/выезда
3. Номер телефона для связи
4. Тип размещения (Отель, Гостиница или Тапчан) и категория (Люкс, Делюкс, VIP-тапчан и т.д.)
5. Количество гостей (взрослых и детей)

3. ФИНАЛЬНЫЙ ШАГ (Когда ВСЕ 5 параметров собраны):
Как только ты получишь все 5 пунктов данных, отправителю высылается вежливая благодарность, а в самом конце ответа СТРОГО генерируется системный блок без изменений названий полей:

Спасибо! Заявка передана администратору на ресепшен, мы скоро свяжемся с вами для подтверждения.

[BOOKING_READY]
Имя: <Имя гостя>
Дата и время: <Даты и точное время заезда/выезда>
Номер для связи: <Номер телефона>
Тип: <Тип размещения / категория номера или тапчана>
Гостей: <Количество взрослых и детей>
[/BOOKING_READY]
"""

user_chats = {}
user_histories = {}

def get_user_chat(chat_id):
    if chat_id not in user_chats:
        user_chats[chat_id] = gemini_client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.7,
            )
        )
    return user_chats[chat_id]

def ask_groq(chat_id, user_text: str, today_str: str) -> str:
    if not groq_client:
        return "Извините, сервис временно недоступен. Попробуйте написать чуть позже."

    if chat_id not in user_histories:
        user_histories[chat_id] = [{"role": "system", "content": SYSTEM_INSTRUCTION}]

    prompt_with_context = f"[Системный контекст: Сегодняшняя дата — {today_str}]\n{user_text}"
    user_histories[chat_id].append({"role": "user", "content": prompt_with_context})

    try:
        completion = groq_client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=user_histories[chat_id],
            temperature=0.7,
            max_tokens=1024
        )
        bot_reply = completion.choices[0].message.content
        user_histories[chat_id].append({"role": "assistant", "content": bot_reply})
        return bot_reply
    except Exception as e:
        logger.error(f"Ошибка Groq API: {e}", exc_info=True)
        return "Извините, возникла заминка при обработке запроса. Попробуйте еще раз через минуту."

def generate_ai_response(chat_id, user_text: str) -> str:
    today_str = datetime.now().strftime("%d.%m.%Y")
    prompt_with_context = f"[Системный контекст: Сегодняшняя дата — {today_str}]\n{user_text}"

    try:
        if gemini_client:
            chat = get_user_chat(chat_id)
            response = chat.send_message(prompt_with_context)
            if response and response.text:
                if chat_id not in user_histories:
                    user_histories[chat_id] = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
                user_histories[chat_id].append({"role": "user", "content": prompt_with_context})
                user_histories[chat_id].append({"role": "assistant", "content": response.text})
                return response.text
    except Exception as e:
        logger.warning(f"Ошибка Gemini ({e}). Переключаемся на Groq fallback...")

    return ask_groq(chat_id, user_text, today_str)

async def send_admin_notification(booking_data: str, source_info: str):
    if not ADMIN_CHAT_ID or not telegram_app:
        return
    admin_notification_md = (
        f"🔔 *НОВАЯ ЗАЯВКА НА БРОНИРОВАНИЕ!*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{booking_data}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{source_info}"
    )
    try:
        await telegram_app.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_notification_md,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Ошибка отправки уведомления админу: {e}")

# ---------------- WEBHOOK МАРШРУТЫ FLASK ----------------

@web_app.route('/')
def health_check():
    return "OK", 200

@web_app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    """Асинхронный обработчик сообщений Telegram без сторонних тредов"""
    if not telegram_app:
        return "Bot non active", 500

    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, telegram_app.bot)

        if update and update.message and update.message.text:
            chat_id = update.effective_chat.id
            user_text = update.message.text.strip()
            user_info = update.effective_user

            # Реакция на команду /start
            if user_text.startswith("/start"):
                welcome_text = (
                    "Здравствуйте! 👋 Добро пожаловать в зону отдыха *«Эдем»*!\n\n"
                    "Я ваш виртуальный администратор. Могу подсказать по ценам на бассейн, "
                    "номерам в отеле, тапчанам и помочь забронировать отдых.\n\n"
                    "Чем могу вам помочь?"
                )
                asyncio.run(telegram_app.bot.send_message(chat_id=chat_id, text=welcome_text, parse_mode="Markdown"))
                return "ok", 200

            # Игнорируем сообщения из групп
            if update.effective_chat.type in ["group", "supergroup"]:
                return "ok", 200

            # Генерация ответа через ИИ
            raw_reply = generate_ai_response(chat_id, user_text)

            pattern = r"\[BOOKING_READY\](.*?)\[/BOOKING_READY\]"
            match = re.search(pattern, raw_reply, re.DOTALL)
            user_reply = raw_reply

            if match:
                booking_data = match.group(1).strip()
                user_reply = re.sub(pattern, "", raw_reply, flags=re.DOTALL).strip()
                username_str = f"@{user_info.username}" if user_info.username else "без username"
                source_info = (
                    f"👤 *Профиль клиента в TG:* {user_info.full_name} ({username_str})\n"
                    f"🆔 *ID чата:* `{chat_id}`"
                )
                asyncio.run(send_admin_notification(booking_data, source_info))

            # Отправка ответа пользователю
            try:
                asyncio.run(telegram_app.bot.send_message(chat_id=chat_id, text=user_reply, parse_mode="Markdown"))
            except Exception:
                clean_text = user_reply.replace("*", "").replace("_", "")
                asyncio.run(telegram_app.bot.send_message(chat_id=chat_id, text=clean_text))

        return "ok", 200
    except Exception as e:
        logger.error(f"Ошибка в Telegram Webhook: {e}", exc_info=True)
        return "ok", 200

@web_app.route('/whatsapp-webhook', methods=['POST'])
def whatsapp_webhook():
    data = request.get_json(silent=True) or {}
    type_webhook = data.get("typeWebhook")

    if type_webhook == "incomingMessageReceived":
        message_data = data.get("messageData", {})
        sender_data = data.get("senderData", {})
        
        wa_chat_id = sender_data.get("chatId")
        sender_name = sender_data.get("senderName", "Клиент WhatsApp")
        text_message = ""

        if message_data.get("typeMessage") == "textMessage":
            text_message = message_data.get("textMessageData", {}).get("textMessage", "")
        elif message_data.get("typeMessage") == "extendedTextMessage":
            text_message = message_data.get("extendedTextMessageData", {}).get("text", "")

        if text_message and wa_chat_id and green_api:
            session_id = f"wa_{wa_chat_id}"
            raw_reply = generate_ai_response(session_id, text_message)

            pattern = r"\[BOOKING_READY\](.*?)\[/BOOKING_READY\]"
            match = re.search(pattern, raw_reply, re.DOTALL)
            user_reply = raw_reply

            if match:
                booking_data = match.group(1).strip()
                user_reply = re.sub(pattern, "", raw_reply, flags=re.DOTALL).strip()
                phone_clean = wa_chat_id.replace("@c.us", "")
                source_info = (
                    f"🟢 *Источник:* WhatsApp\n"
                    f"👤 *Имя:* {sender_name}\n"
                    f"📱 *Телефон:* +{phone_clean}"
                )
                asyncio.run(send_admin_notification(booking_data, source_info))

            try:
                clean_reply = user_reply.replace("**", "*")
                green_api.sending.sendMessage(wa_chat_id, clean_reply)
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения в GREEN-API: {e}")

    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)
