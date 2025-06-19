import os
from dotenv import load_dotenv
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
import pdfplumber
import pandas as pd

# Загрузка .env
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANALYSIS_SERVICE_URL = os.getenv("ANALYSIS_SERVICE_URL", "http://localhost:3001/analyze")

if not BOT_TOKEN:
    raise RuntimeError("❌ Укажите BOT_TOKEN в .env")
if not OPENAI_API_KEY:
    raise RuntimeError("❌ Укажите OPENAI_API_KEY в .env")

import openai
openai.api_key = OPENAI_API_KEY

SUPPORTED_LANGS = {"uz", "ru", "en"}

def find_faq_answer(query: str, lang: str) -> str | None:
    from faq_data import FAQ_DATA
    faq = FAQ_DATA.get(lang, {})
    words = set(query.lower().split())
    best_score, best_ans = 0, None
    for q, ans in faq.items():
        q_words = set(q.lower().split())
        score = len(words & q_words) / max(1, len(q_words))
        if score > best_score:
            best_score, best_ans = score, ans
    return best_ans if best_score >= 0.5 else None

async def generate_ai_answer(question: str, lang: str) -> str:
    resp = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": f"Ты — финансовый консультант. Отвечай на {lang} языке."},
            {"role": "user", "content": question}
        ],
        temperature=0.2,
        max_tokens=400
    )
    return resp.choices[0].message.content.strip()

async def extract_text_from_pdf(path: str) -> str:
    try:
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except:
        return ""

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document:
        await update.message.reply_text("Пожалуйста, отправьте файл.")
        return
    file = await context.bot.get_file(document.file_id)
    ext = document.file_name.split('.')[-1]
    temp_dir = 'temp'
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, f"{uuid4().hex}.{ext}")
    await file.download_to_drive(file_path)
    context.user_data['uploaded_file_path'] = file_path
    await update.message.reply_text(f"Файл получен: {document.file_name}. Теперь введите команду анализа.")

async def handle_report_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().split()
    if not text:
        return
    code = text[0]
    fmt = text[1] if len(text) > 1 else 'json'
    params = {'lang': context.user_data.get('lang', 'ru')}
    if len(text) > 2:
        params['period'] = text[2]

    file_path = context.user_data.get('uploaded_file_path')
    content = ""
    if file_path:
        if file_path.endswith('.pdf'):
            content = await extract_text_from_pdf(file_path)
        elif file_path.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_path)
            content = df.to_string()

    request = f"Анализировать по коду: {code}, формат: {fmt}"
    full_prompt = f"Вот данные: {content[:1500]}\n\n{request}"

    try:
        resp = requests.post(
            ANALYSIS_SERVICE_URL,
            json={"code": code, "params": {**params, "content": content}, "format": fmt}
        )
        if resp.status_code == 200:
            if fmt in ('pdf', 'xlsx', 'docx'):
                await update.message.reply_document(resp.content, filename=f'report.{fmt}')
            else:
                data = resp.json()
                await update.message.reply_text(data.get('result', str(data)))
        else:
            await update.message.reply_text(f"❌ Ошибка анализа: {resp.text}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка подключения: {str(e)}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Здравствуйте! Отправьте файл или введите запрос вида <код_анализа> <формат> <период>")

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        lang = context.args[0].lower()
        if lang in SUPPORTED_LANGS:
            context.user_data['lang'] = lang
            await update.message.reply_text(f"Язык установлен: {lang}")
            return
    await update.message.reply_text("Использование: /language uz|ru|en")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Неизвестная команда. Используйте /start для помощи.")

def main() -> None:
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('language', set_language))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_report_request))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    print("🤖 Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
