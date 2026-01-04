import sys
import os
from sqlmodel import Session, select, func
from sqlalchemy import text

# Add Backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import AdminUser, FOMapping
from models_refactor import Branch # New model
from core.database import engine

def check_integrity():
    with Session(engine) as session:
        print("--- Integrity Check ---")
        
        # 1. Check Branch Table
        branch_count = session.exec(select(func.count(Branch.ro_code))).one()
        print(f"Total Branches: {branch_count}")
        if branch_count < 50:
            print("WARNING: Branch count seems low (expected ~54).")
        else:
            print("Branch count valid.")
        
        # 2. Check Admin Users
        users = session.exec(select(AdminUser)).all()
        ro_users = [u for u in users if u.role == 'RO']
        fo_users = [u for u in users if u.role == 'FO']
        do_users = [u for u in users if u.role == 'DO']
        
        print(f"Total Users: {len(users)}")
        print(f"RO Users: {len(ro_users)}")
        print(f"FO Users: {len(fo_users)}")
        print(f"DO Users: {len(do_users)}")
        
        # 3. Validation: Do RO Users have valid Branch Code?
        print("\nChecking RO User Branch Assignments:")
        invalid_branches = 0
        for u in ro_users:
            if not u.branch_code:
                print(f"ERROR: User {u.username} has NO branch code")
                invalid_branches += 1
                continue
                
            branch = session.get(Branch, u.branch_code)
            if not branch:
                 print(f"ERROR: User {u.username} has invalid branch code {u.branch_code}")
                 invalid_branches += 1
            else:
                 # Check if name/city match
                 if u.branch_name != branch.name:
                     print(f"WARNING: User {u.username} branch name mismatch. User: {u.branch_name}, Branch: {branch.name}")
                 if u.city != branch.city:
                     print(f"WARNING: User {u.username} city mismatch. User: {u.city}, Branch: {branch.city}")
        
        if invalid_branches == 0:
            print("All RO usage of branch codes is valid.")
                     
        print("\nIntegrity check complete.")

if __name__ == "__main__":
    check_integrity()
