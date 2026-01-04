from typing import Optional
from sqlmodel import Field, SQLModel

class Branch(SQLModel, table=True):
    ro_code: str = Field(primary_key=True)
    name: str 
    city: str = Field(index=True)
    
    # Hierarchy caching (simplifies queries)
    do_email: Optional[str] = None
    fo_username: Optional[str] = None
    
    # Metadata
    region: Optional[str] = None
    sales_area: Optional[str] = None
