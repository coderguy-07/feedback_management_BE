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
        print(f"{'Username':<15} {'Role':<10} {'Branch':<10} {'City':<15} {'Name':<20} {'Email':<30} {'Active'}")
        print("-" * 110)
        for user in users:
            print(f"{user.username:<15} {user.role:<10} {user.branch_code:<10} {str(user.city):<15} {str(user.full_name):<20} {user.email:<30} {user.is_active}")

if __name__ == "__main__":
    main()
