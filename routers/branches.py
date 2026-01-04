from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel

from core.database import get_session
from models_refactor import Branch
from models import AdminUser
from services.auth_service import get_current_admin

router = APIRouter(prefix="/api/branches", tags=["branches"])

# --- Schemas ---
class BranchCreate(BaseModel):
    ro_code: str
    name: str
    city: str
    region: Optional[str] = None
    
class BranchResponse(BaseModel):
    ro_code: str
    name: str
    city: str
    region: Optional[str] = None

def get_superuser(current_user: AdminUser = Depends(get_current_admin)):
    if current_user.role != "superuser":
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user

@router.get("/", response_model=dict)
async def list_branches(
    session: Session = Depends(get_session),
    current_user: AdminUser = Depends(get_current_admin)
):
    branches = session.exec(select(Branch)).all()
    return {"success": True, "data": branches}

@router.post("/", response_model=dict)
async def create_branch(
    branch_in: BranchCreate,
    session: Session = Depends(get_session),
    superuser: AdminUser = Depends(get_superuser)
):
    existing = session.get(Branch, branch_in.ro_code)
    if existing:
        raise HTTPException(status_code=400, detail="Branch code already exists")
        
    branch = Branch(**branch_in.model_dump())
    session.add(branch)
    session.commit()
    session.refresh(branch)
    
    return {"success": True, "message": "Branch created successfully", "data": branch}

@router.delete("/{ro_code}", response_model=dict)
async def delete_branch(
    ro_code: str,
    session: Session = Depends(get_session),
    superuser: AdminUser = Depends(get_superuser)
):
    branch = session.get(Branch, ro_code)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
        
    session.delete(branch)
    session.commit()
    
    return {"success": True, "message": "Branch deleted successfully"}
