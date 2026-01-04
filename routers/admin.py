from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select
from typing import List
import os
import io
import base64
from datetime import date, datetime, timedelta
from jose import JWTError, jwt
from PIL import Image
from sqlalchemy import func, case
from fastapi.responses import StreamingResponse, Response

from core.database import get_session
from models import Feedback, FeedbackRead, SurveyListRead, SurveyDetailRead
from core.config import settings
from core.security import create_access_token, verify_password, get_password_hash
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="admin/login")

def get_current_admin(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None or username != settings.ADMIN_USERNAME:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != settings.ADMIN_USERNAME or form_data.password != settings.ADMIN_PASSWORD:
        logger.warning(f"Failed login attempt for user: {form_data.username}")
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    logger.info(f"Admin logged in: {form_data.username}")
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/reports", response_model=List[FeedbackRead])
async def get_reports(
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    try:
        feedbacks = session.exec(select(Feedback)).all()
        results = []
        for f in feedbacks:
            f_dict = f.model_dump()
            if f.photo_air:
                f_dict['photo_air'] = base64.b64encode(f.photo_air).decode('utf-8')
            if f.photo_washroom:
                f_dict['photo_washroom'] = base64.b64encode(f.photo_washroom).decode('utf-8')
            if f.photo_receipt:
                f_dict['photo_receipt'] = base64.b64encode(f.photo_receipt).decode('utf-8')
            results.append(FeedbackRead(**f_dict))
        return results
    except Exception as e:
        logger.error(f"Error fetching reports: {e}")
        raise HTTPException(status_code=500, detail="Error fetching reports")

@router.delete("/feedback/{feedback_id}")
async def delete_feedback(
    feedback_id: int,
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    try:
        feedback = session.get(Feedback, feedback_id)
        if not feedback:
            logger.warning(f"Attempt to delete non-existent feedback: {feedback_id}")
            raise HTTPException(status_code=404, detail="Feedback not found")
        session.delete(feedback)
        session.commit()
        logger.info(f"Feedback deleted: {feedback_id}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting feedback {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail="Error deleting feedback")

@router.patch("/feedback/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: int,
    status_update: dict,
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    try:
        feedback = session.get(Feedback, feedback_id)
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")
        
        if feedback.status == "resolved":
             raise HTTPException(status_code=400, detail="Cannot update resolved feedback")

        new_status = status_update.get("status")
        if new_status not in ["pending", "resolved", "Reviewed"]:
             raise HTTPException(status_code=400, detail="Invalid status")

        feedback.status = new_status
        session.add(feedback)
        session.commit()
        session.refresh(feedback)
        logger.info(f"Feedback {feedback_id} status updated to {new_status}")
        return feedback
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating feedback status {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail="Error updating feedback status")

# Filters Endpoints
@router.get("/filters/ro-codes")
async def get_ro_codes(
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    try:
        logger.info(f"Fetching RO codes for user: {current_user}")
        ro_codes = session.exec(select(Feedback.ro_number).distinct()).all()
        return [code for code in ro_codes if code]
    except Exception as e:
        logger.error(f"Error fetching ro codes: {e}")
        raise HTTPException(status_code=500, detail="Error fetching RO codes")

@router.get("/filters/statuses")
async def get_statuses(
    current_user: str = Depends(get_current_admin)
):
    return ["Pending", "Verified", "Not Verified", "Reviewed"]

@router.get("/filters/date-range")
async def get_date_range(
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    try:
        min_date = session.exec(select(func.min(Feedback.created_at))).first()
        max_date = session.exec(select(func.max(Feedback.created_at))).first()
        return {
            "min_date": min_date.date() if min_date else None,
            "max_date": max_date.date() if max_date else None
        }
    except Exception as e:
        logger.error(f"Error fetching date range: {e}")
        raise HTTPException(status_code=500, detail="Error fetching date range")

# Metrics Endpoint
@router.get("/metrics")
async def get_metrics(
    ro_code: str = None,
    status: str = None,
    date_from: date = None,
    date_to: date = None,
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    try:
        logger.info(f"Fetching metrics for user: {current_user}")
        conditions = []
        if ro_code:
            conditions.append(Feedback.ro_number == ro_code)
        if status:
            conditions.append(Feedback.status == status)
        if date_from:
            conditions.append(Feedback.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            conditions.append(Feedback.created_at <= datetime.combine(date_to, datetime.max.time()))
            
        stmt = select(
            func.count(Feedback.id).label("total"),
            func.sum(case((Feedback.status == "Verified", 1), else_=0)).label("verified"),
            func.sum(case((Feedback.status == "Not Verified", 1), else_=0)).label("not_verified"),
            func.sum(case((Feedback.status.in_(["Pending", "pending"]), 1), else_=0)).label("pending"),
        ).where(*conditions)
        
        result = session.exec(stmt).first()
        
        def safe_int(val):
            return int(val) if val else 0
            
        return {
            "total": safe_int(result[0]),
            "verified": safe_int(result[1]),
            "not_verified": safe_int(result[2]),
            "pending": safe_int(result[3])
        }
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        raise HTTPException(status_code=500, detail="Error fetching metrics")

# Charts Endpoints
@router.get("/charts/daily-trend")
async def get_daily_trend(
    ro_code: str = None,
    status: str = None,
    date_from: date = None,
    date_to: date = None,
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    try:
        conditions = []
        if ro_code:
            conditions.append(Feedback.ro_number == ro_code)
        if status:
            conditions.append(Feedback.status == status)
        if date_from:
            conditions.append(Feedback.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            conditions.append(Feedback.created_at <= datetime.combine(date_to, datetime.max.time()))

        stmt = select(
            func.date(Feedback.created_at).label("date"),
            func.count(Feedback.id).label("count")
        ).where(*conditions).group_by(func.date(Feedback.created_at)).order_by("date")
        
        results = session.exec(stmt).all()
        return [{"date": r.date, "count": r.count} for r in results]
    except Exception as e:
        logger.error(f"Error fetching daily trend: {e}")
        raise HTTPException(status_code=500, detail="Error fetching daily trend")

@router.get("/charts/not-verified-distribution")
async def get_not_verified_dist(
    ro_code: str = None,
    date_from: date = None,
    date_to: date = None,
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    try:
        conditions = [Feedback.status == "Not Verified"] 
        if ro_code:
            conditions.append(Feedback.ro_number == ro_code)
        if date_from:
            conditions.append(Feedback.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            conditions.append(Feedback.created_at <= datetime.combine(date_to, datetime.max.time()))

        results = session.exec(stmt).all()
        return [{"date": r.date, "count": r.count} for r in results]
    except Exception as e:
        logger.error(f"Error fetching not verified distribution: {e}")
        raise HTTPException(status_code=500, detail="Error fetching not verified distribution")

@router.get("/charts/washroom-feedback")
async def get_washroom_feedback(
    ro_code: str = None,
    status: str = None,
    date_from: date = None,
    date_to: date = None,
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    try:
        conditions = []
        if ro_code:
            conditions.append(Feedback.ro_number == ro_code)
        if status:
            conditions.append(Feedback.status == status)
        if date_from:
            conditions.append(Feedback.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            conditions.append(Feedback.created_at <= datetime.combine(date_to, datetime.max.time()))

        stmt = select(
            Feedback.rating_washroom,
            func.count(Feedback.id).label("count")
        ).where(*conditions).group_by(Feedback.rating_washroom)
        
        results = session.exec(stmt).all()
        total = sum(r.count for r in results)
        
        data = []
        for r in results:
            category = r.rating_washroom if r.rating_washroom is not None else "Unknown"
            count = r.count
            percentage = (count / total * 100) if total > 0 else 0
            data.append({"category": str(category), "count": count, "percentage": round(percentage, 1)})
        return data
    except Exception as e:
        logger.error(f"Error fetching washroom feedback: {e}")
        raise HTTPException(status_code=500, detail="Error fetching washroom feedback")

@router.get("/charts/air-facility-feedback")
async def get_air_facility_feedback(
    ro_code: str = None,
    status: str = None,
    date_from: date = None,
    date_to: date = None,
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    try:
        conditions = []
        if ro_code:
            conditions.append(Feedback.ro_number == ro_code)
        if status:
            conditions.append(Feedback.status == status)
        if date_from:
            conditions.append(Feedback.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            conditions.append(Feedback.created_at <= datetime.combine(date_to, datetime.max.time()))

        stmt = select(
            Feedback.rating_air,
            func.count(Feedback.id).label("count")
        ).where(*conditions).group_by(Feedback.rating_air)
        
        results = session.exec(stmt).all()
        total = sum(r.count for r in results)
        
        data = []
        for r in results:
            category = r.rating_air if r.rating_air is not None else "Unknown"
            count = r.count
            percentage = (count / total * 100) if total > 0 else 0
            data.append({"category": str(category), "count": count, "percentage": round(percentage, 1)})
        return data
    except Exception as e:
        logger.error(f"Error fetching air facility feedback: {e}")
        raise HTTPException(status_code=500, detail="Error fetching air facility feedback")

# Reviews Management Endpoints
def get_rating_emoji(value: int) -> str:
    if value is None:
        return None
    if value <= 2:
        return "😢"
    elif value == 3:
        return "😐"
    else:
        return "😊"

@router.get("/surveys", response_model=dict)
async def get_surveys(
    page: int = 1,
    limit: int = 25,
    ro_code: str = None,
    status: str = None,
    search: str = None,
    date_from: date = None,
    date_to: date = None,
    sort_by: str = "created_at",
    order: str = "desc",
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    try:
        offset = (page - 1) * limit
        query = select(Feedback)
        
        if ro_code:
            query = query.where(Feedback.ro_number == ro_code)
        if status:
            if status.lower() == "reviewed":
                query = query.where(Feedback.status == "Reviewed")
            elif status.lower() == "pending":
                query = query.where(Feedback.status == "Pending")
        if date_from:
            query = query.where(Feedback.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            query = query.where(Feedback.created_at <= datetime.combine(date_to, datetime.max.time()))
        if search:
            query = query.where((Feedback.phone.contains(search)) | (Feedback.id == search) | (Feedback.comment.contains(search)))

        total_count = len(session.exec(query).all())

        if hasattr(Feedback, sort_by):
            col = getattr(Feedback, sort_by)
            if order == "desc":
                query = query.order_by(col.desc())
            else:
                query = query.order_by(col.asc())
        else:
             query = query.order_by(Feedback.created_at.desc())

        query = query.offset(offset).limit(limit)
        results = session.exec(query).all()
        
        surveys = []
        for r in results:
            surveys.append(SurveyListRead(
                id=r.id,
                submission_date=r.created_at,
                mobile_number=r.phone,
                ro_code=r.ro_number,
                rating_air=get_rating_emoji(r.rating_air),
                rating_washroom=get_rating_emoji(r.rating_washroom),
                has_receipt=bool(r.photo_receipt),
                has_image_air=bool(r.photo_air),
                has_image_washroom=bool(r.photo_washroom),
                comments_preview=r.comment[:50] + "..." if r.comment and len(r.comment) > 50 else r.comment,
                status=r.status,
                reviewed_at=r.reviewed_at,
                reviewed_by=r.reviewed_by
            ))
            
        return {
            "surveys": surveys,
            "total_count": total_count,
            "page": page,
            "total_pages": (total_count + limit - 1) // limit
        }
    except Exception as e:
        logger.error(f"Error fetching surveys: {e}")
        raise HTTPException(status_code=500, detail="Error fetching surveys")

@router.get("/surveys/{feedback_id}", response_model=SurveyDetailRead)
async def get_survey_detail(
    feedback_id: int,
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    feedback = session.get(Feedback, feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Survey not found")
        
    return SurveyDetailRead(
        id=feedback.id,
        submission_date=feedback.created_at,
        mobile_number=feedback.phone,
        ro_code=feedback.ro_number,
        rating_air=feedback.rating_air,
        rating_washroom=feedback.rating_washroom,
        comment=feedback.comment,
        status=feedback.status,
        reviewed_at=feedback.reviewed_at,
        reviewed_by=feedback.reviewed_by,
        has_receipt=bool(feedback.photo_receipt),
        has_image_air=bool(feedback.photo_air),
        has_image_washroom=bool(feedback.photo_washroom)
    )

@router.patch("/surveys/{feedback_id}/mark-reviewed")
async def mark_reviewed(
    feedback_id: int,
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    feedback = session.get(Feedback, feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Survey not found")
        
    if feedback.status == "Reviewed":
        return {"ok": True, "message": "Already reviewed"}
        
    feedback.status = "Reviewed"
    feedback.reviewed_at = datetime.utcnow()
    feedback.reviewed_by = current_user
    session.add(feedback)
    session.commit()
    session.refresh(feedback)
    return {"ok": True, "message": "Marked as reviewed", "survey": feedback}

@router.get("/surveys/{feedback_id}/images/{image_type}")
async def get_survey_image(
    feedback_id: int,
    image_type: str,
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    feedback = session.get(Feedback, feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Survey not found")
        
    image_data = None
    content_type = "image/jpeg"
    
    if image_type == "air":
        image_data = feedback.photo_air
    elif image_type == "washroom":
        image_data = feedback.photo_washroom
    elif image_type == "receipt":
        image_data = feedback.photo_receipt
        if image_data and image_data.startswith(b'%PDF'):
            content_type = "application/pdf"
    else:
        raise HTTPException(status_code=400, detail="Invalid image type")
        
    if not image_data:
        raise HTTPException(status_code=404, detail="Image not found")
        
    return StreamingResponse(io.BytesIO(image_data), media_type=content_type)

@router.get("/surveys/{feedback_id}/images/thumbnail/{image_type}")
async def get_survey_thumbnail(
    feedback_id: int,
    image_type: str,
    size: int = 150,
    session: Session = Depends(get_session),
    current_user: str = Depends(get_current_admin)
):
    feedback = session.get(Feedback, feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Survey not found")
        
    image_data = None
    if image_type == "air":
        image_data = feedback.photo_air
    elif image_type == "washroom":
        image_data = feedback.photo_washroom
    
    if not image_data:
        raise HTTPException(status_code=404, detail="Image not found")
        
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            img.thumbnail((size, size))
            buf = io.BytesIO()
            img.save(buf, format=img.format or "JPEG")
            buf.seek(0)
            return StreamingResponse(buf, media_type=f"image/{img.format.lower() if img.format else 'jpeg'}")
    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")
        raise HTTPException(status_code=500, detail="Error generating thumbnail")
