import sys
import os
import pandas as pd

def main():
    file_path = os.path.join(os.path.dirname(__file__), "../scratch/data/RO_List.xlsx")
    file_path = os.path.abspath(file_path)
    
    print(f"Reading file: {file_path}")
    
    try:
        df = pd.read_excel(file_path)
        print("File read successfully.")
        print("-" * 50)
        print("Columns:", df.columns.tolist())
        print("-" * 50)
        print("First 10 rows:")
        print(df.head(10).to_string())
        print("-" * 50)
        print(f"Total Rows: {len(df)}")
    except Exception as e:
        print(f"Error reading Excel file: {e}")

if __name__ == "__main__":
    main()
