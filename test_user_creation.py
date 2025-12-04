#!/usr/bin/env python3
"""
Script para probar la creación de usuarios y verificar que se guardan correctamente.
"""

from src.admin_app.db import make_session_factory
from src.admin_app.repository import create_user, get_users_with_roles, list_roles, assign_user_roles

def test_user_creation():
    """Probar la creación de usuarios."""
    factory = make_session_factory()
    
    print("=== ESTADO INICIAL ===")
    with factory() as session:
        users = get_users_with_roles(session)
        print(f"Usuarios actuales: {len(users)}")
        for user in users:
            print(f"  - {user['username']}: {user['full_name']} ({user['roles']})")
        
        print(f"\nRoles disponibles:")
        roles = list_roles(session)
        for role in roles:
            print(f"  - {role.name} (ID: {role.id})")
    
    print("\n=== CREANDO NUEVO USUARIO ===")
    try:
        with factory() as session:
            # Crear un usuario de prueba
            new_user = create_user(
                session,
                username="test_user_" + str(int(__import__('time').time())),
                password="password123",
                full_name="Usuario de Prueba"
            )
            
            # Asignar un rol
            roles = list_roles(session)
            if roles:
                assign_user_roles(session, new_user.id, [roles[0].id])
            
            session.commit()
            print(f"Usuario creado: {new_user.username} con ID: {new_user.id}")
            
    except Exception as e:
        print(f"Error creando usuario: {e}")
        return
    
    print("\n=== ESTADO DESPUÉS DE CREAR ===")
    with factory() as session:
        users = get_users_with_roles(session)
        print(f"Usuarios después de crear: {len(users)}")
        for user in users:
            print(f"  - {user['username']}: {user['full_name']} ({user['roles']})")

if __name__ == "__main__":
    test_user_creation()