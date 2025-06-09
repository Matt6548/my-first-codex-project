import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from langdetect import detect
import openai

from faq_data import FAQ_DATA

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

SUPPORTED_LANGS = {"uz", "ru", "en"}


def find_faq_answer(query: str, lang: str) -> str | None:
    """Return best matching answer from FAQ based on keywords."""
    faq = FAQ_DATA.get(lang, {})
    words = set(query.split())
    best_score = 0
    best_answer = None
    for q, ans in faq.items():
        q_words = set(q.split())
        if not q_words:
            continue
        score = len(words & q_words) / len(q_words)
        if score > best_score:
            best_score = score
            best_answer = ans
    if best_score > 0:
        return best_answer
    return None


async def generate_ai_answer(question: str, lang: str) -> str:
    """Call OpenAI API to get an answer."""
    if not OPENAI_API_KEY:
        return "Извините, я не знаю ответ на этот вопрос."
    openai.api_key = OPENAI_API_KEY
    prompt = f"Answer the following legal or financial question in {lang}: {question}"
    try:
        resp = openai.Completion.create(engine="text-davinci-003", prompt=prompt, max_tokens=100)
        return resp.choices[0].text.strip()
    except Exception:
        return "Извините, я не знаю ответ на этот вопрос."


def log_interaction(question: str, answer: str) -> None:
    """Append interaction to log file."""
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"Q: {question}\nA: {answer}\n\n")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a greeting message when the /start command is issued."""
    await update.message.reply_text(
        "Здравствуйте! Используйте /language uz|ru|en для выбора языка."
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /language command to set user language."""
    if context.args:
        lang = context.args[0].lower()
        if lang in SUPPORTED_LANGS:
            context.user_data["lang"] = lang
            await update.message.reply_text(f"Language set to {lang}.")
            return
    await update.message.reply_text("Usage: /language uz|ru|en")

async def answer_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with an answer from the FAQ or fallback to AI."""
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

    answer = find_faq_answer(question_raw.lower(), lang)
    if not answer:
        answer = await generate_ai_answer(question_raw, lang)

    await update.message.reply_text(answer)
    log_interaction(question_raw, answer)

def main() -> None:
    """Run the Telegram bot."""
    token = BOT_TOKEN
    if not token:
        raise RuntimeError('Specify bot token via TELEGRAM_BOT_TOKEN environment variable.')

    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('language', set_language))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, answer_question))

    application.run_polling()

if __name__ == '__main__':
    main()
