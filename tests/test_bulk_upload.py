"""
Test script to verify bulk upload functionality
"""
import pandas as pd
import io
from sqlmodel import Session, select
from core.database import engine
from models import UserROMapping, FOMapping, AdminUser
from services.user_onboarding import process_ro_excel_upload

def test_bulk_upload():
    print("=== Testing Bulk Upload Functionality ===\n")
    
    # Step 1: Check current state
    with Session(engine) as session:
        initial_count = len(session.exec(select(UserROMapping)).all())
        print(f"1. Initial UserROMapping count: {initial_count}")
        
        initial_users = len(session.exec(select(AdminUser)).all())
        print(f"   Initial AdminUser count: {initial_users}")
    
    # Step 2: Create test Excel data
    print("\n2. Creating test Excel with 2 RO codes...")
    test_data = {
        'RO Code': ['TEST_RO_001', 'TEST_RO_002'],
        'RO Name': ['Test RO One', 'Test RO Two'],
        'Do Name': ['Test DO Alpha', 'Test DO Beta'],
        'FO Name': ['Test FO Alpha', 'Test FO Beta'],
        'FO EMAIL': ['fo_alpha@test.com', 'fo_beta@test.com'],
        'DRSM Name': ['Test DRSM One', 'Test DRSM Two'],
        'DRSM EMAIL': ['drsm1@test.com', 'drsm2@test.com'],
        'SRH Name': ['Test SRH', 'Test SRH'],
        'SRH EMAIL': ['srh@test.com', 'srh@test.com']
    }
    
    df = pd.DataFrame(test_data)
    
    # Convert to Excel bytes
    output = io.BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    excel_bytes = output.getvalue()
    
    print(f"   Created Excel with {len(df)} rows")
    
    # Step 3: Test the upload
    print("\n3. Testing upload...")
    with Session(engine) as session:
        result = process_ro_excel_upload(excel_bytes, session)
    
    if result["success"]:
        print(f"   ✓ Upload successful!")
        print(f"   Message: {result['message']}")
    else:
        print(f"   ✗ Upload failed!")
        print(f"   Error: {result.get('error', 'Unknown error')}")
        return False
    
    # Step 4: Verify data was added
    print("\n4. Verifying data was added...")
    with Session(engine) as session:
        final_count = len(session.exec(select(UserROMapping)).all())
        print(f"   Final UserROMapping count: {final_count}")
        
        # Check specific test mappings
        test_mappings = session.exec(
            select(UserROMapping).where(
                UserROMapping.ro_code.in_(['TEST_RO_001', 'TEST_RO_002'])
            )
        ).all()
        print(f"   Test RO mappings found: {len(test_mappings)}")
        
        if len(test_mappings) > 0:
            print("\n   Sample mappings:")
            for m in test_mappings[:5]:
                print(f"     - {m.ro_code} | {m.role} | {m.username}")
        
        # Check if old data preserved
        if final_count >= initial_count:
            print(f"\n   ✓ Old data preserved (count increased from {initial_count} to {final_count})")
        else:
            print(f"\n   ✗ WARNING: Data lost! (count decreased from {initial_count} to {final_count})")
    
    # Step 5: Test duplicate prevention (upload same data again)
    print("\n5. Testing duplicate prevention (uploading same data again)...")
    with Session(engine) as session:
        result2 = process_ro_excel_upload(excel_bytes, session)
    
    with Session(engine) as session:
        after_duplicate = len(session.exec(select(UserROMapping)).all())
        
        if after_duplicate == final_count:
            print(f"   ✓ Duplicates prevented! Count unchanged: {after_duplicate}")
        else:
            print(f"   ✗ Duplicates created! Count changed from {final_count} to {after_duplicate}")
    
    print("\n=== Test Complete ===")
    return True

if __name__ == "__main__":
    try:
        test_bulk_upload()
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
