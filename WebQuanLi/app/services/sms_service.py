import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

ESMS_SEND_URL = "http://rest.esms.vn/MainService.svc/json/SendMultipleMessage_V4_post_json/"


async def send_sms(phone: str, content: str) -> dict:
    """Send SMS via eSMS.vn API (SmsType=2 — CSKH)."""
    payload = {
        "ApiKey": settings.ESMS_API_KEY,
        "Content": content,
        "Phone": phone,
        "SecretKey": settings.ESMS_SECRET_KEY,
        "Brandname": settings.ESMS_BRANDNAME,
        "SmsType": settings.ESMS_SMS_TYPE,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(ESMS_SEND_URL, json=payload)
            result = resp.json()
            if result.get("CodeResult") == "100":
                logger.info(f"SMS sent to {phone}: {content[:50]}...")
            else:
                logger.warning(f"SMS failed: {result}")
            return result
    except Exception as e:
        logger.error(f"SMS error: {e}")
        return {"CodeResult": "-1", "ErrorMessage": str(e)}


async def send_face_mismatch_sms(phone: str, plate: str, expected_name: str):
    """Send face mismatch warning SMS to vehicle manager."""
    content = (
        f"[CANH BAO] Xe {plate}: Khuon mat khong khop voi the RFID. "
        f"Tai xe du kien: {expected_name}. Vui long kiem tra ngay!"
    )
    return await send_sms(phone, content)


async def send_drowsiness_sms(phone: str, plate: str, level: str):
    """Send drowsiness alert SMS."""
    content = (
        f"[CANH BAO BUON NGU] Xe {plate}: Phat hien tai xe buon ngu muc {level}. "
        f"Vui long lien he tai xe!"
    )
    return await send_sms(phone, content)
