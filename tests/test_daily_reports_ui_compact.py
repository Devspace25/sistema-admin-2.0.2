
import pytest
from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QScrollArea
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.admin_app.models import Base
from src.admin_app.ui.daily_reports_view import DailyReportsView

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)

def test_alerts_section_compact_when_empty(qapp, session_factory):
    view = DailyReportsView(session_factory)
    view.show()
    
    # Check that no_alerts_widget is visible and container is hidden
    assert view.no_alerts_widget.isVisible()
    assert not view.alerts_container.isVisible()
    
    # Check text
    labels = view.no_alerts_widget.findChildren(QLabel)
    found_text = False
    for lbl in labels:
        if "Todo al día" in lbl.text():
            found_text = True
            break
    assert found_text
    
    view.close()
