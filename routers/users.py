from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
import uuid

from core.database import get_session
from models import AdminUser, FOMapping, UserROMapping
from models_refactor import Branch
from services.auth_service import get_current_admin
from services.user_onboarding import process_ro_excel_upload
from core.security import get_password_hash

router = APIRouter(prefix="/api/users", tags=["users"])

# --- schemas ---

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    fullName: str
    branchCode: str
    branchName: str
    city: Optional[str] = None
    role: str = "RO" # RO, DO, FO, superuser

class UserUpdate(BaseModel):
    email: Optional[str] = None
    fullName: Optional[str] = None
    branchCode: Optional[str] = None
    branchName: Optional[str] = None
    city: Optional[str] = None
    role: Optional[str] = None

class PasswordReset(BaseModel):
    newPassword: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    fullName: Optional[str] = None
    branchCode: str
    branchName: Optional[str] = None
    city: Optional[str] = None
    role: str
    isActive: bool

# --- dependencies ---

def get_superuser(current_user: AdminUser = Depends(get_current_admin)):
    if current_user.role != "superuser":
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user

# --- endpoints ---

@router.post("/upload_ro_list")
async def upload_ro_list(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_superuser)
):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload Excel.")
    
    contents = await file.read()
    result = process_ro_excel_upload(contents, session)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
        
    return result

@router.get("/hierarchy", response_model=dict)
async def get_user_hierarchy(
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_superuser)
):
    # Fetch all mappings and branches
    mappings = session.exec(select(UserROMapping)).all()
    branches = session.exec(select(Branch)).all()
    
    # Map RO Code -> Branch Data
    branch_map = {b.ro_code: b for b in branches}
    
    # Organize Mappings by RO Code: ro_code -> {role: username}
    ro_map = {}
    for m in mappings:
        if m.ro_code not in ro_map: ro_map[m.ro_code] = {}
        ro_map[m.ro_code][m.role] = m.username

    # Helper to find children
    def build_level(parent_users, child_role, ro_subset):
        nodes = []
        # Find all unique users of child_role within this ro_subset
        child_usernames = set()
        for ro in ro_subset:
            if ro in ro_map and child_role in ro_map[ro]:
                child_usernames.add(ro_map[ro][child_role])
        
        for username in sorted(child_usernames):
            # Find ROs for this specific child user
            child_ros = [ro for ro in ro_subset if ro in ro_map and ro_map[ro].get(child_role) == username]
            
            node = {
                "name": username,
                "type": child_role,
                "children": []
            }
            
            # Recurse or add ROs
            if child_role == "SRH":
                node["children"] = build_level([username], "DRSM", child_ros)
            elif child_role == "DRSM":
                node["children"] = build_level([username], "DO", child_ros)
            elif child_role == "DO":
                node["children"] = build_level([username], "FO", child_ros)
            elif child_role == "FO":
                # Leaves are ROs
                for ro in child_ros:
                    b_data = branch_map.get(ro)
                    node["children"].append({
                        "name": b_data.name if b_data else ro,
                        "type": "RO",
                        "ro_code": ro,
                        "children": []
                    })
            nodes.append(node)
        return nodes

    # Start from Roots (SRH)
    # Get all ROs
    all_ros = list(branch_map.keys())
    
    # If no mappings, fallback ??
    if not mappings:
        return {"success": True, "data": []}

    srh_nodes = build_level([], "SRH", all_ros)
    
    # Handle orphans (ROs with no SRH)?
    # For now, simplistic tree based on SRH -> DRSM -> DO -> FO
    
    return {"success": True, "data": srh_nodes}

@router.get("/", response_model=dict)
async def list_users(
    session: Session = Depends(get_session),
    superuser: AdminUser = Depends(get_superuser)
):
    users = session.exec(select(AdminUser)).all()
    
    # Map to response format
    data = []
    for u in users:
        data.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "fullName": u.full_name,
            "branchCode": u.branch_code if u.branch_code else "", # Handle None for Vendor
            "branchName": u.branch_name if u.branch_name else "",
            "city": u.city,
            "role": u.role,
            "isActive": u.is_active
        })
        
    return {"success": True, "data": data}

@router.post("/", response_model=dict)
async def create_user(
    user_in: UserCreate,
    session: Session = Depends(get_session),
    superuser: AdminUser = Depends(get_superuser)
):
    # Check if username exists
    existing = session.exec(select(AdminUser).where(AdminUser.username == user_in.username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    existing_email = session.exec(select(AdminUser).where(AdminUser.email == user_in.email)).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")

    # Validate Branch Code exists (Skip for Vendor)
    branch_obj = None
    if user_in.role != "Vendor":
        branch_obj = session.get(Branch, user_in.branchCode)
        if not branch_obj:
            raise HTTPException(status_code=400, detail=f"Invalid Branch Code: {user_in.branchCode}")

    # Enforce Singleton Vendor
    if user_in.role == "Vendor":
        existing_vendor = session.exec(select(AdminUser).where(AdminUser.role == "Vendor")).first()
        if existing_vendor:
            raise HTTPException(status_code=400, detail="A Vendor account already exists. Only one Vendor is allowed.")

    # Enforce One RO per Branch
    if user_in.role == "RO":
        existing_branch_admin = session.exec(select(AdminUser).where(
            AdminUser.branch_code == user_in.branchCode,
            AdminUser.role == "RO"
        )).first()
        if existing_branch_admin:
            raise HTTPException(status_code=400, detail=f"An RO already exists for branch {user_in.branchCode}. Every branch should have one RO only.")

    # Enforce One FO per Branch
    if user_in.role == "FO":
        existing_fo = session.exec(select(AdminUser).where(
            AdminUser.branch_code == user_in.branchCode,
            AdminUser.role == "FO"
        )).first()
        if existing_fo:
            raise HTTPException(status_code=400, detail=f"An FO already exists for branch {user_in.branchCode}. Every branch should have one FO only.")

    new_user = AdminUser(
        id=str(uuid.uuid4()),
        username=user_in.username,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        full_name=user_in.fullName,
        branch_code=branch_obj.ro_code if branch_obj else "GLOBAL", # Vendor gets GLOBAL
        branch_name=branch_obj.name if branch_obj else "Global Vendor",
        city=branch_obj.city if branch_obj else None,
        role=user_in.role,
        is_active=True
    )
    
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    return {"success": True, "message": "User created successfully", "data": {"id": new_user.id}}

@router.put("/{id}", response_model=dict)
async def update_user(
    id: str,
    user_in: UserUpdate,
    session: Session = Depends(get_session),
    superuser: AdminUser = Depends(get_superuser)
):
    user = session.get(AdminUser, id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    target_role = user_in.role if user_in.role else user.role
    target_branch_code = user_in.branchCode if user_in.branchCode else user.branch_code
    
    if user_in.branchCode:
         # Validate branch if not making it a Vendor (or if Vendor wants to be demoted? - edge case, assume no)
         # If Role is Vendor, ignore branch update or set to Global? 
         # Simplification: If Updating TO Vendor, verify singleton.
         
         branch_obj = session.get(Branch, user_in.branchCode)
         if not branch_obj and target_role != "Vendor":
             raise HTTPException(status_code=400, detail=f"Invalid Branch Code: {user_in.branchCode}")
         
         if branch_obj:
            # Auto update name/city if branch changes
            user.branch_name = branch_obj.name
            user.city = branch_obj.city
    
    if user_in.role == "Vendor" and user.role != "Vendor":
         existing_vendor = session.exec(select(AdminUser).where(AdminUser.role == "Vendor")).first()
         if existing_vendor:
            raise HTTPException(status_code=400, detail="A Vendor account already exists.")
         user.branch_code = "GLOBAL"
         user.branch_name = "Global Vendor"
         user.city = None
    
    if target_role == "RO":
        existing = session.exec(select(AdminUser).where(
            AdminUser.branch_code == target_branch,
            AdminUser.role == "RO",
            AdminUser.id != id
        )).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"An RO already exists for branch {target_branch}.")

    if target_role == "FO":
        existing = session.exec(select(AdminUser).where(
            AdminUser.branch_code == target_branch,
            AdminUser.role == "FO",
            AdminUser.id != id
        )).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"An FO already exists for branch {target_branch}.")

    if user_in.email:
        user.email = user_in.email
    if user_in.fullName:
        user.full_name = user_in.fullName
    if user_in.branchCode:
        user.branch_code = user_in.branchCode
    if user_in.branchName:
        user.branch_name = user_in.branchName
    if user_in.city:
        user.city = user_in.city
    if user_in.role:
        user.role = user_in.role
        
    session.add(user)
    session.commit()
    
    return {"success": True, "message": "User updated successfully"}

@router.post("/{id}/reset-password", response_model=dict)
async def reset_password(
    id: str,
    payload: PasswordReset,
    session: Session = Depends(get_session),
    superuser: AdminUser = Depends(get_superuser)
):
    user = session.get(AdminUser, id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.password_hash = get_password_hash(payload.newPassword)
    session.add(user)
    session.commit()
    
    return {"success": True, "message": "Password reset successfully"}

@router.delete("/{id}", response_model=dict)
async def delete_user(
    id: str,
    session: Session = Depends(get_session),
    superuser: AdminUser = Depends(get_superuser)
):
    user = session.get(AdminUser, id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == superuser.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
        
    session.delete(user)
    session.commit()
    
    return {"success": True, "message": "User deleted successfully"}
