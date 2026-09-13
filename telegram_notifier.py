import os
import requests
from dotenv import load_dotenv

load_dotenv()


def send_telegram_message(message: str) -> bool:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing from .env")

    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID is missing from .env")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }

    response = requests.post(
        url,
        data=payload,
        timeout=30,
    )

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            f"Telegram send failed: {data}"
        )

    return True