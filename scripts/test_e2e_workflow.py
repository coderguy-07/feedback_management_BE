import requests
import uuid
import sys
import os

# Configuration
BASE_URL = "http://localhost:8000"
TEST_BRANCH_CODE = "E2E_TEST_001"
TEST_CITY = "Test City"
TEST_PHONE = "1234567890"

def log(msg):
    print(f"[E2E] {msg}")

def test_workflow():
    session = requests.Session()
    
    # 1. Login as Superuser
    log("Logging in as Superuser...")
    # Using the JSON-friendly login endpoint defined in routers/auth.py
    resp = session.post(f"{BASE_URL}/api/auth/login-json", json={"username": "super", "password": "secret"})
    if resp.status_code != 200:
        log(f"Login Failed: {resp.text}")
        return
    token = resp.json()["token"] # Token key is 'token' in LoginResponse
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Create Branch
    log(f"Creating Branch {TEST_BRANCH_CODE}...")
    try:
        # Check if exists first to clean up? Or just ignore error
        requests.delete(f"{BASE_URL}/api/branches/{TEST_BRANCH_CODE}", headers=headers)
    except:
        pass
        
    branch_data = {
        "ro_code": TEST_BRANCH_CODE,
        "name": "E2E Test Branch",
        "city": TEST_CITY,
        "region": "Test Region"
    }
    resp = requests.post(f"{BASE_URL}/api/branches", json=branch_data, headers=headers)
    if resp.status_code not in [200, 201]:
        log(f"Create Branch Failed: {resp.text}")
        # return # Proceeding might fail but let's see

    # 3. Create Users
    run_id = str(uuid.uuid4())[:8]
    
    # RO
    ro_user = f"ro_{run_id}"
    log(f"Creating RO User {ro_user}...")
    
    ro_data = {
        "username": ro_user, "email": f"{ro_user}@test.com", "password": "password",
        "fullName": "Test RO", "branchCode": TEST_BRANCH_CODE, "role": "RO"
    }
    resp = requests.post(f"{BASE_URL}/api/users/", json=ro_data, headers=headers)
    if resp.status_code != 200:
        log(f"Create RO Failed: {resp.text}")

    # FO
    fo_user = f"fo_{run_id}"
    log(f"Creating FO User {fo_user}...")
    
    fo_data = {
        "username": fo_user, "email": f"{fo_user}@test.com", "password": "password",
        "fullName": "Test FO", "branchCode": TEST_BRANCH_CODE, "role": "FO"
    }
    resp = requests.post(f"{BASE_URL}/api/users/", json=fo_data, headers=headers)
    if resp.status_code != 200:
        log(f"Create FO Failed: {resp.text}")
        
    # DO
    do_user = f"do_{run_id}"
    log(f"Creating DO User {do_user}...")
    do_data = {
        "username": do_user, "email": f"{do_user}@test.com", "password": "password",
        "fullName": "Test DO", "branchCode": TEST_BRANCH_CODE, "role": "DO"
    }
    resp = requests.post(f"{BASE_URL}/api/users/", json=do_data, headers=headers)
    if resp.status_code != 200:
        log(f"Create DO Failed: {resp.text}")


    # 4. Submit Feedback (Simulate Public User)
    log("Submitting Feedback...")
    feedback_data = {
        "phone": TEST_PHONE,
        "rating_air": 1, "rating_washroom": 1, "rating_water": 1, # Negative to trigger workflow?
        "comment": "E2E Test Feedback",
        "terms_accepted": True,
        "ro_number": TEST_BRANCH_CODE
    }
    # Feedback endpoint is form data
    resp = requests.post(f"{BASE_URL}/feedback/", data=feedback_data)
    if resp.status_code != 200:
        log(f"Feedback Submission Failed: {resp.text}")
        return
    feedback_id = resp.json()["id"]
    log(f"Feedback Submitted. ID: {feedback_id}, Status: {resp.json()['status']}")
    
    # login helper
    def get_token(u, p="password"):
        resp = requests.post(f"{BASE_URL}/api/auth/login-json", json={"username": u, "password": p})
        if resp.status_code != 200:
            log(f"Login failed for {u}")
            return None
        return resp.json()["token"]

    # 5. Workflow: RO Verify
    log("--- Step: RO Verify ---")
    ro_token = get_token(ro_user)
    if ro_token:
        headers_ro = {"Authorization": f"Bearer {ro_token}"}
        # Verify
        resp = requests.patch(f"{BASE_URL}/api/feedbacks/{feedback_id}/workflow", json={"status": "RO Verified"}, headers=headers_ro)
        log(f"RO Verify Response: {resp.status_code} - {resp.text}")
    else:
        log("Skipping RO step (Login failed)")

    # 6. Workflow: DO Verify & Auto Assign
    log("--- Step: DO Verify ---")
    do_token = get_token(do_user)
    if do_token:
        headers_do = {"Authorization": f"Bearer {do_token}"}
        # Verify (Triggers Auto Assign)
        resp = requests.patch(f"{BASE_URL}/api/feedbacks/{feedback_id}/workflow", json={"status": "DO Verified"}, headers=headers_do)
        log(f"DO Verify Response: {resp.status_code} - {resp.text}")
        
        # Check if Assigned
        resp = requests.get(f"{BASE_URL}/api/feedbacks/{feedback_id}", headers=headers_do)
        status = resp.json()["data"]["workflowStatus"]
        fo_id = resp.json()["data"]["assignedFoId"]
        log(f"Post-DO Status: {status}")
        log(f"Assigned FO ID: {fo_id}")
        if status == "Assigned" and fo_id:
            log("SUCCESS: Auto- Assignment Worked!")
        else:
            log("FAILURE: Auto-Assignment Failed.")

    else:
        log("Skipping DO step (Login failed)")
        
    # 7. Workflow: FO Resolve
    log("--- Step: FO Resolve ---")
    fo_token = get_token(fo_user)
    if fo_token:
        headers_fo = {"Authorization": f"Bearer {fo_token}"}
        resp = requests.patch(f"{BASE_URL}/api/feedbacks/{feedback_id}/workflow", json={"status": "Resolved"}, headers=headers_fo)
        log(f"FO Resolve Response: {resp.status_code} - {resp.text}")
    else:
         log("Skipping FO step (Login failed)")

    # 8. Workflow: DO Close
    log("--- Step: DO Close ---")
    if do_token:
        headers_do = {"Authorization": f"Bearer {do_token}"}
        resp = requests.patch(f"{BASE_URL}/api/feedbacks/{feedback_id}/workflow", json={"status": "Closed"}, headers=headers_do)
        log(f"DO Close Response: {resp.status_code} - {resp.text}")
        
        # Final Check
        resp = requests.get(f"{BASE_URL}/api/feedbacks/{feedback_id}", headers=headers_do)
        status = resp.json()["data"]["workflowStatus"]
        log(f"Final Status: {status}")
        if status == "Closed":
            log("E2E TEST PASSED COMPLETE CYLCE")
        else:
            log("E2E TEST FAILED TO CLOSE")

if __name__ == "__main__":
    test_workflow()
