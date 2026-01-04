from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session
from datetime import datetime
import json
from core.database import get_session
from models import Feedback, WhatsAppState
from services.whatsapp_client import send_whatsapp_message, send_interactive_message, download_media
from core.config import settings
from core.logger import get_logger

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
logger = get_logger(__name__)

@router.get("/webhook")
async def verify_webhook(request: Request):
    """
    Verifies the webhook with Meta.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == settings.WHATSAPP_TOKEN: # Using same token for verify for simplicity, or add VERIFY_TOKEN
            logger.info("Webhook verified successfully.")
            return int(challenge)
        else:
            raise HTTPException(status_code=403, detail="Verification failed")
    return {"status": "ok"}

@router.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    """
    Handles incoming WhatsApp messages.
    """
    try:
        body = await request.json()
        
        # Check if it's a message
        if body.get("object") == "whatsapp_business_account":
            for entry in body.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    
                    if messages:
                        message = messages[0]
                        from_number = message.get("from")
                        msg_type = message.get("type")
                        
                        # Handle text or interactive button reply
                        user_input = ""
                        media_id = None
                        
                        if msg_type == "text":
                            user_input = message.get("text", {}).get("body", "")
                        elif msg_type == "interactive":
                            user_input = message.get("interactive", {}).get("button_reply", {}).get("id", "")
                        elif msg_type == "image":
                            media_id = message.get("image", {}).get("id")
                        
                        # Process in background to avoid timeout
                        background_tasks.add_task(process_whatsapp_message, from_number, user_input, media_id, session)
                        
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"status": "error"}

async def process_whatsapp_message(phone: str, user_input: str, media_id: str, session: Session):
    # Get or Create State
    state_record = session.get(WhatsAppState, phone)
    if not state_record:
        state_record = WhatsAppState(phone=phone, state="GREETING")
        session.add(state_record)
        session.commit()
        session.refresh(state_record)
    
    current_state = state_record.state
    temp_data = json.loads(state_record.temp_data)
    
    logger.info(f"Processing message from {phone} in state {current_state}. Input: {user_input}, Media: {media_id}")

    next_state = current_state
    
    # State Machine
    if current_state == "GREETING":
        # Always greet and ask for Air Rating
        await send_interactive_message(
            phone, 
            "Welcome to our Feedback Service! 👋\n\nPlease rate our *Air Filling Service*:",
            [("air_1", "1 Star 😞"), ("air_2", "2 Stars 😐"), ("air_3", "3 Stars 😃")]
        )
        next_state = "RATING_AIR"

    elif current_state == "RATING_AIR":
        if user_input.startswith("air_"):
            rating = int(user_input.split("_")[1])
            temp_data["rating_air"] = rating
            await send_whatsapp_message(phone, "Thanks! Would you like to upload a photo of the Air Filling area? (Send photo or type 'skip')")
            next_state = "PHOTO_AIR"
        else:
            await send_whatsapp_message(phone, "Please select a rating using the buttons above.")

    elif current_state == "PHOTO_AIR":
        if media_id:
            # Download and store photo
            photo_bytes = await download_media(media_id)
            if photo_bytes:
                # Store temporarily in memory? No, database BLOBs are heavy for temp_data JSON.
                # We can't store bytes in JSON. 
                # Strategy: Create the Feedback row NOW and update it incrementally? 
                # Or just store a placeholder and ask user to re-upload if session lost?
                # Better: Create Feedback row now with status='draft'
                pass 
            # For simplicity in this flow, let's assume we skip photo storage in temp_data 
            # and just say "Photo received". 
            # REAL IMPLEMENTATION: We need to store this. 
            # Let's create a partial Feedback record if not exists?
            # Or just store in a temporary file?
            # Let's use a simple approach: We will ask for photos at the end? No, flow says "for each".
            # Okay, let's store bytes in a separate temporary table or just use the Feedback table directly?
            # Let's use the Feedback table. We need a way to link this session to a feedback ID.
            # Let's store feedback_id in temp_data.
            pass
        
        # Handling Photo Logic with Feedback Table
        feedback_id = temp_data.get("feedback_id")
        if not feedback_id:
            # Create new feedback row
            feedback = Feedback(
                phone=phone, 
                feedback_method="whatsapp", 
                status="draft",
                rating_air=temp_data.get("rating_air"),
                session_id=phone # Using phone as session_id for WhatsApp
            )
            session.add(feedback)
            session.commit()
            session.refresh(feedback)
            temp_data["feedback_id"] = feedback.id
        
        feedback = session.get(Feedback, temp_data["feedback_id"])
        
        if media_id:
            photo_bytes = await download_media(media_id)
            if photo_bytes:
                feedback.photo_air = photo_bytes
                session.add(feedback)
                session.commit()
                await send_whatsapp_message(phone, "Photo received! 📸")
        
        # Move to next step regardless of photo or skip
        await send_interactive_message(
            phone, 
            "Now, please rate our *Washroom Cleanliness*:",
            [("wash_1", "1 Star 😞"), ("wash_2", "2 Stars 😐"), ("wash_3", "3 Stars 😃")]
        )
        next_state = "RATING_WASHROOM"

    elif current_state == "RATING_WASHROOM":
        if user_input.startswith("wash_"):
            rating = int(user_input.split("_")[1])
            
            # Update Feedback
            feedback_id = temp_data.get("feedback_id")
            if feedback_id:
                feedback = session.get(Feedback, feedback_id)
                feedback.rating_washroom = rating
                session.add(feedback)
                session.commit()
            
            await send_whatsapp_message(phone, "Thanks! Would you like to upload a photo of the Washroom? (Send photo or type 'skip')")
            next_state = "PHOTO_WASHROOM"
        else:
             await send_whatsapp_message(phone, "Please select a rating using the buttons above.")

    elif current_state == "PHOTO_WASHROOM":
        feedback_id = temp_data.get("feedback_id")
        if feedback_id and media_id:
            photo_bytes = await download_media(media_id)
            if photo_bytes:
                feedback = session.get(Feedback, feedback_id)
                feedback.photo_washroom = photo_bytes
                session.add(feedback)
                session.commit()
                await send_whatsapp_message(phone, "Photo received! 📸")

        await send_whatsapp_message(phone, "Almost done! Any additional comments? (Type your comment or 'skip')")
        next_state = "COMMENT"

    elif current_state == "COMMENT":
        feedback_id = temp_data.get("feedback_id")
        if feedback_id:
            feedback = session.get(Feedback, feedback_id)
            if user_input.lower() != "skip":
                feedback.comment = user_input
            
            feedback.status = "submitted"
            feedback.terms_accepted = True # Implicit via WhatsApp usage
            session.add(feedback)
            session.commit()
            
            # Trigger Immediate Report if Negative
            from services.tasks import send_immediate_negative_report
            if feedback.rating_air == 1 or feedback.rating_washroom == 1:
                # We need to run this async, but we are in async function.
                # However, tasks.py imports might cause circular dependency if not careful.
                # We did local import above.
                await send_immediate_negative_report(feedback.id)

        await send_whatsapp_message(phone, "Thank you for your feedback! Have a great day! 🌟")
        
        # Reset State
        session.delete(state_record)
        session.commit()
        return

    # Update State
    state_record.state = next_state
    state_record.temp_data = json.dumps(temp_data)
    state_record.updated_at = datetime.utcnow()
    session.add(state_record)
    session.commit()
