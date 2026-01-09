from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from .models import User
from .repository import user_has_role


def is_admin_user(session_factory: sessionmaker, username: str | None) -> bool:
    """Retorna True si el usuario tiene el rol ADMIN.

    Regla del negocio solicitada: solo ADMIN puede ver Editar/Eliminar.
    """
    if not username:
        return False

    try:
        with session_factory() as session:
            user = session.query(User).filter(User.username == username).first()
            if not user:
                return False
            return bool(user_has_role(session, user_id=user.id, role_name="ADMIN"))
    except Exception:
        return False
