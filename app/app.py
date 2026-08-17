import os
from flask import Flask, request, jsonify
import requests
from google import genai
from google.genai import types

app = Flask(__name__)

# --- Считываем настройки из переменных окружения (Environment Variables) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secret_token_123")

# Инициализируем клиента Gemini
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = """
Ты — вежливый и гостеприимный ИИ-администратор отеля.
Твоя цель — проконсультировать гостя, ответить на вопросы по ценам и собрать данные для бронирования.

ОБЩИЕ ПРАВИЛА:
1. Отвечай кратко, понятными предложениями (удобно для чтения в WhatsApp).
2. Общайся уважительно и дружелюбно.
3. Указывай цены строго по прайс-листу.

БАЗА ЗНАНИЙ И ПРАЙС-ЛИСТ:
- Отель: Отель
- Check-in: с 14:00 | Check-out: до 12:00
- Категории номеров:
  * Стандарт: 14 000 ₸/сутки (двуспальная кровать, Wi-Fi, ТВ, санузел)
  * Люкс: 25 000 ₸/сутки (двухкомнатный, диван, балкон)
- Дополнительные услуги:
  * Завтрак: 3 000 ₸/чел
  * Парковка: Бесплатно для гостей

СЦЕНАРИЙ СБОРА БРОНИ:
Когда гость пишет, что хочет забронировать номер, попроси указать:
1. Имя
2. Дату и точное время заезда/выезда
3. Категорию номера
4. Количество гостей

КАК ТОЛЬКО ГОСТЬ НАЗВАЛ ВСЕ ДАННЫЕ И ПОДТВЕРДИЛ БРОНЬ:
В конце своего ответа сформируй итоговый блок строго в таком формате:

[BOOKING_READY]
Имя: ...
Дата и время: ...
Номер: ...
Гостей: ...
[/BOOKING_READY]

И напиши гостю: "Спасибо! Заявка передана администратору на ресепшен, мы скоро свяжемся с вами."
"""

# Хранилище сессий чата для каждого номера телефона в памяти
user_sessions = {}

def get_or_create_chat(phone_number: str):
    if phone_number not in user_sessions:
        user_sessions[phone_number] = gemini_client.chats.create(
            model='gemini-3.5-flash',
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.3,
            )
        )
    return user_sessions[phone_number]

def send_whatsapp_message(to_phone: str, message_text: str):
    """Отправка ответа пользователю в WhatsApp"""
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message_text}
    }
    try:
        res = requests.post(url, headers=headers, json=payload)
        return res.json()
    except Exception as e:
        print(f"Ошибка отправки WhatsApp: {e}")
        return None

# 1. Проверка Webhook (требование Meta при сохранении Callback URL)
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print("Webhook успешно подтвержден Meta!")
        return challenge, 200
    return "Forbidden", 403

# 2. Прием входящих сообщений от гостей
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    data = request.json

    try:
        entries = data.get('entry', [])
        for entry in entries:
            for change in entry.get('changes', []):
                value = change.get('value', {})
                messages = value.get('messages', [])
                if messages:
                    msg = messages[0]
                    from_phone = msg['from']

                    # Обрабатываем только текстовые сообщения
                    if msg.get('type') == 'text':
                        user_text = msg['text']['body']
                        print(f"Сообщение от {from_phone}: {user_text}")

                        # Передаем в Gemini
                        chat = get_or_create_chat(from_phone)
                        ai_response = chat.send_message(user_text).text
                        print(f"Ответ ИИ: {ai_response}")

                        # Отправляем ответ в WhatsApp
                        send_whatsapp_message(from_phone, ai_response)

    except Exception as e:
        print(f"Ошибка обработки запроса: {e}")

    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)