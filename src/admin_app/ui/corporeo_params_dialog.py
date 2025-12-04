from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QWidget, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QInputDialog
)

from ..corporeo import (
    ensure_dyn_schema, list_tables, create_table, drop_table,
    list_fields, add_field,
    list_rows, insert_row, delete_row, get_columns, update_row,
)


ALLOWED_TYPES = ["TEXT", "INTEGER", "REAL", "NUMERIC", "BLOB"]


class CorporeoParamsDialog(QDialog):
    """Administra tablas y campos dinámicos del módulo corpóreo."""

    def __init__(self, parent=None, producto_id: Optional[int] = None) -> None:
        super().__init__(parent)
        self.producto_id = producto_id
        self._loading_rows = False
        self._cols: list[str] = []
        self._rows_signal_connected = False
        self.setWindowTitle("Parámetros de Corpóreo")
        self.setSizeGripEnabled(True)
        ensure_dyn_schema()
        self._build_ui()
        self._refresh_tables()
        self._fit_to_screen(target_w=820, target_h=520)

    def _fit_to_screen(self, *, target_w: int, target_h: int) -> None:
        try:
            screen = self.screen() or QGuiApplication.primaryScreen()
            if not screen:
                self.resize(target_w, target_h)
                return
            avail = screen.availableGeometry()
            w = min(target_w, int(avail.width() * 0.85))
            h = min(target_h, int(avail.height() * 0.85))
            self.resize(max(560, w), max(420, h))
        except Exception:
            self.resize(target_w, target_h)

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)

        # Panel izquierdo (tablas)
        left = QVBoxLayout()
        left.addWidget(QLabel("Tablas personalizadas"))
        self.lst_tables = QListWidget(self)
        left.addWidget(self.lst_tables, 1)
        bar_l = QHBoxLayout()
        self.btn_add_table = QPushButton("Nueva tabla…")
        self.btn_del_table = QPushButton("Eliminar tabla")
        self.btn_ref_table = QPushButton("Refrescar")
        bar_l.addWidget(self.btn_add_table)
        bar_l.addWidget(self.btn_del_table)
        bar_l.addStretch(1)
        bar_l.addWidget(self.btn_ref_table)
        left.addLayout(bar_l)

        # Panel derecho (campos + filas del producto)
        right = QVBoxLayout()
        self.lbl_fields_title = QLabel("Campos")
        right.addWidget(self.lbl_fields_title)
        self.tbl_fields = QTableWidget(0, 5, self)
        self.tbl_fields.setHorizontalHeaderLabels(["ID", "Nombre", "Tipo", "NOT NULL", "Default"])
        self.tbl_fields.setSelectionBehavior(self.tbl_fields.SelectionBehavior.SelectRows)
        self.tbl_fields.setEditTriggers(self.tbl_fields.EditTrigger.NoEditTriggers)
        self.tbl_fields.verticalHeader().setVisible(False)
        self.tbl_fields.setAlternatingRowColors(True)
        right.addWidget(self.tbl_fields, 1)
        bar_r = QHBoxLayout()
        self.btn_add_field = QPushButton("Agregar campo…")
        self.btn_ref_fields = QPushButton("Refrescar")
        bar_r.addWidget(self.btn_add_field)
        bar_r.addStretch(1)
        bar_r.addWidget(self.btn_ref_fields)
        right.addLayout(bar_r)
        # Subpanel de filas
        right.addWidget(QLabel("Filas (por producto)"))
        self.tbl_rows = QTableWidget(0, 0, self)
        self.tbl_rows.setSelectionBehavior(self.tbl_rows.SelectionBehavior.SelectRows)
        self.tbl_rows.setEditTriggers(self.tbl_rows.EditTrigger.DoubleClicked | self.tbl_rows.EditTrigger.SelectedClicked)
        self.tbl_rows.verticalHeader().setVisible(False)
        self.tbl_rows.setAlternatingRowColors(True)
        right.addWidget(self.tbl_rows, 1)
        bar_rows = QHBoxLayout()
        self.btn_add_row = QPushButton("Insertar fila…")
        self.btn_del_row = QPushButton("Eliminar fila")
        self.btn_ref_rows = QPushButton("Refrescar filas")
        bar_rows.addWidget(self.btn_add_row)
        bar_rows.addWidget(self.btn_del_row)
        bar_rows.addStretch(1)
        bar_rows.addWidget(self.btn_ref_rows)
        right.addLayout(bar_rows)

        # Empaquetar
        w_left = QWidget(self)
        w_left.setLayout(left)
        w_right = QWidget(self)
        w_right.setLayout(right)
        root.addWidget(w_left, 1)
        root.addWidget(w_right, 2)

        # Wiring
        self.lst_tables.currentItemChanged.connect(self._on_select_table)
        self.btn_add_table.clicked.connect(self._on_add_table)
        self.btn_del_table.clicked.connect(self._on_del_table)
        self.btn_ref_table.clicked.connect(self._refresh_tables)
        self.btn_add_field.clicked.connect(self._on_add_field)
        self.btn_ref_fields.clicked.connect(self._refresh_fields)
        self.btn_add_row.clicked.connect(self._on_add_row)
        self.btn_del_row.clicked.connect(self._on_del_row)
        self.btn_ref_rows.clicked.connect(self._refresh_rows)

    # Utilidades
    def _current_table_id(self) -> Optional[int]:
        item = self.lst_tables.currentItem()
        if not item:
            return None
        tid = item.data(Qt.ItemDataRole.UserRole)
        try:
            return int(tid) if tid is not None else None
        except Exception:
            return None

    # Tablas
    def _refresh_tables(self) -> None:
        self.lst_tables.clear()
        for t in list_tables():
            label = f"{t.display_name}  ({t.slug})"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, t.id)
            self.lst_tables.addItem(it)
        if self.lst_tables.count() > 0:
            self.lst_tables.setCurrentRow(0)
        else:
            self._clear_fields()

    def _on_add_table(self) -> None:
        name, ok = QInputDialog.getText(self, "Nueva tabla", "Nombre visible:")
        if not ok or not name.strip():
            return
        # Slug opcional
        slug, ok2 = QInputDialog.getText(self, "Nueva tabla", "Slug (opcional):")
        if not ok2:
            return
        try:
            t = create_table(name.strip(), slug.strip() or None)
        except Exception as e:
            QMessageBox.warning(self, "Crear tabla", f"No se pudo crear: {e}")
            return
        self._refresh_tables()
        # Seleccionar creada
        for i in range(self.lst_tables.count()):
            it = self.lst_tables.item(i)
            if int(it.data(Qt.ItemDataRole.UserRole)) == t.id:
                self.lst_tables.setCurrentRow(i)
                break

    def _on_del_table(self) -> None:
        tid = self._current_table_id()
        if not tid:
            return
        if QMessageBox.question(self, "Eliminar tabla", "¿Eliminar la tabla seleccionada y sus datos?") != QMessageBox.StandardButton.Yes:
            return
        try:
            drop_table(table_id=tid)
        except Exception as e:
            QMessageBox.warning(self, "Eliminar tabla", f"No se pudo eliminar: {e}")
            return
        self._refresh_tables()

    def _on_select_table(self, _cur: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        self._refresh_fields()

    # Campos
    def _clear_fields(self) -> None:
        self.lbl_fields_title.setText("Campos")
        self.tbl_fields.setRowCount(0)
        self.tbl_rows.setRowCount(0)
        self.tbl_rows.setColumnCount(0)

    def _refresh_fields(self) -> None:
        tid = self._current_table_id()
        if not tid:
            self._clear_fields()
            return
        # Título
        cur_item = self.lst_tables.currentItem()
        self.lbl_fields_title.setText(f"Campos de: {cur_item.text()}")
        fields = list_fields(tid)
        t = self.tbl_fields
        t.setRowCount(len(fields))
        for i, f in enumerate(fields):
            t.setItem(i, 0, QTableWidgetItem(str(f.id)))
            t.setItem(i, 1, QTableWidgetItem(f.name))
            t.setItem(i, 2, QTableWidgetItem(f.type))
            t.setItem(i, 3, QTableWidgetItem("Sí" if f.not_null else "No"))
            t.setItem(i, 4, QTableWidgetItem("" if f.default_value is None else str(f.default_value)))
        t.resizeColumnsToContents()
        self._refresh_rows()

    # Filas (por producto)
    def _refresh_rows(self) -> None:
        tid = self._current_table_id()
        if not tid or not self.producto_id:
            self.tbl_rows.setRowCount(0)
            self.tbl_rows.setColumnCount(0)
            # Nos aseguramos de no dejar la señal marcada como conectada
            self._rows_signal_connected = False
            return
        self._loading_rows = True
        try:
            self._cols = get_columns(tid)
            self.tbl_rows.setColumnCount(len(self._cols))
            self.tbl_rows.setHorizontalHeaderLabels(self._cols)
            data = list_rows(tid, int(self.producto_id))
            self.tbl_rows.setRowCount(len(data))
            for i, row in enumerate(data):
                for j, c in enumerate(self._cols):
                    it = QTableWidgetItem("" if row.get(c) is None else str(row.get(c)))
                    # Bloquear edición en id y producto_id
                    if c in {"id", "producto_id"}:
                        flags = it.flags()
                        flags &= ~Qt.ItemFlag.ItemIsEditable
                        it.setFlags(flags)
                    self.tbl_rows.setItem(i, j, it)
            self.tbl_rows.resizeColumnsToContents()
        finally:
            self._loading_rows = False
        # Conectar cambios (evitar múltiples conexiones)
        if self._rows_signal_connected:
            try:
                self.tbl_rows.itemChanged.disconnect(self._on_cell_changed)
            except Exception:
                pass
            self._rows_signal_connected = False
        self.tbl_rows.itemChanged.connect(self._on_cell_changed)
        self._rows_signal_connected = True

    def _row_selected_id(self) -> Optional[int]:
        r = self.tbl_rows.currentRow()
        if r < 0:
            return None
        id_item = self.tbl_rows.item(r, 0)
        try:
            return int(id_item.text()) if id_item else None
        except Exception:
            return None

    def _on_add_row(self) -> None:
        tid = self._current_table_id()
        if not tid:
            return
        if not self.producto_id:
            QMessageBox.information(self, "Filas", "Seleccione un producto desde la vista de Corpóreos.")
            return
        # Inserta fila con sólo producto_id
        try:
            insert_row(tid, int(self.producto_id), {})
        except Exception as e:
            QMessageBox.warning(self, "Insertar fila", f"No se pudo insertar: {e}")
            return
        self._refresh_rows()

    def _on_del_row(self) -> None:
        tid = self._current_table_id()
        rid = self._row_selected_id()
        if not tid or not rid:
            return
        if QMessageBox.question(self, "Eliminar fila", "¿Eliminar la fila seleccionada?") != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_row(tid, rid)
        except Exception as e:
            QMessageBox.warning(self, "Eliminar fila", f"No se pudo eliminar: {e}")
            return
        self._refresh_rows()

    def _on_cell_changed(self, item: QTableWidgetItem) -> None:
        # Persistir cambios de una celda editada
        if self._loading_rows:
            return
        tid = self._current_table_id()
        if not tid:
            return
        row = item.row()
        col = item.column()
        if col < 0 or col >= len(self._cols):
            return
        header = self._cols[col]
        # Id de la fila (columna 0)
        id_item = self.tbl_rows.item(row, 0)
        if not id_item:
            return
        try:
            rid = int(id_item.text())
        except Exception:
            return
        # Evitar persistir en columnas no editables
        if header in {"id", "producto_id"}:
            return
        val = item.text()
        try:
            update_row(tid, rid, {header: val})
        except Exception as e:
            QMessageBox.warning(self, "Actualizar", f"No se pudo actualizar: {e}")

    def _on_add_field(self) -> None:
        tid = self._current_table_id()
        if not tid:
            QMessageBox.information(self, "Campos", "Seleccione una tabla primero.")
            return
        # Inputs
        name, ok = QInputDialog.getText(self, "Nuevo campo", "Nombre del campo:")
        if not ok or not name.strip():
            return
        typ, ok2 = QInputDialog.getItem(self, "Nuevo campo", "Tipo:", ALLOWED_TYPES, 0, False)
        if not ok2:
            return
        nn_label, ok3 = QInputDialog.getItem(self, "Nuevo campo", "Obligatorio (NOT NULL):", ["No", "Sí"], 0, False)
        if not ok3:
            return
        not_null = (nn_label == "Sí")
        default, ok4 = QInputDialog.getText(self, "Nuevo campo", "Default (opcional):")
        if not ok4:
            return
        default_val = default if default.strip() != "" else None
        try:
            add_field(tid, name.strip(), typ, not_null=not_null, default_value=default_val)
        except Exception as e:
            QMessageBox.warning(self, "Agregar campo", f"No se pudo agregar: {e}")
            return
        self._refresh_fields()
