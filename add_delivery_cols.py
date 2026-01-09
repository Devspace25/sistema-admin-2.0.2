from sqlalchemy import create_engine, text

def add_columns():
    engine = create_engine('sqlite:///data/app.db')
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE orders ADD COLUMN delivered_at DATETIME"))
            print("Added delivered_at")
        except Exception as e:
            print(f"Error adding delivered_at: {e}")
            
        try:
            conn.execute(text("ALTER TABLE orders ADD COLUMN delivery_method VARCHAR(50)"))
            print("Added delivery_method")
        except Exception as e:
            print(f"Error adding delivery_method: {e}")
            
        conn.commit()

if __name__ == "__main__":
    add_columns()
