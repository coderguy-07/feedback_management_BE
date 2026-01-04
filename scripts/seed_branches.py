import pandas as pd
import sys
import os
from sqlmodel import Session, select, create_engine

# Add Backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models_refactor import Branch
from core.database import engine # Re-use existing engine if possible, or create new
# Note: Ensure models_refactor is imported so SQLModel knows about it
from core.config import settings

# Explicitly create engine if needed for script context
# DATABASE_URL = "sqlite:///Backend/database.db" 
# Using the one from core.database is better if environment is set up

def seed_branches():
    file_path = r"d:\__SELF\Feedback_management_system\Backend\scratch\data\RO_List.xlsx"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    try:
        df = pd.read_excel(file_path)
        # Columns: ['RO Code', 'RO Name', 'Do Name', 'FO Name', 'FO EMAIL', 'DRSM Name', 'DRSM EMAIL', 'SRH Name', 'SRH EMAIL']
        
        print(f"Found {len(df)} rows in Excel.")
        
        with Session(engine) as session:
            # Create table if not exists (hack for now until migration)
            Branch.metadata.create_all(engine)
            
            count = 0
            for index, row in df.iterrows():
                try:
                    ro_code = str(row['RO Code']).strip()
                    if pd.isna(row['RO Code']) or ro_code == 'nan':
                        print(f"Skipping row {index} due to missing RO Code")
                        continue
                        
                    ro_name = str(row['RO Name']).strip()
                    if ro_name == 'nan': ro_name = "Unknown RO"
                    
                    do_name = str(row['Do Name']).strip()
                    if do_name == 'nan': 
                        city = "Unknown City"
                    else:
                        city = do_name.replace(' DO', '').strip()
                    
                    region = str(row['DRSM Name']).strip()
                    if region == 'nan': region = None

                    # print(f"Processing: {ro_code} - {city}")

                    branch = session.get(Branch, ro_code)
                    if not branch:
                        branch = Branch(
                            ro_code=ro_code,
                            name=ro_name,
                            city=city,
                            do_email=None, 
                            fo_username=None,
                            region=region
                        )
                        session.add(branch)
                        count += 1
                    else:
                        branch.name = ro_name
                        branch.city = city
                        branch.region = region
                        session.add(branch)
                except Exception as row_err:
                    print(f"Error processing row {index}: {row_err}")
                    print(f"Row data: {row.to_dict()}")
            
            session.commit()
            print(f"Seeded {count} new branches.")
            
    except Exception as e:
        print(f"Error seeding branches: {e}")

if __name__ == "__main__":
    seed_branches()
