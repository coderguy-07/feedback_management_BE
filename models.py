from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel

class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    phone: str
    is_testimonial: bool = False
    rating_air: Optional[int] = None
    rating_washroom: Optional[int] = None
    rating_water: Optional[int] = None
    comment: Optional[str] = None
    photo_air: Optional[bytes] = None
    photo_washroom: Optional[bytes] = None
    photo_water: Optional[bytes] = None
    photo_receipt: Optional[bytes] = None
    terms_accepted: bool = False
    ro_number: Optional[str] = None
    feedback_method: str = Field(default="web") # web or whatsapp
    session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Review fields
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None # Admin username
    reviewed_by_id: Optional[str] = None # Admin ID (if applicable)
    
    # Status field - supports 'Pending', 'Verified', 'Rejected'
    status: str = Field(default="Pending", index=True)
    
    # Workflow fields
    workflow_status: str = Field(default="Pending", index=True) # Pending -> Escalated -> Assigned -> Resolved -> Closed
    assigned_fo_id: Optional[str] = Field(default=None, index=True)

    reviewed: bool = Field(default=False, index=True)
    branch_code: Optional[str] = Field(default=None, index=True)
    ro_code: Optional[str] = None

class AdminUser(SQLModel, table=True):
    __tablename__ = "admin_users"
    id: Optional[str] = Field(primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True)
    password_hash: str
    full_name: Optional[str] = None
    branch_code: str = Field(index=True)
    branch_name: Optional[str] = None
    city: Optional[str] = Field(default=None, index=True)
    role: str = Field(default="admin")
    is_active: bool = Field(default=True)
    last_login: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

class ReviewHistory(SQLModel, table=True):
    __tablename__ = "review_history"
    id: Optional[str] = Field(primary_key=True)
    feedback_id: int = Field(foreign_key="feedback.id")
    reviewed_by: str = Field(foreign_key="admin_users.id")
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)
    comments: Optional[str] = None

class FOMapping(SQLModel, table=True):
    __tablename__ = "fo_mapping"
    id: Optional[int] = Field(default=None, primary_key=True)
    fo_username: str = Field(index=True)
    ro_code: str = Field(index=True)
    do_email: Optional[str] = None


class WhatsAppState(SQLModel, table=True):
    phone: str = Field(primary_key=True)
    state: str = Field(default="GREETING")
    temp_data: str = Field(default="{}") # JSON string
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class FeedbackRead(SQLModel):
    id: Optional[int]
    phone: str
    is_testimonial: bool
    rating_air: Optional[int]
    rating_washroom: Optional[int]
    rating_water: Optional[int]
    comment: Optional[str]
    photo_air: Optional[str] = None
    photo_washroom: Optional[str] = None
    photo_receipt: Optional[str] = None
    terms_accepted: bool
    ro_number: Optional[str]
    status: str
    feedback_method: str
    session_id: Optional[str]
    created_at: datetime
    # Review fields
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None

class SurveyListRead(SQLModel):
    id: int
    submission_date: datetime
    mobile_number: str
    ro_code: Optional[str]
    rating_air: Optional[str] # Emoji or text
    rating_washroom: Optional[str] # Emoji or text
    has_receipt: bool
    has_image_air: bool
    has_image_washroom: bool
    comments_preview: Optional[str]
    status: str
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[str]
    
class SurveyDetailRead(SQLModel):
    id: int
    submission_date: datetime
    mobile_number: str
    ro_code: Optional[str]
    rating_air: Optional[int]
    rating_washroom: Optional[int]
    comment: Optional[str]
    status: str
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[str]
    has_receipt: bool
    has_image_air: bool
    has_image_washroom: bool
