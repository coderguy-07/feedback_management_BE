import sys
import os
import pandas as pd
import uuid

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from sqlmodel import Session, select
from core.database import engine
from core.security import get_password_hash
from models import AdminUser, FOMapping

EXCEL_PATH = os.path.join(os.path.dirname(__file__), "../scratch/data/RO_List.xlsx")

def sanitize_username(name):
    """Converts 'Pratik Agarwal' to 'pratik_agarwal'."""
    if not name or pd.isna(name):
        return None
    return str(name).strip().lower().replace(" ", "_").replace(".", "")

def main():
    if not os.path.exists(EXCEL_PATH):
        print(f"Error: File not found at {EXCEL_PATH}")
        return

    print("Reading Excel file...")
    try:
        df = pd.read_excel(EXCEL_PATH)
        df.columns = [c.strip() for c in df.columns] # Clean columns
    except Exception as e:
        print(f"Error reading Excel: {e}")
        return

    settings_pwd_hash = get_password_hash("password123") # Default password

    with Session(engine) as session:
        # 1. Process DOs
        print("\nProcessing DOs...")
        unique_dos = df['Do Name'].dropna().unique()
        for do_name in unique_dos:
            username = sanitize_username(do_name)
            if not username: continue
            
            # Check exist
            user = session.exec(select(AdminUser).where(AdminUser.username == username)).first()
            if not user:
                print(f"Creating DO: {username}")
                user = AdminUser(
                    id=str(uuid.uuid4()),
                    username=username,
                    email=f"{username}@example.com", # Placeholder
                    password_hash=get_password_hash("DO123"),
                    full_name=do_name,
                    branch_code="DO_OFFICE", # Generic
                    role="DO",
                    city=do_name.split(" ")[0] if " " in do_name else do_name, # Approximation
                    is_active=True
                )
                session.add(user)
            else:
                print(f"Update DO: {username}")
                user.city = do_name.split(" ")[0] if " " in do_name else do_name
                session.add(user)
        
        # 2. Process FOs
        print("\nProcessing FOs...")
        # Get unique FOs with their emails
        fos = df[['FO Name', 'FO EMAIL']].drop_duplicates().dropna(subset=['FO Name'])
        
        for _, row in fos.iterrows():
            fo_name = row['FO Name']
            fo_email = row['FO EMAIL']
            username = sanitize_username(fo_name)
            
            if not username: continue
            
            # Check exist
            user = session.exec(select(AdminUser).where(AdminUser.username == username)).first()
            if not user:
                print(f"Creating FO: {username}")
                user = AdminUser(
                    id=str(uuid.uuid4()),
                    username=username,
                    email=fo_email if pd.notna(fo_email) else f"{username}@example.com",
                    password_hash=get_password_hash("FO123"),
                    full_name=fo_name,
                    branch_code="FO_CLUSTER", # Placeholder, mapping table handles real link
                    role="FO",
                    is_active=True
                )
                session.add(user)
            else:
                 print(f"Updating FO: {username}")
                 if pd.notna(fo_email):
                     user.email = fo_email
                 session.add(user)
        
        session.commit() # Commit users first

        # 3. Process Mappings
        print("\nProcessing Mappings...")
        # Clear existing mappings? Maybe safer to truncate table first if re-running
        session.exec(select(FOMapping)).all() 
        # Actually, let's just delete all and re-insert to be clean sync
        session.exec(FOMapping.__table__.delete())
        
        count = 0
        for _, row in df.iterrows():
            fo_name = row['FO Name']
            ro_code = row['RO Code']
            do_name = row['Do Name']
            
            fo_username = sanitize_username(fo_name)
            
            if fo_username and pd.notna(ro_code):
                mapping = FOMapping(
                    fo_username=fo_username,
                    ro_code=str(ro_code),
                    do_email=f"{sanitize_username(do_name)}@example.com" # Best guess link
                )
                session.add(mapping)
                count += 1
        
        session.commit()
        print(f"Successfully seeded {count} mappings.")

if __name__ == "__main__":
    main()
