# my-first-codex-project

This project contains a Telegram bot that answers legal and financial questions. It supports Uzbek, Russian and English.

## Quick start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set the Telegram bot token in the `TELEGRAM_BOT_TOKEN` environment variable.
   Optionally set `OPENAI_API_KEY` to enable AI answers when the FAQ does not contain a response.
3. Run the bot:
   ```bash
   python bot.py
   ```

The bot determines the user's language via the first message or the `/language` command. It searches the FAQ using keywords, and if nothing is found it queries OpenAI for a reply. All interactions are appended to `log.txt` for analysis.
