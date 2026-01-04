import sys
import os

# Add parent directory to path to import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select, delete
from core.database import engine
from models import Feedback

def clean_feedbacks():
    print("Connecting to database...")
    with Session(engine) as session:
        # Check current count
        statement = select(Feedback)
        results = session.exec(statement).all()
        count = len(results)
        print(f"Found {count} existing feedback records.")
        
        if count == 0:
            print("No feedbacks to clean.")
            return

        # Delete all
        print("Deleting all feedback records...")
        session.exec(delete(Feedback))
        session.commit()
        
        # Verify
        results = session.exec(statement).all()
        new_count = len(results)
        print(f"Feedbacks cleared. Current count: {new_count}")

if __name__ == "__main__":
    clean_feedbacks()
