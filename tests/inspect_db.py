import sys
import os
from sqlalchemy import text
from sqlmodel import Session

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from core.database import engine

def inspect_db():
    print(f"{'Table Name':<30} {'Row Count':<10}")
    print("-" * 40)
    
    with Session(engine) as session:
        # Get list of tables (SQLite specific)
        result = session.exec(text("SELECT name FROM sqlite_master WHERE type='table';")).all()
        tables = [row[0] for row in result if row[0] != "sqlite_sequence"]
        
        for table in tables:
            try:
                count = session.exec(text(f"SELECT COUNT(*) FROM {table}")).one()[0]
                print(f"{table:<30} {count:<10}")
            except Exception as e:
                print(f"{table:<30} Error: {e}")

if __name__ == "__main__":
    inspect_db()
