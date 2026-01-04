import sys
import os
import uuid
# Adjust path to import from backend
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from sqlmodel import Session, select
from backend.models import Feedback, AdminUser
from backend.core.database import engine
from backend.core.security import get_password_hash

def init_admin():
    with Session(engine) as session:
        # 0. Update Schema (Add columns if they don't exist)
        # We use raw SQL for this as SQLModel create_all doesn't handle migrations
        # Note: 'feedback' table name is usually 'feedback' (default) or 'feedbacks' (if pluralized). 
        # Checking models.py: class Feedback(SQLModel, table=True). Default table name is 'feedback'.
        # User prompt said 'feedbacks'. I should check if table is 'feedback' or 'feedbacks'. 
        # Usually SQLModel uses lowercase class name 'feedback'. 
        # I'll try 'feedback' first. If user explicitly set __tablename__, I should check model.
        
        # Checking AdminUser model I added: __tablename__ = "admin_users".
        # Feedback model didn't have __tablename__ set in my view_file output earlier, so it's 'feedback'.
        
        from sqlalchemy import text
        print("Running schema updates for 'feedback' table...")
        try:
            # We wrap in try/except or use 'ADD COLUMN IF NOT EXISTS' which is Postgres specific usually.
            # SQLite doesn't support IF NOT EXISTS for columns in all versions.
            # Assuming Postgres/Neon as per README.
            
            alter_commands = [
                "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'Pending';",
                "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS reviewed BOOLEAN DEFAULT false;",
                "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP NULL;",
                "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR(50) NULL;",
                "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS reviewed_by_id VARCHAR(50) NULL;",
                "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS branch_code VARCHAR(50) NULL;",
                "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS ro_code VARCHAR(50) NULL;",
                "CREATE INDEX IF NOT EXISTS idx_status ON feedback(status);",
                "CREATE INDEX IF NOT EXISTS idx_branch ON feedback(branch_code);",
                "CREATE INDEX IF NOT EXISTS idx_reviewed ON feedback(reviewed);"
            ]
            
            for cmd in alter_commands:
                try:
                    session.exec(text(cmd))
                    session.commit()
                except Exception as e:
                    print(f"Command failed (might already exist): {cmd} -> {e}")
                    session.rollback()
                    
            # Update Tables from SQLModel metadata (creates admin_users if missing)
            from sqlmodel import SQLModel
            SQLModel.metadata.create_all(engine)
            
        except Exception as e:
            print(f"Schema update error: {e}")

        # 1. Backfill Feedbacks
        print("Backfilling Feedbacks with default branch_code...")
        feedbacks = session.exec(select(Feedback).where(Feedback.branch_code == None)).all()
        count = 0
        for f in feedbacks:
            f.branch_code = "BR001"
            if not f.status:
                f.status = "Pending"
            # Attempt to derive ro_code if ro_number exists
            if f.ro_number and not f.ro_code:
                f.ro_code = f.ro_number
            session.add(f)
            count += 1
        session.commit()
        print(f"Updated {count} feedbacks.")

        # 2. Create Default Admin
        print("Checking for existing admin user...")
        existing_admin = session.exec(select(AdminUser).where(AdminUser.username == "admin")).first()
        if not existing_admin:
            print("Creating default admin user...")
            admin = AdminUser(
                id=str(uuid.uuid4()),
                username="admin",
                email="admin@example.com",
                password_hash=get_password_hash("admin123"),
                full_name="System Admin",
                branch_code="BR001",
                branch_name="Main Branch",
                role="admin",
                is_active=True
            )
            session.add(admin)
            session.commit()
            print("Default admin created: username=admin, password=admin123")
        else:
            print("Admin user already exists.")

if __name__ == "__main__":
    init_admin()
