
import sqlite3
import os

DB_PATH = "data/app.db"

def upgrade_db():
    if not os.path.exists(DB_PATH):
        print("DB not found in data/app.db, skipping upgrade.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(workers)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if "payment_frequency" not in columns:
        print("Adding payment_frequency column to workers table...")
        try:
            cursor.execute("ALTER TABLE workers ADD COLUMN payment_frequency TEXT DEFAULT 'QUINCENAL'")
            conn.commit()
            print("Column added successfully.")
            
            # Update existing 'Diseñadores' to WEEKLY to migrate data
            print("Migrating existing Designers to WEEKLY...")
            cursor.execute("UPDATE workers SET payment_frequency = 'SEMANAL' WHERE rol LIKE '%diseñad%'")
            conn.commit()
            print("Migration done.")
            
        except Exception as e:
            print(f"Error adding column: {e}")
    else:
        print("Column payment_frequency already exists.")

    conn.close()

if __name__ == "__main__":
    upgrade_db()
