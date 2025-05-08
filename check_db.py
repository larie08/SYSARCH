import sqlite3

def check_resources():
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        
        # Check if resources table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resources';")
        if not cursor.fetchone():
            print("Resources table does not exist!")
            return
            
        # Count resources
        cursor.execute("SELECT COUNT(*) FROM resources;")
        count = cursor.fetchone()[0]
        print(f"Total resources in database: {count}")
        
        # Get sample of resources
        cursor.execute("""
            SELECT folder_name, name, file_path, is_active 
            FROM resources 
            LIMIT 5;
        """)
        resources = cursor.fetchall()
        print("\nSample resources:")
        for r in resources:
            print(f"Folder: {r[0]}, Name: {r[1]}, Path: {r[2]}, Active: {r[3]}")
            
    except Exception as e:
        print(f"Error checking database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_resources()