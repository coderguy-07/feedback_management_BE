import sys
import os

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from core.database import engine
from models import Feedback

def main():
    print(f"{'ID':<5} {'Phone':<15} {'Rating(A/W/W)':<15} {'Status':<10} {'Created At'}")
    print("-" * 70)
    
    with Session(engine) as session:
        statement = select(Feedback).order_by(Feedback.created_at.desc())
        feedbacks = session.exec(statement).all()
        
        for f in feedbacks:
            # Format ratings
            ratings = f"{f.rating_air or '-'}/{f.rating_washroom or '-'}/{f.rating_water or '-'}"
            
            print(f"{f.id:<5} {f.phone:<15} {ratings:<15} {f.status:<10} {f.created_at}")

if __name__ == "__main__":
    main()
