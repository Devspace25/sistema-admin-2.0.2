from .app import MainWindow, create_qt_app
from .ui.login_dialog import LoginDialog
from .db import make_engine, make_session_factory


def main() -> None:
    app = create_qt_app()
    # Mostrar login
    # Construir una session_factory mínima para autenticación previa
    try:
        engine = make_engine()
        from .repository import init_db
        init_db(engine, seed=True)
        s_factory = make_session_factory(engine)
    except Exception:
        s_factory = None
    login = LoginDialog(session_factory=s_factory)
    if login.exec() == 0:  # Cancelado o inválido repetido
        return
    # Credenciales válidas
    user, _ = login.get_credentials()
    window = MainWindow(current_user=user)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
