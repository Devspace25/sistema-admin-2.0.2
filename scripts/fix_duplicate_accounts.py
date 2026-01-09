from src.admin_app.db import make_session_factory
from src.admin_app.models import Account, Transaction

def fix_duplicates():
    session_factory = make_session_factory()
    session = session_factory()
    
    try:
        # 1. Fix Banesco
        # We want to keep the account that has data.
        # ID 3: Banesco (Bs) (Has Data)
        # ID 7: Banesco (Empty)
        
        acc_old_banesco = session.query(Account).filter(Account.name == "Banesco (Bs)").first()
        acc_new_banesco = session.query(Account).filter(Account.name == "Banesco").first()
        
        if acc_old_banesco and acc_new_banesco:
            print(f"Merging Banesco... Keeping ID {acc_old_banesco.id}, deleting ID {acc_new_banesco.id}")
            if acc_new_banesco.balance == 0:
                session.delete(acc_new_banesco)
                session.flush() # Ensure delete is processed before rename
                acc_old_banesco.name = "Banesco" # Rename old to clean name
            else:
                print("Warning: New Banesco account has balance! Merging transactions not implemented.")

        # 2. Fix Banco de Venezuela
        # ID 4: Banco de Venezuela (Bs) (Has Data)
        # ID 6: Banco de Venezuela (Empty)
        acc_old_bdv = session.query(Account).filter(Account.name == "Banco de Venezuela (Bs)").first()
        acc_new_bdv = session.query(Account).filter(Account.name == "Banco de Venezuela").first()
        
        if acc_old_bdv and acc_new_bdv:
             print(f"Merging BDV... Keeping ID {acc_old_bdv.id}, deleting ID {acc_new_bdv.id}")
             if acc_new_bdv.balance == 0:
                 session.delete(acc_new_bdv)
                 session.flush() # Ensure delete is processed before rename
                 acc_old_bdv.name = "Banco de Venezuela"
             else:
                 print("Warning: New BDV account has balance!")

        # 3. Rename Zelle/Digital if needed
        # User said "Zelle".
        acc_zelle = session.query(Account).filter(Account.name == "Zelle / Digital").first()
        if acc_zelle:
            print("Renaming 'Zelle / Digital' to 'Zelle'")
            acc_zelle.name = "Zelle"

        session.commit()
        print("Duplicates fixed.")
        
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    fix_duplicates()
