from PySide6.QtCore import QObject, QTimer, Signal
import os
import logging
import time
from pathlib import Path

class DbWatcher(QObject):
    """
    Monitorea cambios en el archivo de base de datos para notificar a la UI.
    """
    db_updated = Signal()
    
    def __init__(self, db_path: str, interval: int = 2000, parent=None):
        super().__init__(parent)
        self.db_path = Path(db_path)
        self.interval = interval
        self._last_mtime = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_update)
        
        # Init state
        if self.db_path.exists():
            self._last_mtime = self.db_path.stat().st_mtime

    def start(self):
        self._timer.start(self.interval)
        
    def stop(self):
        self._timer.stop()

    def _check_update(self):
        if not self.db_path.exists():
            return

        try:
            current_mtime = self.db_path.stat().st_mtime
            if current_mtime > self._last_mtime:
                # Detectado cambio real
                self._last_mtime = current_mtime
                self.db_updated.emit()
        except OSError:
            pass
