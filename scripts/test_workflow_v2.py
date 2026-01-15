
import requests
import uuid
import sys
import os
from sqlmodel import Session, create_engine
from datetime import datetime

# Add parent directory to path to import models
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
from models import FOMapping, UserROMapping

# Configuration
BASE_URL = "http://localhost:8000"
TEST_BRANCH_CODE = f"E2E_V2_{str(uuid.uuid4())[:4]}"
TEST_CITY = "Test City V2"
TEST_PHONE = "9998887776"

# DB Connection for Seeding Mapping
SQLITE_FILE_NAME = "database.db"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, SQLITE_FILE_NAME)}"
engine = create_engine(DATABASE_URL)

def log(msg):
    print(f"[E2E V2] {msg}")

def ensure_login(username, password):
    resp = requests.post(f"{BASE_URL}/api/auth/login-json", json={"username": username, "password": password})
    if resp.status_code == 200:
        return resp.json()["token"]
    print(f"Login Failed for {username}: {resp.status_code} {resp.text}")
    return None

def test_workflow_v2():
    log("Starting V2 Workflow Test (Vendor -> DO -> FO -> DO)")
    
    # 1. Setup Data
    run_id = str(uuid.uuid4())[:8]
    super_token = ensure_login("admin", "admin123") # Assuming default admin
    if not super_token:
        # Try creating admin if not exists? Or assume one exists. 
        # In this env, main.py might have initialized one. 
        # Let's try the one from previous test: super/secret
        super_token = ensure_login("super", "secret")
        
    if not super_token:
        log("CRITICAL: Cannot login as Superuser/Admin. Aborting.")
        return

    headers_super = {"Authorization": f"Bearer {super_token}"}

    # Create Branch
    requests.post(f"{BASE_URL}/api/branches", json={
        "ro_code": TEST_BRANCH_CODE, "name": "V2 Test Branch", "city": TEST_CITY, "region": "V2 Region"
    }, headers=headers_super)

    # Create DO
    do_user = f"do_{run_id}"
    r = requests.post(f"{BASE_URL}/api/users/", json={
        "username": do_user, "email": f"{do_user}@test.com", "password": "DO123",
        "fullName": "Test DO V2", "branchCode": TEST_BRANCH_CODE, "role": "DO", "city": TEST_CITY
    }, headers=headers_super)
    if r.status_code != 200:
        log(f"Create DO Failed: {r.text}")
    else:
        log(f"Create DO Success: {do_user}")

    # Create FO
    fo_user = f"fo_{run_id}"
    r = requests.post(f"{BASE_URL}/api/users/", json={
        "username": fo_user, "email": f"{fo_user}@test.com", "password": "FO123",
        "fullName": "Test FO V2", "branchCode": TEST_BRANCH_CODE, "role": "FO"
    }, headers=headers_super)
    if r.status_code != 200:
        log(f"Create FO Failed: {r.text}")
    else:
        log(f"Create FO Success: {fo_user}")
    
    # Create Mapping (DO THIS DIRECTLY IN DB)
    with Session(engine) as session:
        mapping = FOMapping(fo_username=fo_user, ro_code=TEST_BRANCH_CODE, do_email=f"{do_user}@test.com")
        session.add(mapping)
        # Also add new UserROMapping for backend compatibility
        session.add(UserROMapping(username=fo_user, role="FO", ro_code=TEST_BRANCH_CODE))
        session.add(UserROMapping(username=do_user, role="DO", ro_code=TEST_BRANCH_CODE))
        session.commit()
    log(f"Created Mapping: FO {fo_user} -> RO {TEST_BRANCH_CODE}")

    # 2. Submit Feedback
    resp = requests.post(f"{BASE_URL}/feedback/", data={
        "phone": TEST_PHONE, "rating_air": 1, "rating_washroom": 1, "rating_water": 1,
        "comment": "V2 Workflow Test", "terms_accepted": True, "ro_number": TEST_BRANCH_CODE
    })
    if resp.status_code != 200:
        log(f"Feedback Submission Failed: {resp.text}")
        return
    feedback_id = resp.json()["id"]
    log(f"Feedback Created: {feedback_id} [Status: {resp.json()['workflow_status']}]")

    # 3. Vendor Step (Using Superuser)
    log("Step 1: Vendor Verification")
    resp = requests.patch(
        f"{BASE_URL}/api/feedbacks/{feedback_id}/workflow", 
        json={"status": "Vendor Verified"}, 
        headers=headers_super
    )
    if resp.status_code == 200:
        log("Vendor Verified: SUCCESS")
    else:
        log(f"Vendor Verified: FAILED {resp.text}")
        return

    # 4. DO Step 1 (Assignment)
    log("Step 2: DO Assignment")
    do_token = ensure_login(do_user, "DO123")
    headers_do = {"Authorization": f"Bearer {do_token}"}
    
    # DO tries to "assign" -> Should Auto -Assign
    resp = requests.patch(
        f"{BASE_URL}/api/feedbacks/{feedback_id}/workflow", 
        json={"status": "Assigned"}, 
        headers=headers_do
    )
    if resp.status_code == 200:
        log("DO Assignment: SUCCESS")
        # Verify assignment
        chk = requests.get(f"{BASE_URL}/api/feedbacks/{feedback_id}", headers=headers_super).json()
        log(f"Assigned To FO ID: {chk['data']['assignedFoId']}")
        if not chk['data']['assignedFoId']:
             log("Data Verification: FAILED (No FO ID)")
             return
    else:
        log(f"DO Assignment: FAILED {resp.text}")
        return

    # 5. FO Step
    log("Step 3: FO Action")
    fo_token = ensure_login(fo_user, "FO123")
    headers_fo = {"Authorization": f"Bearer {fo_token}"}
    
    resp = requests.patch(
        f"{BASE_URL}/api/feedbacks/{feedback_id}/workflow", 
        json={"status": "Action Taken"}, 
        headers=headers_fo
    )
    if resp.status_code == 200:
        log("FO Action: SUCCESS")
    else:
        log(f"FO Action: FAILED {resp.text}")
        return

    # 6. DO Step 2 (Resolution)
    log("Step 4: DO Resolution")
    resp = requests.patch(
        f"{BASE_URL}/api/feedbacks/{feedback_id}/workflow", 
        json={"status": "Resolved"}, 
        headers=headers_do
    )
    if resp.status_code == 200:
        log("DO Resolution: SUCCESS")
        # Final Check
        final = requests.get(f"{BASE_URL}/api/feedbacks/{feedback_id}", headers=headers_super).json()
        log(f"Final Status: {final['data']['workflowStatus']} (Expected: Resolved)")
        if final['data']['workflowStatus'] == "Resolved":
            log("TEST PASSED")
        else:
             log("TEST FAILED (Final status mismatch)")

    else:
        log(f"DO Resolution: FAILED {resp.text}")


if __name__ == "__main__":
    test_workflow_v2()
