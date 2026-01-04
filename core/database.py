from sqlmodel import SQLModel, create_engine, Session
from .config import settings

connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args["check_same_thread"] = False

# Fix for some platforms (like Render/Neon) using postgres:// which SQLAlchemy doesn't like
database_url = settings.DATABASE_URL
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True, pool_recycle=300)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
