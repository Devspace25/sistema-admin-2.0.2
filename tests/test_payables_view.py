import pytest
from PySide6.QtWidgets import QApplication
from src.admin_app.ui.payables_view import PayablesView
from src.admin_app.db import make_session_factory, make_engine

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

def test_payables_view_init(qapp):
    engine = make_engine("sqlite:///:memory:") 
    # Must create tables if view tries to load data on init
    from src.admin_app.models import Base
    Base.metadata.create_all(engine)
    
    session_factory = make_session_factory(engine)
    
    view = PayablesView(session_factory)
    assert view is not None
    assert view.tabs.count() == 3
    assert view.tabs.tabText(0) == "Proveedores (Facturas)"
    
    # Check data loading didn't crash
    # (Tables are empty so it should be handling 0 rows fine)
    assert view.suppliers_tab.table.rowCount() == 0
    assert view.delivery_tab.table.rowCount() == 0

