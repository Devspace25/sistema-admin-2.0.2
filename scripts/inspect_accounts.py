from src.admin_app.db import make_session_factory
from src.admin_app.models import Account, Transaction

def list_accounts():
    session_factory = make_session_factory()
    session = session_factory()
    
    accounts = session.query(Account).all()
    print(f"{'ID':<5} {'Name':<35} {'Currency':<10} {'Balance':<15}")
    print("-" * 70)
    for acc in accounts:
        print(f"{acc.id:<5} {acc.name:<35} {acc.currency:<10} {acc.balance:,.2f}")
    
    print("-" * 70)
    session.close()

if __name__ == "__main__":
    list_accounts()
