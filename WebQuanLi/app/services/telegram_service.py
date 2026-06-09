import logging

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


def _masked_chat_id(chat_id: str) -> str:
    if len(chat_id) <= 4:
        return "***"
    return f"***{chat_id[-4:]}"


async def send_telegram_message(chat_id: str | None, text: str) -> dict:
    if not chat_id:
        logger.warning("Telegram message skipped: missing chat_id")
        return {"ok": False, "description": "missing chat_id"}

    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram message skipped: missing TELEGRAM_BOT_TOKEN")
        return {"ok": False, "description": "missing TELEGRAM_BOT_TOKEN"}

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            result = response.json()
    except Exception as exc:
        logger.exception("Telegram message failed for chat_id=%s", _masked_chat_id(chat_id))
        return {"ok": False, "description": str(exc)}

    if result.get("ok"):
        logger.info("Telegram message sent to chat_id=%s", _masked_chat_id(chat_id))
    else:
        logger.warning("Telegram message failed for chat_id=%s: %s", _masked_chat_id(chat_id), result.get("description"))
    return result
