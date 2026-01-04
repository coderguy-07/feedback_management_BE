import sys
import os

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from sqlmodel import Session, select
from core.database import engine
from models import AdminUser, FOMapping, Feedback

def main():
    with Session(engine) as session:
        # 1. Verify DOs
        print("--- Verifying DOs ---")
        dos = session.exec(select(AdminUser).where(AdminUser.role == "DO")).all()
        for do in dos:
            print(f"Found DO: {do.username} ({do.city})")
            
        # 2. Verify FOs and Mappings
        print("\n--- Verifying FOs and Mappings ---")
        fos = session.exec(select(AdminUser).where(AdminUser.role == "FO")).all()
        for fo in fos:
            mappings = session.exec(select(FOMapping).where(FOMapping.fo_username == fo.username)).all()
            ro_codes = [m.ro_code for m in mappings]
            print(f"FO: {fo.username:<20} | Mapped to {len(mappings)} ROs | Codes: {ro_codes[:3]}...")

        # 3. Simulate FO Access (pratik_agarwal)
        target_fo = "pratik_agarwal"
        print(f"\n--- Simulating Access for {target_fo} ---")
        mappings = session.exec(select(FOMapping).where(FOMapping.fo_username == target_fo)).all()
        valid_ros = [m.ro_code for m in mappings]
        print(f"Valid ROs: {valid_ros}")
        
        if valid_ros:
            # Check RBAC logic equivalent
            stmt = select(Feedback).where(Feedback.ro_number.in_(valid_ros))
            feedbacks = session.exec(stmt).all()
            print(f"Feedbacks visible to {target_fo}: {len(feedbacks)}")
            
if __name__ == "__main__":
    main()
