from src.admin_app.db import make_engine, make_session_factory
from src.admin_app.models import User, Role, UserRole, Order
from src.admin_app.repository import user_has_role, get_pending_orders_for_user

engine = make_engine()
session_factory = make_session_factory(engine)

with session_factory() as session:
    user = session.query(User).filter(User.username == 'admin').first()
    if not user:
        print("User admin not found")
        exit()
    
    print(f"User: {user.username} (ID: {user.id})")
    
    # Check explicitly assigned roles
    user_roles = session.query(UserRole).filter(UserRole.user_id == user.id).all()
    print("User Roles in DB:")
    for ur in user_roles:
        role = session.get(Role, ur.role_id)
        if role:
            print(f" - Role ID {ur.role_id}: {role.name}")
    
    # Check default role
    if user.default_role_id:
        def_role = session.get(Role, user.default_role_id)
        print(f"Default Role: {def_role.name if def_role else 'None'}")

    # Check validation function
    print(f"user_has_role(..., role_name='PRODUCCION') -> {user_has_role(session, user_id=user.id, role_name='PRODUCCION')}")
    print(f"user_has_role(..., role_name='produccion') -> {user_has_role(session, user_id=user.id, role_name='produccion')}")
    print(f"user_has_role(..., role_name='ADMINISTRADOR') -> {user_has_role(session, user_id=user.id, role_name='ADMINISTRADOR')}")
    print(f"user_has_role(..., role_name='admin') -> {user_has_role(session, user_id=user.id, role_name='admin')}")

    # Check orders
    orders = session.query(Order).all()
    print(f"Total Orders in DB: {len(orders)}")
    for o in orders:
        print(f" - Order {o.order_number}: Status='{o.status}'")

    # Check logic function
    pending = get_pending_orders_for_user(session, user.id)
    print(f"get_pending_orders_for_user returned {len(pending)} orders.")
