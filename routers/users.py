from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
import uuid

from core.database import get_session
from models import AdminUser, FOMapping
from models_refactor import Branch
from services.auth_service import get_current_admin
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

@router.get("/hierarchy", response_model=dict)
async def get_user_hierarchy(
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_superuser)
):
    # Fetch all branches, FOs, and DOs
    branches = session.exec(select(Branch)).all()
    # FOs are mapped via FOMapping
    fo_mappings = session.exec(select(FOMapping)).all()
    
    # Structure: City -> FO -> ROs
    hierarchy = {}

    # 1. Group by City (DO Level)
    for branch in branches:
        city = branch.city
        if city not in hierarchy:
            hierarchy[city] = {"city": city, "fos": {}, "unassigned_ros": []}
            
        # 2. Find FO for this branch
        fo_map = next((m for m in fo_mappings if m.ro_code == branch.ro_code), None)
        
        if fo_map:
            fo_name = fo_map.fo_username
            if fo_name not in hierarchy[city]["fos"]:
                 hierarchy[city]["fos"][fo_name] = []
            hierarchy[city]["fos"][fo_name].append({
                "ro_code": branch.ro_code,
                "name": branch.name,
                "region": branch.region
            })
        else:
            hierarchy[city]["unassigned_ros"].append({
                "ro_code": branch.ro_code,
                "name": branch.name,
                "region": branch.region
            })
            
    # Convert to list for frontend
    result = []
    for city, data in hierarchy.items():
        city_node = {
            "name": city,
            "type": "DO",
            "children": []
        }
        
        # Add FOs
        for fo_name, ros in data["fos"].items():
            fo_node = {
                "name": fo_name,
                "type": "FO",
                "children": ros  # Leaves are ROs
            }
            city_node["children"].append(fo_node)
            
        # Add Unassigned ROs (Directly under DO/City?)
        if data["unassigned_ros"]:
             unassigned_node = {
                 "name": "Unassigned Branches",
                 "type": "FO_Placeholder",
                 "children": data["unassigned_ros"]
             }
             city_node["children"].append(unassigned_node)
        
        result.append(city_node)

    return {"success": True, "data": result}

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
            "branchCode": u.branch_code,
            "branchName": u.branch_name,
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

    # Validate Branch Code exists
    branch_obj = session.get(Branch, user_in.branchCode)
    if not branch_obj:
        raise HTTPException(status_code=400, detail=f"Invalid Branch Code: {user_in.branchCode}")

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
        branch_code=branch_obj.ro_code,
        branch_name=branch_obj.name, # Auto-fill from Branch table
        city=branch_obj.city,        # Auto-fill from Branch table
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
         branch_obj = session.get(Branch, user_in.branchCode)
         if not branch_obj:
             raise HTTPException(status_code=400, detail=f"Invalid Branch Code: {user_in.branchCode}")
         # Auto update name/city if branch changes
         user.branch_name = branch_obj.name
         user.city = branch_obj.city
    
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
