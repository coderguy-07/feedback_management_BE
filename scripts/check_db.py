from sqlmodel import create_engine, Session, select, func
import sys
import os

# Add Backend directory to sys.path to resolve imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import Feedback, AdminUser, ReviewHistory, FOMapping, WhatsAppState

# Database URL from .env (hardcoded for script based on inspection)
DATABASE_URL = "sqlite:///Backend/database.db"
# Adjust path if running from root
if os.path.exists("Backend/database.db"):
    DATABASE_URL = "sqlite:///Backend/database.db"
elif os.path.exists("database.db"):
     DATABASE_URL = "sqlite:///database.db"
else:
    # try absolute path based on workspace
    DATABASE_URL = "sqlite:///d:/__SELF/Feedback_management_system/Backend/database.db"

engine = create_engine(DATABASE_URL)

def check_table(model, model_name):
    try:
        with Session(engine) as session:
            statement = select(func.count()).select_from(model)
            count = session.exec(statement).one()
            print(f"--- {model_name} ({count} rows) ---")
            
            if count > 0:
                statement = select(model).limit(5)
                results = session.exec(statement).all()
                for row in results:
                    print(row)
            else:
                print("No data.")
            print("\n")
    except Exception as e:
        print(f"Error checking {model_name}: {e}")

if __name__ == "__main__":
    print(f"Checking database at: {DATABASE_URL}\n")
    check_table(Feedback, "Feedback")
    check_table(AdminUser, "AdminUser")
    check_table(ReviewHistory, "ReviewHistory")
    check_table(FOMapping, "FOMapping")
    check_table(WhatsAppState, "WhatsAppState")
