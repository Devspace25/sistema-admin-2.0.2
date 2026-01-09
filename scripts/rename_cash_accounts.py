from src.admin_app.db import make_session_factory
from src.admin_app.models import Account

def rename_accounts():
    session_factory = make_session_factory()
    session = session_factory()
    try:
        # 1. Rename USD Cash
        acc_usd = session.query(Account).filter(Account.name == "Caja Chica (USD)").first()
        if acc_usd:
            print(f"Renaming {acc_usd.name} to 'Efectivo USD'")
            acc_usd.name = "Efectivo USD"
        
        # 2. Rename VES Cash
        acc_bs = session.query(Account).filter(Account.name == "Caja Chica (Bs)").first()
        if acc_bs:
            print(f"Renaming {acc_bs.name} to 'Efectivo Bs'")
            acc_bs.name = "Efectivo Bs"
            
        session.commit()
        print("Accounts renamed successfully.")
        
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    rename_accounts()
