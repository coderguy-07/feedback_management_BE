import sys
import os
import uuid
import argparse
import getpass

# Adjust path to import from backend
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from sqlmodel import Session, select
from backend.models import AdminUser
from backend.core.database import engine
from backend.core.security import get_password_hash

def add_user(username, email, password, full_name, role, branch_code, branch_name):
    with Session(engine) as session:
        # Check if user exists
        existing_user = session.exec(select(AdminUser).where(AdminUser.username == username)).first()
        if existing_user:
            print(f"Error: User '{username}' already exists.")
            return

        new_user = AdminUser(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            password_hash=get_password_hash(password),
            full_name=full_name,
            branch_code=branch_code,
            branch_name=branch_name,
            role=role,
            is_active=True
        )
        session.add(new_user)
        session.commit()
        print(f"Successfully created user: {username} ({role})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a new user to the Survey System")
    parser.add_argument("--username", help="Username")
    parser.add_argument("--email", help="Email", default="")
    parser.add_argument("--password", help="Password")
    parser.add_argument("--fullname", help="Full Name", default="New User")
    parser.add_argument("--role", help="Role (admin/user)", default="user")
    parser.add_argument("--branch-code", help="Branch Code", default="BR001")
    parser.add_argument("--branch-name", help="Branch Name", default="Main Branch")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")

    args = parser.parse_args()

    if args.interactive:
        print("--- Add New User ---")
        username = input("Username: ")
        email = input("Email: ")
        password = getpass.getpass("Password: ")
        full_name = input("Full Name: ")
        role = input("Role (admin/user): ")
        branch_code = input("Branch Code [BR001]: ") or "BR001"
        branch_name = input("Branch Name [Main Branch]: ") or "Main Branch"
        
        add_user(username, email, password, full_name, role, branch_code, branch_name)
    
    elif args.username and args.password:
        add_user(args.username, args.email, args.password, args.fullname, args.role, args.branch_code, args.branch_name)
    else:
        print("Error: Please provide --username and --password, or use --interactive")
        parser.print_help()
