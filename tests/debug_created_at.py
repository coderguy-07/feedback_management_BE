import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from sqlmodel import Session, select
from core.database import engine
from models import Feedback

def main():
    print(f"System Local Time: {datetime.now()}")
    print(f"System UTC Time:   {datetime.utcnow()}")
    print("-" * 60)
    
    with Session(engine) as session:
        # Fetch last 5 feedbacks
        feedbacks = session.exec(select(Feedback).order_by(Feedback.created_at.desc()).limit(5)).all()
        
        print(f"{'ID':<5} {'UTC (Stored)':<25} {'IST (Approximated +5:30)'}")
        print("-" * 60)
        
        for f in feedbacks:
            # Manually add 5:30 for display
            if f.created_at:
                ist_time = f.created_at + timedelta(hours=5, minutes=30)
                print(f"{f.id:<5} {str(f.created_at)[:19]:<25} {str(ist_time)[:19]}")

if __name__ == "__main__":
    main()
