from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from typing import Any

from core.database import get_session
from models import AdminUser
from services.auth_service import get_current_admin
from core.config import settings
from core.security import verify_password, create_access_token, get_password_hash
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginResponse(BaseModel):
    success: bool
    token: str
    user: Any

class UserProfile(BaseModel):
    id: str
    username: str
    email: str
    fullName: str
    branch: str
    branchName: str | None
    role: str


# Let's create a JSON-friendly login endpoint
class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login-json", response_model=LoginResponse)
@router.post("/login", response_model=LoginResponse)
async def login_json(
    login_data: LoginRequest,
    session: Session = Depends(get_session)
):
    user = session.exec(select(AdminUser).where(AdminUser.username == login_data.username)).first()
    
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Update last login
    user.last_login = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 24) # e.g. 1 day usually for admin
    access_token = create_access_token(
        data={"sub": user.username, "branch": user.branch_code, "role": user.role},
        expires_delta=access_token_expires
    )
    
    return {
        "success": True,
        "token": access_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "fullName": user.full_name,
            "branch": user.branch_code,
            "branchName": user.branch_name,
            "role": user.role
        }
    }

@router.post("/refresh")
async def refresh_token(current_user: AdminUser = Depends(get_current_admin)):
    access_token = create_access_token(
        data={"sub": current_user.username, "branch": current_user.branch_code, "role": current_user.role}
    )
    return {"token": access_token}

@router.get("/profile", response_model=UserProfile)
async def get_profile(current_user: AdminUser = Depends(get_current_admin)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "fullName": current_user.full_name,
        "branch": current_user.branch_code,
        "branchName": current_user.branch_name,
        "role": current_user.role
    }

class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str

@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    if not verify_password(payload.currentPassword, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    
    current_user.password_hash = get_password_hash(payload.newPassword)
    session.add(current_user)
    session.commit()
    
    return {"success": True, "message": "Password changed successfully"}
