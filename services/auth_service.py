from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from core.config import settings
from core.database import get_session
from core.security import verify_password, get_password_hash, create_access_token, decode_token
from models import AdminUser

# JWT handling
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

# Dependency
async def get_current_admin(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)) -> AdminUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
        
    admin_user = session.query(AdminUser).filter(AdminUser.username == username).first()
    if admin_user is None:
        raise credentials_exception
    
    if not admin_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    return admin_user
