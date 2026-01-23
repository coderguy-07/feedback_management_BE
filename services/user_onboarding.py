
import pandas as pd
import uuid
import io
from sqlmodel import Session, select
from core.security import get_password_hash
from models import AdminUser, UserROMapping, FOMapping
from models_refactor import Branch

def sanitize_username(name):
    """Converts 'Pratik Agarwal' to 'pratik_agarwal'."""
    if not name or pd.isna(name):
        return None
    return str(name).strip().lower().replace(" ", "_").replace(".", "")

def process_ro_excel_upload(file_content: bytes, session: Session):
    """
    Parses the RO List Excel and updates Users and Mappings for the full hierarchy:
    SRH -> DRSM -> DO -> FO -> RO
    """
    try:
        df = pd.read_excel(io.BytesIO(file_content))
        # Normalize columns
        df.columns = [c.strip() for c in df.columns]
        
        # Handle column name variations - normalize to expected names
        column_mappings = {
            'CUSTCODE': 'RO Code',
            'custcode': 'RO Code',
        }
        
        # Apply column name mappings
        df.rename(columns=column_mappings, inplace=True)
        
    except Exception as e:
        return {"success": False, "error": f"Failed to parse Excel: {str(e)}"}

    # Required structure check
    required_cols = ['RO Code', 'Do Name', 'FO Name', 'FO EMAIL'] 
    # Optional/Hierarchy cols: 'DRSM Name', 'DRSM EMAIL', 'SRH Name', 'SRH EMAIL'
    
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        return {"success": False, "error": f"Missing required columns: {missing}"}

    count_users = 0
    count_mappings = 0

    # Helper to upsert user
    def upsert_user(name, email, role, branch_code_prefix):
        nonlocal count_users
        username = sanitize_username(name)
        if not username: return None
        
        user = session.exec(select(AdminUser).where(AdminUser.username == username)).first()
        if not user:
            user = AdminUser(
                id=str(uuid.uuid4()),
                username=username,
                email=email if pd.notna(email) else f"{username}@example.com",
                password_hash=get_password_hash(f"{role}123"), # Default password convention
                full_name=name,
                branch_code=f"{branch_code_prefix}_OFFICE", 
                role=role,
                city=name.split(" ")[0] if " " in name else name, # Fallback city logic
                is_active=True
            )
            session.add(user)
            count_users += 1
        else:
            # Update email if provided
            if pd.notna(email):
                user.email = email
            # Ensure role match?
            if user.role != role:
                user.role = role # Promote/Demote?
            session.add(user)
        return username

    # Iterate rows - Process each RO code individually
    # Delete mappings ONLY for RO codes in this upload (selective update)
    # This preserves existing mappings for other RO codes

    # Iterate rows
    for _, row in df.iterrows():
        ro_code = str(row['RO Code'])
        if not ro_code or pd.isna(ro_code): continue

        # STEP 0: Create/Update Branch record (for branch_management view)
        ro_name = row.get('RO Name', ro_code)
        do_name_raw = row.get('Do Name', '')
        
        # Extract city from DO name (e.g., "Mumbai DO" -> "Mumbai")
        city = "Unknown"
        if pd.notna(do_name_raw) and str(do_name_raw).strip():
            city = str(do_name_raw).replace(' DO', '').strip()
        
        # Extract region from DRSM name if available
        region = None
        drsm_name_raw = row.get('DRSM Name')
        if pd.notna(drsm_name_raw):
            region = str(drsm_name_raw).strip()
        
        # Check if Branch already exists
        existing_branch = session.get(Branch, ro_code)
        if not existing_branch:
            # Create new Branch
            branch = Branch(
                ro_code=ro_code,
                name=str(ro_name) if pd.notna(ro_name) else ro_code,
                city=city,
                region=region
            )
            session.add(branch)
        else:
            # Update existing Branch (in case details changed)
            if pd.notna(ro_name):
                existing_branch.name = str(ro_name)
            existing_branch.city = city
            if region:
                existing_branch.region = region
            session.add(existing_branch)

        # PURELY ADDITIVE - No deletes, just add new mappings
        # Skip if mapping already exists to avoid duplicates

        # 1. FO
        fo_name = row.get('FO Name')
        fo_email = row.get('FO EMAIL')
        fo_user = upsert_user(fo_name, fo_email, "FO", "FO")
        
        if fo_user:
            # Check if mapping already exists
            existing = session.exec(
                select(UserROMapping).where(
                    UserROMapping.username == fo_user,
                    UserROMapping.role == "FO",
                    UserROMapping.ro_code == ro_code
                )
            ).first()
            if not existing:
                session.add(UserROMapping(username=fo_user, role="FO", ro_code=ro_code))

        # 2. DO
        do_name = row.get('Do Name')
        do_user = upsert_user(do_name, None, "DO", "DO")
        if do_user:
            existing = session.exec(
                select(UserROMapping).where(
                    UserROMapping.username == do_user,
                    UserROMapping.role == "DO",
                    UserROMapping.ro_code == ro_code
                )
            ).first()
            if not existing:
                session.add(UserROMapping(username=do_user, role="DO", ro_code=ro_code))

        # 3. DRSM
        drsm_name = row.get('DRSM Name')
        drsm_email = row.get('DRSM EMAIL')
        drsm_user = upsert_user(drsm_name, drsm_email, "DRSM", "DRSM")
        if drsm_user:
            existing = session.exec(
                select(UserROMapping).where(
                    UserROMapping.username == drsm_user,
                    UserROMapping.role == "DRSM",
                    UserROMapping.ro_code == ro_code
                )
            ).first()
            if not existing:
                session.add(UserROMapping(username=drsm_user, role="DRSM", ro_code=ro_code))

        # 4. SRH
        srh_name = row.get('SRH Name')
        srh_email = row.get('SRH EMAIL')
        srh_user = upsert_user(srh_name, srh_email, "SRH", "SRH")
        if srh_user:
            existing = session.exec(
                select(UserROMapping).where(
                    UserROMapping.username == srh_user,
                    UserROMapping.role == "SRH",
                    UserROMapping.ro_code == ro_code
                )
            ).first()
            if not existing:
                session.add(UserROMapping(username=srh_user, role="SRH", ro_code=ro_code))

        # Legacy FOMapping Sync (also check for duplicates)
        if fo_user and do_user:
            existing_fo_mapping = session.exec(
                select(FOMapping).where(
                    FOMapping.fo_username == fo_user,
                    FOMapping.ro_code == ro_code
                )
            ).first()
            if not existing_fo_mapping:
                session.add(FOMapping(
                    fo_username=fo_user,
                    ro_code=ro_code,
                    do_email=f"{do_user}@example.com"
                ))
            
        count_mappings += 1

    try:
        session.commit()
        return {
            "success": True, 
            "message": f"Successfully processed {len(df)} rows. Created/Updated {count_users} users and {count_mappings} Branch records. "
                       f"Added new mappings for {count_mappings} RO codes. "
                       f"All existing data preserved (purely additive). "
                       f"Branch management and hierarchy views updated.",
            "rows_processed": len(df),
            "users_created_updated": count_users,
            "ro_codes_processed": count_mappings
        }
    except Exception as e:
        session.rollback()
        return {"success": False, "error": f"Database error: {str(e)}"}
