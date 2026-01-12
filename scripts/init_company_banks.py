from src.admin_app.db import make_session_factory
from src.admin_app.models import Account

def init_banks():
    session_factory = make_session_factory()
    session = session_factory()
    
    # List of Company Banks (VES)
    banks_ves = [
        "Banco de Venezuela",
        "Banesco",
        "Bancamiga"
    ]
    
    # Check and Create VES Banks
    print("Checking VES Banks...")
    for bank_name in banks_ves:
        acc = session.query(Account).filter(Account.name == bank_name, Account.currency == 'VES').first()
        if not acc:
            # Check if exists with "Banco" prefix for Banesco/Bancamiga if not in list
            # But the list names are what we want.
            print(f"Creating account: {bank_name} (VES)")
            new_acc = Account(
                name=bank_name,
                type='BANK',
                currency='VES',
                balance=0.0,
                is_active=True
            )
            session.add(new_acc)
        else:
            print(f"Found: {acc.name}")

    # Ensure Zelle exists (USD)
    print("\nChecking USD Accounts...")
    zelle = session.query(Account).filter(Account.name.ilike('%Zelle%'), Account.currency == 'USD').first()
    if not zelle:
         print("Creating account: Zelle (USD)")
         new_zelle = Account(
            name="Zelle",
            type='DIGITAL',
            currency='USD',
            balance=0.0,
            is_active=True
         )
         session.add(new_zelle)
    else:
         print(f"Found: {zelle.name}")
         
    try:
        session.commit()
        print("\nBank initialization complete.")
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    init_banks()
