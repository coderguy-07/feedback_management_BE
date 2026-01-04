import requests
import json

BASE_URL = "http://localhost:8000"

def test_hierarchy():
    # Login as superuser
    resp = requests.post(f"{BASE_URL}/api/auth/login-json", json={"username": "super", "password": "secret"})
    if resp.status_code != 200:
        print("Login failed")
        return
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get Hierarchy
    print("Fetching hierarchy...")
    resp = requests.get(f"{BASE_URL}/api/users/hierarchy", headers=headers)
    
    if resp.status_code == 200:
        data = resp.json()["data"]
        print("Hierarchy fetched successfully.")
        print(json.dumps(data, indent=2))
        
        # Validation checks
        if isinstance(data, list):
            print("Structure is a list (Cities/DOs). OK.")
            if len(data) > 0:
                 city = data[0]
                 if "children" in city and "type" in city:
                     print("City node structure correct. OK.")
        else:
            print("Structure invalid.")
    else:
        print(f"Failed to fetch hierarchy: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    test_hierarchy()
