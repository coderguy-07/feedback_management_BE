import sys
import os
import pandas as pd

def main():
    file_path = os.path.join(os.path.dirname(__file__), "../scratch/data/RO_List.xlsx")
    file_path = os.path.abspath(file_path)
    
    try:
        df = pd.read_excel(file_path)
        
        # Normalize column names (strip spaces)
        df.columns = [c.strip() for c in df.columns]
        
        n_ros = df['RO Code'].nunique()
        n_fos = df['FO Name'].nunique()
        n_dos = df['Do Name'].nunique()
        
        print(f"Total Unique ROs: {n_ros}")
        print(f"Total Unique FOs: {n_fos}")
        print(f"Total Unique DOs: {n_dos}")
        print("-" * 50)
        
        print("\nMapping Structure:")
        
        # Group by DO
        by_do = df.groupby('Do Name')
        for do_name, do_group in by_do:
            print(f"\nDO: {do_name}")
            print(f"  Total ROs: {len(do_group)}")
            
            # FOs under this DO
            unique_fos = do_group[['FO Name', 'FO EMAIL']].drop_duplicates()
            print(f"  Unique FOs: {len(unique_fos)}")
            for _, fo_row in unique_fos.iterrows():
                fo_name = fo_row['FO Name']
                # Count ROs for this FO within this DO context
                ro_count = len(do_group[do_group['FO Name'] == fo_name])
                print(f"    - FO: {fo_name:<20} (Manages {ro_count} ROs)")
                
    except Exception as e:
        print(f"Error reading Excel file: {e}")

if __name__ == "__main__":
    main()
