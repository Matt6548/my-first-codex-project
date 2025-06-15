import os
import requests
from langdetect import detect
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from faq_data import FAQ_DATA

# 🔐 Ключи берутся из переменных окружения
BOT_TOKEN = '7697595103:AAElGIoz281OUoWluFQOSlO7l79rM5vAP9M'  # ← сюда токен Telegram
GROQ_API_KEY = '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'  # ← сюда Groq API ключ

SUPPORTED_LANGS = {"uz", "ru", "en"}


def find_faq_answer(query: str, lang: str) -> str | None:
    """Поиск лучшего совпадения в FAQ по ключевым словам (≥ 50%)."""
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
    """Запрос к Groq API (LLaMA 3)."""
    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = f"Ты финансовый и юридический консультант. Отвечай на {lang} языке. Пиши ясно и коротко."

    data = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        "temperature": 0.2,
        "max_tokens": 400
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        result = response.json()
        ai_answer = result['choices'][0]['message']['content'].strip()
        return f"🤖 ИИ-ответ:\n{ai_answer}"
    except Exception as e:
        print(f"Groq API error: {e}")
        return "Извините, произошла ошибка при обращении к ИИ."


def log_interaction(question: str, answer: str) -> None:
    """Логирование в файл."""
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


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError('Укажите TELEGRAM_BOT_TOKEN в переменных окружения.')

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('language', set_language))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(pdf|excel)$"), handle_report_request))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, answer_question))


    print("🤖 Бот запущен...")
    application.run_polling()


# ==== Flask-заглушка для Render ====
from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return "Бот запущен и работает!"

def run_flask():
    app.run(host="0.0.0.0", port=10000)

# 🟢 Запуск Flask-потока и бота
threading.Thread(target=run_flask).start()

if __name__ == '__main__':
    main()
# 1. Импорт
import os
from uuid import uuid4

# 2. Определение функции до main()
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
        f"📄 Файл получен: {document.file_name}\nКакой тип отчёта вы хотите подготовить?\n\nНапишите: `pdf` или `excel`",
        parse_mode="Markdown"
    )

import pandas as pd
from fpdf import FPDF

async def handle_report_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text.lower().strip()
    file_path = context.user_data.get("uploaded_file_path")

    if message not in ["pdf", "excel"] or not file_path:
        return  # Игнорируем, если нет файла или команды

    try:
        # Создание заглушки-отчёта на основе содержимого
        report_path = ""
        if message == "excel":
            df = pd.DataFrame([["Файл успешно получен", file_path]])
            report_path = file_path.replace(".", "_report.") + "xlsx"
            df.to_excel(report_path, index=False)
        elif message == "pdf":
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt="Отчёт по загруженному файлу", ln=True)
            pdf.cell(200, 10, txt=f"Путь: {file_path}", ln=True)
            report_path = file_path.replace(".", "_report.") + "pdf"
            pdf.output(report_path)

        # Отправляем отчёт пользователю
        await update.message.reply_document(document=open(report_path, "rb"))

        # Удаляем временные файлы
        os.remove(file_path)
        os.remove(report_path)
        context.user_data.clear()

    except Exception as e:
        await update.message.reply_text(f"❗ Ошибка при создании отчёта: {e}")
