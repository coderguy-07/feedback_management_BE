from sqlmodel import create_engine, Session, select, func
import sys
import os

# Add Backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import Feedback, AdminUser, ReviewHistory, FOMapping, WhatsAppState

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

def get_count(model, name):
    try:
        with Session(engine) as session:
            count = session.exec(select(func.count()).select_from(model)).one()
            print(f"{name}: {count}")
    except Exception as e:
        print(f"{name}: Error {e}")

if __name__ == "__main__":
    get_count(Feedback, "Feedback")
    get_count(AdminUser, "AdminUser")
    get_count(ReviewHistory, "ReviewHistory")
    get_count(FOMapping, "FOMapping")
    get_count(WhatsAppState, "WhatsAppState")
