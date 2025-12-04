from PySide6.QtCore import QObject, Signal


class _AppEvents(QObject):
    order_created = Signal(int)  # order_id


events = _AppEvents()
