import logging
import re
import requests
import base64
import os
import uuid
from flask import Flask, request, jsonify
from together import Together
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Логирование ошибок
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = "7052813240:AAFoNqx7MpQp4J1nqQKBmYebemTG5JrJYP0"
TOGETHER_API_KEY = "c4a7bc8a7e01f6e7a301d05cb7a265debf98c77755f70b33db7c288326946e9b"
IMAGE_GEN_API_URL = "https://api-inference.huggingface.co/models/XLabs-AI/flux-RealismLora"

# Папка для сохранения изображений
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "poto")
os.makedirs(IMAGE_DIR, exist_ok=True)

client = Together(api_key=TOGETHER_API_KEY)
app = Flask(__name__)

async def generate_response(user_message, lang="ru"):
    """Генерирует ответ на основе сообщения пользователя."""
    url = "https://api.together.xyz/v1/chat/completions"
    headers = {"Authorization": f"Bearer {TOGETHER_API_KEY}", "Content-Type": "application/json"}

    system_message = (
        f"Ты — Trader, дружелюбный помощник. Отвечай кратко и информативно. Всегда используй {lang} язык."
    )

    data = {
        "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.2
    }

    try:
        logger.info(f"Отправка запроса к Together API: {data}")
        response = requests.post(url, json=data, headers=headers)
        logger.info(f"Ответ Together API: {response.status_code}, {response.text}")
        if response.status_code == 200:
            ai_response = response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            return ai_response if ai_response else "Ответ от помощника пустой."
        else:
            return f"Ошибка: {response.text}"
    except Exception as e:
        logger.error(f"Ошибка при запросе к Together API: {e}")
        return f"Ошибка при запросе к Together API: {e}"

def generate_image(prompt):
    """Генерация изображения через Together API."""
    try:
        response = client.images.generate(
            prompt=prompt,
            model="black-forest-labs/FLUX.1-schnell-Free",
            width=1792,  # Full HD ширина
            height=1792,  # Исправлено на кратное 16
            steps=4,
            n=1,
            response_format="b64_json",
        )

        if response and response.data and response.data[0].b64_json:
            image_data = base64.b64decode(response.data[0].b64_json)
            image_path = os.path.join(IMAGE_DIR, f"output_{uuid.uuid4().hex}.jpg")
            with open(image_path, "wb") as f:
                f.write(image_data)
            return image_path
    except Exception as e:
        logger.error(f"Ошибка генерации изображения: {e}")
    
    return None

@app.route("/generate", methods=["POST"])
def generate():
    """Обработчик Flask для генерации изображения."""
    data = request.get_json()
    prompt = data.get("prompt", "")
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    
    image_path = generate_image(prompt)
    if image_path:
        return jsonify({"image_path": image_path})
    return jsonify({"error": "Image generation failed"}), 500

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.strip()
    logger.info(f"Получено сообщение от пользователя: {user_message}")

    if re.match(r"^[а-яА-ЯёЁ]", user_message):  # Кириллица → русский
        response = await generate_response(user_message, lang="ru")
        logger.info(f"Отправка ответа пользователю (русский): {response}")
        await update.message.reply_text(response)
    elif re.match(r"^[a-zA-Z]", user_message):  # Латиница → узбекский
        response = await generate_response(user_message, lang="uz")
        logger.info(f"Отправка ответа пользователю (узбекский): {response}")
        await update.message.reply_text(response)
    elif user_message.startswith(".") or user_message.startswith("/"):  # Генерация изображения
        prompt = user_message[1:].strip()
        logger.info(f"Запрос на генерацию изображения: {prompt}")
        image_path = generate_image(prompt)
        if image_path:
            with open(image_path, "rb") as f:
                await update.message.reply_photo(photo=f)
            logger.info("Изображение успешно сгенерировано и отправлено пользователю.")
        else:
            logger.error("Ошибка генерации изображения. Ответ не отправлен.")
            await update.message.reply_text("Генерация изображения временно недоступна.")
    else:
        logger.warning("Не удалось определить язык сообщения. Ответ не отправлен.")
        await update.message.reply_text("Не удалось определить язык сообщения.")

def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    from threading import Thread
    flask_thread = Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 5000, "debug": True})
    flask_thread.start()
    main()
