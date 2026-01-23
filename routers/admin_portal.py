from datetime import date, datetime, timedelta
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select, func, case, col
from sqlalchemy.orm import aliased
import io
import csv

from core.database import get_session
from models import Feedback, AdminUser, ReviewHistory, FOMapping, UserROMapping
from models_refactor import Branch
from services.auth_service import get_current_admin
from schemas.schemas import DashboardStats, ChartData, PieChartData, WorkflowUpdate

router = APIRouter(prefix="/api", tags=["admin-portal"])

# --- Helpers ---

def apply_rbac(query, user: AdminUser):
    """Applies Role-Based Access Control filters to the query."""
    if user.role == "superuser" or user.role == "Vendor":
        return query
    elif user.role in ["DO", "FO", "DRSM", "SRH"]:
        # Unified mapping logic for all hierarchy levels
        # Checks the user_ro_mapping table for assigned ROs
        sub = select(UserROMapping.ro_code).where(UserROMapping.username == user.username)
        return query.where(Feedback.ro_number.in_(sub))
    else:
        # RO (or default admin) sees their branch
        return query.where(Feedback.ro_number == user.branch_code)

def apply_date_filter(query, start_date: Optional[Union[date, datetime]] = None, end_date: Optional[Union[date, datetime]] = None):
    """Applies date range filters to the query."""
    if start_date:
        # If it's a date object, convert to datetime at start of day
        dt_start = datetime.combine(start_date, datetime.min.time()) if isinstance(start_date, date) and not isinstance(start_date, datetime) else start_date
        query = query.where(Feedback.created_at >= dt_start)
    if end_date:
        # If it's a date object, convert to datetime at end of day
        dt_end = datetime.combine(end_date, datetime.max.time()) if isinstance(end_date, date) and not isinstance(end_date, datetime) else end_date
        query = query.where(Feedback.created_at <= dt_end)
    return query

def apply_common_filters(query, user: AdminUser, ro_code: Optional[str] = None, status: Optional[str] = None, start_date: Optional[date] = None, end_date: Optional[date] = None):
    """Applies RBAC, ro_code, status, and date filters."""
    query = apply_rbac(query, user)
    
    if ro_code:
        query = query.where(Feedback.ro_number == ro_code)
    if status:
        query = query.where(Feedback.status == status)
    
    query = apply_date_filter(query, start_date, end_date)
    return query

def process_rating_distribution(results, total):
    rating_map = {1: 'Poor', 2: 'Neutral', 3: 'Good', 4: 'Good', 5: 'Good'}
    aggregated = {'Good': 0, 'Neutral': 0, 'Poor': 0}
    
    for r in results:
        rating = r[0]
        count = r[1]
        label = rating_map.get(rating, str(rating))
        aggregated[label] = aggregated.get(label, 0) + count
        
    data = []
    # Ensure consistent order: Good, Neutral, Poor (matches typical pie chart needs)
    for label in ['Good', 'Neutral', 'Poor']:
        count = aggregated.get(label, 0)
        pass

    # Use items() to catch unknown labels too (like "6"?)
    for label, count in aggregated.items():
        if count > 0:
            data.append({
                "name": label,
                "count": count,
                "value": round((count / total * 100), 1) if total > 0 else 0
            })
            
    return data

def verify_feedback_access(session: Session, feedback: Feedback, user: AdminUser):
    """
    Verifies if the user has access to the specific feedback item.
    Returns True if accessible, False otherwise.
    """
    if user.role == "superuser" or user.role == "Vendor":
        return True
    elif user.role == "DO":
        # Check if feedback belongs to DO's city
        stmt = select(AdminUser).where(AdminUser.branch_code == feedback.ro_number, AdminUser.role == "RO")
        ro_user = session.exec(stmt).first()
        if ro_user and ro_user.city == user.city:
            return True
    elif user.role == "RO":
        if feedback.ro_number == user.branch_code:
             return True
    elif user.role == "FO":
        # Check mapping
        mapping = session.exec(select(FOMapping).where(FOMapping.fo_username == user.username, FOMapping.ro_code == feedback.ro_number)).first()
        if mapping:
            return True
    return False

# --- Dashboard APIs ---

@router.get("/dashboard", response_model=dict)
async def get_dashboard_stats(
    roCode: Optional[str] = None,
    status: Optional[str] = None,
    startDate: Optional[date] = None,
    endDate: Optional[date] = None,
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    # Optimize with aggregate query
    stmt = select(
        func.count(Feedback.id),
        func.sum(case((Feedback.status == "Verified", 1), else_=0)),
        func.sum(case((Feedback.status == "Not Verified", 1), else_=0)),
        func.sum(case((Feedback.status.in_(["Pending", "pending"]), 1), else_=0)),
        func.sum(case((Feedback.status == "Reviewed", 1), else_=0)),
    )
    
    stmt = apply_common_filters(stmt, current_user, roCode, status, startDate, endDate)

    result = session.exec(stmt).first()
    
    def safe_int(val): return int(val) if val else 0

    return {
        "success": True,
        "data": {
            "totalFeedbacks": safe_int(result[0]),
            "verifiedFeedbacks": safe_int(result[1]),
            "notVerifiedFeedbacks": safe_int(result[2]),
            "pendingFeedbacks": safe_int(result[3]),
            "reviewedFeedbacks": safe_int(result[4]),
            "lastUpdated": datetime.utcnow()
        }
    }

@router.get("/dashboard/daily-complaints", response_model=dict)
async def get_daily_complaints(
    startDate: Optional[date] = None,
    endDate: Optional[date] = None,
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    print(f"DEBUG: Daily Complaints - User: {current_user.username} ({current_user.role}), Branch: {current_user.branch_code}")
    
    start = startDate if startDate else (datetime.utcnow() - timedelta(days=30)).date()
    end = endDate if endDate else datetime.utcnow().date()

    stmt = select(
        func.date(Feedback.created_at).label("date"),
        func.count(Feedback.id).label("count")
    )
    
    stmt = apply_rbac(stmt, current_user)
    stmt = apply_date_filter(stmt, start, end)
        
    stmt = stmt.group_by(func.date(Feedback.created_at)).order_by("date")

    results = session.exec(stmt).all()
    data = [{"date": str(r.date), "count": r.count} for r in results]
    
    return {"success": True, "data": data}

@router.get("/dashboard/not-verified-distribution", response_model=dict)
async def get_not_verified_distribution(
    startDate: Optional[date] = None,
    endDate: Optional[date] = None,
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    print(f"DEBUG: Not Verified Dist - User: {current_user.username} ({current_user.role}), Branch: {current_user.branch_code}")
    
    if not startDate and not endDate:
         start = (datetime.utcnow() - timedelta(days=30)).date()
         end = datetime.utcnow().date()
    else:
         start = startDate
         end = endDate

    stmt = select(
        func.date(Feedback.created_at).label("date"),
        func.count(Feedback.id).label("count")
    )
    
    stmt = apply_rbac(stmt, current_user)
    stmt = stmt.where(Feedback.status == "Not Verified")
    stmt = apply_date_filter(stmt, start, end)

    stmt = stmt.group_by(func.date(Feedback.created_at)).order_by("date")

    results = session.exec(stmt).all()
    data = [{"date": str(r.date), "count": r.count} for r in results]
    return {"success": True, "data": data}

@router.get("/dashboard/washroom-feedback", response_model=dict)
async def get_washroom_feedback(
    startDate: Optional[date] = None,
    endDate: Optional[date] = None,
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    print(f"DEBUG: Washroom Feedback - User: {current_user.username} ({current_user.role}), Branch: {current_user.branch_code}")
    stmt = select(Feedback.rating_washroom, func.count(Feedback.id))
    
    stmt = apply_rbac(stmt, current_user)
    stmt = apply_date_filter(stmt, startDate, endDate)
        
    stmt = stmt.where(
        Feedback.rating_washroom != None
    ).group_by(Feedback.rating_washroom).order_by(Feedback.rating_washroom)
    
    results = session.exec(stmt).all()
    total = sum(r[1] for r in results)
    
    data = process_rating_distribution(results, total)
        
    return {"success": True, "data": data, "total": total}

@router.get("/dashboard/free-air-feedback", response_model=dict)
async def get_free_air_feedback(
    startDate: Optional[date] = None,
    endDate: Optional[date] = None,
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    print(f"DEBUG: Free Air Feedback - User: {current_user.username} ({current_user.role}), Branch: {current_user.branch_code}")
    stmt = select(Feedback.rating_air, func.count(Feedback.id))
    
    stmt = apply_rbac(stmt, current_user)
    stmt = apply_date_filter(stmt, startDate, endDate)

    stmt = stmt.where(
        Feedback.rating_air != None
    ).group_by(Feedback.rating_air).order_by(Feedback.rating_air)
    
    results = session.exec(stmt).all()
    total = sum(r[1] for r in results)
    
    data = process_rating_distribution(results, total)

    return {"success": True, "data": data, "total": total}

@router.get("/dashboard/drinking-water-feedback", response_model=dict)
async def get_drinking_water_feedback(
    startDate: Optional[date] = None,
    endDate: Optional[date] = None,
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    print(f"DEBUG: Drinking Water Feedback - User: {current_user.username} ({current_user.role}), Branch: {current_user.branch_code}")
    stmt = select(Feedback.rating_water, func.count(Feedback.id))
    
    stmt = apply_rbac(stmt, current_user)
    stmt = apply_date_filter(stmt, startDate, endDate)

    stmt = stmt.where(
        Feedback.rating_water != None
    ).group_by(Feedback.rating_water).order_by(Feedback.rating_water)
    
    results = session.exec(stmt).all()
    total = sum(r[1] for r in results)
    
    data = process_rating_distribution(results, total)

    return {"success": True, "data": data, "total": total}

# --- Feedback Management APIs ---

@router.get("/feedbacks", response_model=dict)
async def get_feedbacks(
    page: int = 1,
    limit: int = 10,
    sortBy: str = "created_at",
    sortOrder: str = "desc",
    search: Optional[str] = None,
    roCode: Optional[str] = None,
    status: Optional[str] = None,
    startDate: Optional[str] = None, # String for broader acceptance
    endDate: Optional[str] = None,
    freeAirRating: Optional[int] = None,
    washroomRating: Optional[int] = None,
    hasReceipt: Optional[bool] = None,
    hasImages: Optional[bool] = None,
    useAsTestimonial: Optional[bool] = None,
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    query = select(Feedback)
    
    dt_start = None
    dt_end = None
    
    if startDate:
        dt_start = datetime.fromisoformat(startDate.replace('Z', '')) if 'T' in startDate else datetime.strptime(startDate, "%Y-%m-%d")
    
    if endDate:
        dt_end = datetime.fromisoformat(endDate.replace('Z', '')) if 'T' in endDate else datetime.strptime(endDate, "%Y-%m-%d")
        if 'T' not in endDate:
             dt_end = dt_end + timedelta(days=1) - timedelta(seconds=1)

    query = apply_common_filters(query, current_user, roCode, status, dt_start, dt_end)
    
    if freeAirRating:
        query = query.where(Feedback.rating_air == freeAirRating)
    if washroomRating:
        query = query.where(Feedback.rating_washroom == washroomRating)
    if useAsTestimonial is not None:
        query = query.where(Feedback.is_testimonial == useAsTestimonial)
    
    if search:
        query = query.where(
            (Feedback.phone.contains(search)) | 
            (Feedback.comment.contains(search))
        )
        
    if hasReceipt:
        query = query.where(Feedback.photo_receipt != None)
    elif hasReceipt is False:
        query = query.where(Feedback.photo_receipt == None)

    if hasImages:
        query = query.where((Feedback.photo_air != None) | (Feedback.photo_washroom != None))
    elif hasImages is False:
        query = query.where((Feedback.photo_air == None) & (Feedback.photo_washroom == None))
        
    count_stmt = select(func.count()).select_from(query.subquery())
    total = session.exec(count_stmt).one()

    if hasattr(Feedback, sortBy):
        col_attr = getattr(Feedback, sortBy)
        if sortOrder == 'desc':
            query = query.order_by(col_attr.desc())
        else:
            query = query.order_by(col_attr.asc())
    else:
        query = query.order_by(Feedback.created_at.desc())
        
    query = query.offset((page - 1) * limit).limit(limit)
    
    feedbacks = session.exec(query).all()
    
    feedback_dtos = []
    for f in feedbacks:
        dto = {
            "id": f.id,
            "createdAt": f.created_at,
            "phoneNumber": f.phone,
            "useAsTestimonial": f.is_testimonial,
            "acceptTermsAndConditions": f.terms_accepted,
            "freeAirFacilityRating": f.rating_air,
            "drinkingWaterRating": f.rating_water,
            "washroomCleanlinessRating": f.rating_washroom,
            "experienceComments": f.comment,
            "status": f.status,
            "reviewed": f.reviewed,
            "reviewedAt": f.reviewed_at,
            "reviewedBy": f.reviewed_by,
            "roCode": f.ro_number,
            "freeAirFacilityImage": f.id if f.photo_air else None,
            "drinkingWaterImage": f.id if f.photo_water else None,
            "washroomCleanlinessImage": f.id if f.photo_washroom else None,
            "fuelTransactionReceipt": f.id if f.photo_receipt else None,
            "workflowStatus": f.workflow_status,
            "assignedFoId": f.assigned_fo_id,
        }
        feedback_dtos.append(dto)

    return {
        "success": True,
        "data": feedback_dtos,
        "pagination": {
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": (total + limit - 1) // limit
        }
    }

@router.get("/feedbacks/{id}", response_model=dict)
async def get_feedback_detail(
    id: int,
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    feedback = session.get(Feedback, id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
        
    if not verify_feedback_access(session, feedback, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to access this feedback")

    return {
        "success": True,
        "data": feedback 
    }

@router.patch("/feedbacks/{id}/review", response_model=dict)
async def review_feedback(
    id: int,
    payload: dict, # {status: str, reviewedAt: str}
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    feedback = session.get(Feedback, id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
        
    if not verify_feedback_access(session, feedback, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to review this feedback")

    old_status = feedback.status
    
    feedback.status = payload.get("status", "Reviewed")
    feedback.reviewed = True
    feedback.reviewed_by = current_user.id
    feedback.reviewed_by_id = current_user.id
    feedback.reviewed_at = datetime.utcnow()
    
    session.add(feedback)
    session.commit()
    session.refresh(feedback)
    
    history = ReviewHistory(
        feedback_id=feedback.id,
        reviewed_by=current_user.id,
        old_status=old_status,
        new_status=feedback.status,
        reviewed_at=datetime.utcnow()
    )
    import uuid
    history.id = str(uuid.uuid4())
    session.add(history)
    session.commit()
    
    return {
        "success": True,
        "message": "Feedback reviewed successfully",
        "data": {
            "id": feedback.id,
            "status": feedback.status,
            "reviewedBy": current_user.username,
            "reviewedAt": feedback.reviewed_at
        }
    }

@router.patch("/feedbacks/{id}/workflow", response_model=dict)
async def update_workflow_status(
    id: int,
    payload: WorkflowUpdate,
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    feedback = session.get(Feedback, id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    new_status = payload.status
    old_status = feedback.workflow_status
    
    # Global Reject Handler
    if new_status == "Rejected":
         if current_user.role in ["Vendor", "superuser", "DO"]:
              feedback.workflow_status = "Rejected"
              feedback.status = "Rejected"
              session.add(feedback)
              session.commit()
              session.refresh(feedback)
              return {"success": True, "message": "Feedback Rejected"}
         else:
              raise HTTPException(status_code=403, detail="Only Vendor or DO can reject feedback.")

    # --- New Workflow: Vendor -> DO -> FO -> DO ---
    
    # 1. Vendor Step
    if current_user.role == "Vendor" or current_user.role == "superuser":
        # Vendor moves Pending -> Vendor Verified
        if new_status == "Vendor Verified":
            feedback.workflow_status = "Vendor Verified"
            feedback.status = "Reviewed" 
        else:
            # Allow superuser to force other states if needed, but stricter for Vendor
            feedback.workflow_status = new_status
            if payload.assignedTo:
                feedback.assigned_fo_id = payload.assignedTo

    # 2. DO Step (Two Interaction Points)
    elif current_user.role == "DO":
        # Interaction A: Vendor Verified -> Assigned (Assign to FO)
        if new_status == "Assigned":
             if old_status != "Vendor Verified":
                 raise HTTPException(status_code=400, detail="DO can only assign feedback after Vendor verification.")
             
             # Auto-Assignment Logic
             # Find FO mapped to this RO using the new UserROMapping table
             stmt = select(AdminUser.id).join(UserROMapping, UserROMapping.username == AdminUser.username).where(
                 UserROMapping.ro_code == feedback.ro_number,
                 UserROMapping.role == "FO"
             )
             fo_id = session.exec(stmt).first()
             
             if fo_id:
                 feedback.workflow_status = "Assigned"
                 feedback.assigned_fo_id = fo_id
                 feedback.status = "Verified"
             else:
                 # Fallback if no FO is mapped
                 logger.warning(f"No FO mapped for RO {feedback.ro_number}. Updating to DO Verified instead.")
                 feedback.workflow_status = "DO Verified" # Intermediate state if no FO? Or keep as Vendor Verified? 
                 # Let's fail or allow manual assignment? 
                 # For now, let's allow it but warn.
                 # Actually, expectation is "Assigned to respective FO". 
                 if payload.assignedTo: # Allow manual override
                     feedback.assigned_fo_id = payload.assignedTo
                     feedback.workflow_status = "Assigned"
                 else:
                     raise HTTPException(status_code=400, detail=f"No Field Officer found mapped to RO {feedback.ro_number}. Please check mappings.")

        # Interaction B: Action Taken -> Resolved (Final Closure)
        elif new_status == "Resolved":
             if old_status != "Action Taken": # Should strictly follow FO action
                  # Maybe allow bypassing FO if needed? "Action Taken" or "Assigned" (if FO did it offline)
                  pass 
             
             feedback.workflow_status = "Resolved"
             feedback.status = "Resolved"
        
        else:
             raise HTTPException(status_code=400, detail="Invalid transition for DO. Valid: Assign (from Vendor Verified) or Resolve (from Action Taken).")

    # 3. FO Step
    elif current_user.role == "FO":
        if feedback.assigned_fo_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not assigned to this task")
            
        if new_status == "Action Taken":
            feedback.workflow_status = "Action Taken"
            # Keep overall status as Verified or Change to In Progress?
            # Let's keep as Verified.
        else:
             raise HTTPException(status_code=400, detail="Invalid transition for FO. Can only mark as 'Action Taken'.")
             
    else:
        # RO or others?
        raise HTTPException(status_code=403, detail="Unauthorized role for this workflow.")

    session.add(feedback)
    session.commit()
    session.refresh(feedback)
    
    return {"success": True, "message": f"Status updated to {feedback.workflow_status}"}

@router.get("/users/fo", response_model=dict)
async def get_field_officers(
    branchCode: str,
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    stmt = select(AdminUser).where(AdminUser.role == "FO")
    # Find FOs mapped to this branchCode
    sub = select(FOMapping.fo_username).where(FOMapping.ro_code == branchCode)
    stmt = stmt.where(AdminUser.username.in_(sub))
    fos = session.exec(stmt).all()
    
    data = [{"id": u.id, "username": u.username, "fullName": u.full_name} for u in fos]
    return {"success": True, "data": data}

@router.get("/filters/options", response_model=dict)
async def get_filter_options(
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    query = select(Branch)
    
    if current_user.role == "DO":
        if current_user.city:
            query = query.where(Branch.city == current_user.city)
        else:
            query = query.where(Branch.city == "NON_EXISTENT_CITY")
            
    elif current_user.role == "RO":
        query = query.where(Branch.ro_code == current_user.branch_code)
        
    elif current_user.role == "FO":
        # FO Manages multiple ROs via FOMapping
        sub = select(FOMapping.ro_code).where(FOMapping.fo_username == current_user.username)
        query = query.where(Branch.ro_code.in_(sub))
        
    results = session.exec(query).all()
    statuses = ["Pending", "Vendor Verified", "Assigned", "Action Taken", "Resolved", "Rejected"]
    
    ro_options = []
    for branch in results:
        code = branch.ro_code
        name = branch.name
        if code:
            label = f"{code} - {name}" if name else code
            ro_options.append({"label": label, "value": code})
            
    ro_options.sort(key=lambda x: x['label'])

    return {
        "success": True,
        "data": {
            "roCodes": ro_options,
            "statuses": [{"label": s, "value": s} for s in statuses]
        }
    }

from fastapi.responses import StreamingResponse

@router.get("/feedbacks/export/csv")
async def export_csv(
    roCode: Optional[str] = None,
    status: Optional[str] = None,
    startDate: Optional[str] = None,
    endDate: Optional[str] = None,
    timezone_offset: int = 0, # Offset in minutes (e.g., -330 for IST +5:30) - Client should send negated offset from JS usually 
    # Or simplified: User sends expected offset to ADD to UTC.
    # Let's assume user sends "minutes to add to UTC". IST = 330.
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    query = select(Feedback)
    
    dt_start = None
    dt_end = None
    # Fix robust date parsing
    try:
        if startDate:
            # Handle YYYY-MM-DD or ISO
            clean_date = startDate.split('T')[0]
            dt_start = datetime.strptime(clean_date, "%Y-%m-%d")
        
        if endDate:
            clean_date = endDate.split('T')[0]
            dt_end = datetime.strptime(clean_date, "%Y-%m-%d")
            # Set to end of day
            dt_end = dt_end.replace(hour=23, minute=59, second=59)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    query = apply_common_filters(query, current_user, roCode, status, dt_start, dt_end)
        
    query = query.order_by(Feedback.created_at.desc())
    feedbacks = session.exec(query).all()
    
    def adjust_time(dt_utc):
        if not dt_utc: return ""
        # Adjust UTC to Target Timezone
        # timezone_offset is in minutes to ADD
        # e.g. IST is +5:30 -> +330 minutes
        adjusted = dt_utc + timedelta(minutes=timezone_offset)
        return adjusted.strftime('%Y-%m-%d %H:%M')

    def iter_csv(data):
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Add 'Drinking Water Rating' to header
        writer.writerow(['ID', 'Date', 'Phone Number', 'RO Code', 'Free Air Rating', 'Washroom Rating', 'Drinking Water Rating', 'Comments', 'Status', 'Reviewed By'])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        
        for f in data:
            writer.writerow([
                f.id,
                adjust_time(f.created_at), # Dynamic Time
                f.phone,
                f.ro_number or 'N/A',
                f.rating_air,
                f.rating_washroom,
                f.rating_water, # Added Water Rating
                f.comment or '',
                f.status,
                f.reviewed_by or 'N/A'
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    filename_date = datetime.now().strftime('%Y%m%d%H%M%S')
    response = StreamingResponse(iter_csv(feedbacks), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=feedbacks_{filename_date}.csv"
    return response
