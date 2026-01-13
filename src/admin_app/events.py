from PySide6.QtCore import QObject, Signal


class _AppEvents(QObject):
    order_created = Signal(int)  # order_id
    sale_updated = Signal()      # Signal to refresh sales lists

events = _AppEvents()
