import sys
import os

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from core.database import engine
from models import AdminUser

def main():
    with Session(engine) as session:
        statement = select(AdminUser)
        users = session.exec(statement).all()
        print(f"{'Username':<20} {'Password Hash (Prefix)':<30}")
        print("-" * 50)
        for user in users:
            hash_prefix = user.password_hash[:15] + "..." if user.password_hash else "None"
            print(f"{user.username:<20} {hash_prefix:<30}")

if __name__ == "__main__":
    main()
