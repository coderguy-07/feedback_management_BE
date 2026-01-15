import sqlite3
import os

# Path to database
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database.db")

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(feedback)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "workflow_status" not in columns:
            print("Adding workflow_status column...")
            cursor.execute("ALTER TABLE feedback ADD COLUMN workflow_status VARCHAR DEFAULT 'Pending'")
            # Add index? SQLite simple alter doesn't do index easily in one go, but we can do separately
            cursor.execute("CREATE INDEX ix_feedback_workflow_status ON feedback (workflow_status)")
            
        else:
            print("workflow_status column already exists.")

        if "assigned_fo_id" not in columns:
            print("Adding assigned_fo_id column...")
            cursor.execute("ALTER TABLE feedback ADD COLUMN assigned_fo_id VARCHAR DEFAULT NULL")
            cursor.execute("CREATE INDEX ix_feedback_assigned_fo_id ON feedback (assigned_fo_id)")
        else:
            print("assigned_fo_id column already exists.")

        conn.commit()
        print("Migration check complete.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
