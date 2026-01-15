
import requests
import json
import os

API_URL = "http://localhost:8000"
EXCEL_PATH = os.path.join(os.path.dirname(__file__), "../scratch/data/RO_List.xlsx")

def login(username, password):
    url = f"{API_URL}/api/auth/login-json"
    payload = {"username": username, "password": password}
    try:
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            return r.json()["token"]
        else:
            print(f"Login failed: {r.status_code} {r.text}")
            return None
    except Exception as e:
        print(f"Connection failed: {e}")
        return None

def test_onboarding():
    print("1. Logging in as superuser...")
    token = login("admin", "admin123")
    if not token: return

    headers = {"Authorization": f"Bearer {token}"}

    print("\n2. Uploading RO List...")
    url = f"{API_URL}/api/users/upload_ro_list"
    
    if not os.path.exists(EXCEL_PATH):
        print(f"Error: File not found at {EXCEL_PATH}")
        return

    with open(EXCEL_PATH, 'rb') as f:
        files = {'file': ('RO_List.xlsx', f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        r = requests.post(url, headers=headers, files=files)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()}")

    print("\n3. Verifying Hierarchy...")
    url = f"{API_URL}/api/users/hierarchy"
    r = requests.get(url, headers=headers)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json().get("data", [])
        print(f"Root Nodes: {len(data)}")
        if data:
            root = data[0]
            print(f"Root: {root['name']} ({root['type']})")
            if root['children']:
                child = root['children'][0]
                print(f"  -> Child: {child['name']} ({child['type']})")
                if child['children']:
                    grandchild = child['children'][0]
                    print(f"    -> Grandchild: {grandchild['name']} ({grandchild['type']})")
    
if __name__ == "__main__":
    test_onboarding()
