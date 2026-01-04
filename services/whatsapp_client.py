import httpx
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

async def send_whatsapp_message(to_number: str, message_body: str):
    """
    Sends a WhatsApp message using the Meta Cloud API.
    """
    if not settings.ENABLE_WHATSAPP:
        logger.info("WhatsApp disabled. Skipping message.")
        return

    if not settings.WHATSAPP_TOKEN or not settings.WHATSAPP_PHONE_ID:
        logger.warning("WhatsApp credentials missing. Skipping message.")
        return

    url = f"https://graph.facebook.com/v17.0/{settings.WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    clean_number = "".join(filter(str.isdigit, to_number))
    
    payload = {
        "messaging_product": "whatsapp",
        "to": clean_number,
        "type": "text",
        "text": {"body": message_body},
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(f"WhatsApp message sent to {clean_number}")
    except httpx.HTTPStatusError as e:
        logger.error(f"WhatsApp API Error: {e.response.text}")
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")

async def send_interactive_message(to_number: str, body_text: str, buttons: list):
    """
    Sends an interactive message with buttons.
    buttons: list of tuples (id, title)
    """
    if not settings.ENABLE_WHATSAPP: return

    url = f"https://graph.facebook.com/v17.0/{settings.WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    clean_number = "".join(filter(str.isdigit, to_number))
    
    button_actions = []
    for btn_id, btn_title in buttons:
        button_actions.append({
            "type": "reply",
            "reply": {
                "id": btn_id,
                "title": btn_title
            }
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": clean_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": body_text
            },
            "action": {
                "buttons": button_actions
            }
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(f"WhatsApp interactive message sent to {clean_number}")
    except Exception as e:
        logger.error(f"Failed to send WhatsApp interactive message: {e}")

async def download_media(media_id: str) -> bytes:
    """
    Downloads media from WhatsApp API using media_id.
    """
    if not settings.ENABLE_WHATSAPP: return None

    try:
        async with httpx.AsyncClient() as client:
            # 1. Get Media URL
            url_info = f"https://graph.facebook.com/v17.0/{media_id}"
            headers = {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"}
            
            resp_info = await client.get(url_info, headers=headers)
            resp_info.raise_for_status()
            media_url = resp_info.json().get("url")
            
            if not media_url:
                logger.error("Media URL not found")
                return None

            # 2. Download Media Binary
            resp_media = await client.get(media_url, headers=headers)
            resp_media.raise_for_status()
            return resp_media.content
            
    except Exception as e:
        logger.error(f"Failed to download media {media_id}: {e}")
        return None
