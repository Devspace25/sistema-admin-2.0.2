import sqlite3
import os

DB_PATH = os.path.join("data", "app.db")

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        print("Checking 'deliveries' table...")
        cursor.execute("PRAGMA table_info(deliveries)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "payment_source" not in columns:
            print("Adding 'payment_source' column...")
            cursor.execute("ALTER TABLE deliveries ADD COLUMN payment_source VARCHAR(50) DEFAULT 'EMPRESA'")
            print("Column added successfully.")
        else:
            print("Column 'payment_source' already exists.")
            
        conn.commit()
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
