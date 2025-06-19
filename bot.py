import os
import requests
from uuid import uuid4
from langdetect import detect
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from flask import Flask
import threading
import pandas as pd
import pdfplumber
from dotenv import load_dotenv
from faq_data import FAQ_DATA
import openai

# 🔐 Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

SUPPORTED_LANGS = {"uz", "ru", "en"}

def find_faq_answer(query: str, lang: str) -> str | None:
    faq = FAQ_DATA.get(lang, {})
    words = set(query.lower().split())
    best_score = 0
    best_answer = None
    for q, ans in faq.items():
        q_words = set(q.lower().split())
        if not q_words:
            continue
        score = len(words & q_words) / len(q_words)
        if score > best_score:
            best_score = score
            best_answer = ans
    return best_answer if best_score >= 0.5 else None

async def generate_ai_answer(question: str, lang: str) -> str:
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[
                {"role": "system", "content": f"Ты финансовый и юридический консультант. Отвечай на {lang} языке. Пиши ясно и коротко."},
                {"role": "user", "content": question}
            ],
            temperature=0.2,
            max_tokens=400
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return "Ошибка при обращении к ИИ."

def log_interaction(question: str, answer: str) -> None:
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"Q: {question}\nA: {answer}\n\n")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Здравствуйте! Задайте вопрос или используйте /language uz|ru|en для выбора языка."
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        lang = context.args[0].lower()
        if lang in SUPPORTED_LANGS:
            context.user_data["lang"] = lang
            await update.message.reply_text(f"Язык установлен: {lang}.")
            return
    await update.message.reply_text("Пример использования: /language uz|ru|en")

async def answer_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question_raw = update.message.text.strip()
    lang = context.user_data.get("lang")
    if not lang:
        try:
            lang = detect(question_raw).split("-")[0]
        except Exception:
            lang = "ru"
        if lang not in SUPPORTED_LANGS:
            lang = "ru"
        context.user_data["lang"] = lang
    answer = find_faq_answer(question_raw, lang)
    if not answer:
        answer = await generate_ai_answer(question_raw, lang)
    await update.message.reply_text(answer)
    log_interaction(question_raw, answer)

async def extract_text_from_pdf(path: str) -> str:
    try:
        with pdfplumber.open(path) as pdf:
            text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
            return text.strip()
    except Exception as e:
        print(f"Ошибка извлечения текста: {e}")
        return ""

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document:
        await update.message.reply_text("Пожалуйста, отправьте файл.")
        return
    file = await context.bot.get_file(document.file_id)
    file_extension = document.file_name.split('.')[-1]
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, f"{uuid4().hex}.{file_extension}")
    await file.download_to_drive(file_path)
    context.user_data["uploaded_file_path"] = file_path
    await update.message.reply_text(
        f"📄 Файл получен: {document.file_name}\nНапишите, какой анализ или отчёт вы хотите получить по содержимому файла."
    )

async def handle_report_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.message.text.strip()
    file_path = context.user_data.get("uploaded_file_path")
    if not file_path:
        return
    try:
        lang = context.user_data.get("lang", "ru")
        if file_path.endswith(".pdf"):
            content = await extract_text_from_pdf(file_path)
        elif file_path.endswith(".xlsx"):
            df = pd.read_excel(file_path)
            content = df.to_string()
        else:
            await update.message.reply_text("Формат файла не поддерживается для анализа.")
            return

        full_prompt = f"Вот данные: {content[:1500]}\n\n{request}"
        answer = await generate_ai_answer(full_prompt, lang)
        await update.message.reply_text(f"📊 Анализ:\n\n{answer}")

        os.remove(file_path)
        context.user_data.clear()
    except Exception as e:
        await update.message.reply_text(f"❗ Ошибка при анализе файла: {e}")

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError('Укажите TELEGRAM_BOT_TOKEN в переменных окружения.')
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('language', set_language))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_report_request))
    application.add_handler(MessageHandler(filters.COMMAND, answer_question))
    print("🤖 Бот запущен...")
    application.run_polling()

# ==== Flask-заглушка для Render ====
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот запущен и работает!"

def run_flask():
    app.run(host="0.0.0.0", port=10000)

threading.Thread(target=run_flask).start()

if __name__ == '__main__':
    main()
