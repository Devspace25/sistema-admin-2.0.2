import os
import sys
import pytest
from PySide6.QtWidgets import QApplication
from src.admin_app.db import make_engine, make_session_factory
from src.admin_app.ui.sale_dialog import SaleDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app

@pytest.fixture
def session_factory():
    engine = make_engine()
    Session = make_session_factory(engine)
    return Session

def test_description_field_visibility(qapp, session_factory):
    dlg = SaleDialog(session_factory=session_factory)
    dlg.show()
    assert dlg.edt_descripcion.isVisible(), "edt_descripcion should be visible"
