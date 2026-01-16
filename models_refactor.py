from typing import Optional
from sqlmodel import Field, SQLModel


class Branch(SQLModel, table=True):
    """
    Branch model representing RO (Retail Outlet) locations.
    This table stores information about each branch/RO in the system.
    """
    __tablename__ = "branch"
    
    ro_code: str = Field(primary_key=True, index=True)
    name: str
    city: str
    region: Optional[str] = None
    do_email: Optional[str] = None
    fo_username: Optional[str] = None
