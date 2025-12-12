from __future__ import annotations

from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QComboBox, QPushButton
)
from PySide6.QtCore import Qt

try:
    from .. import repository as _repo
except Exception:  # pragma: no cover
    _repo = None


class ProductConfigDialog(QDialog):
    # (eliminar duplicado de __init__)
    """Diálogo genérico que construye un formulario dinámico a partir de
    las tablas de parámetros relacionadas a un producto configurable.

    Reglas:
    - Crea un ComboBox por tabla.
    - Si hay relación padre->hijo, el hijo se filtra por la selección del padre.
    - El total se calcula como suma de campos de precio presentes en la fila seleccionada
      (heurística: 'precio', 'precio_unit', 'precio_usd', 'costo', 'monto', 'price').
    - Devuelve un resumen con 'total' y una 'descripcion' concatenando textos elegidos.
    """

    PRICE_KEYS = ('precio', 'precio_unit', 'precio_usd', 'costo', 'monto', 'price')

    def __init__(self, session_factory, *, product_id: int, initial_data: dict | None = None):
        super().__init__()
        self.session_factory = session_factory
        self.product_id = product_id
        self.initial_data = initial_data
        self.setWindowTitle("Configurar Producto")
        self._combos: Dict[int, QComboBox] = {}
        self._selected_data: Dict[int, Dict[str, Any]] = {}
        self._last_config_summary = None
        self._last_config_data = None
        self._build_ui()
        self._load_tables()
        self._wire_logic()
        
        if self.initial_data:
            self._restore_state()

    def _restore_state(self):
        """Restaurar selecciones previas si existen."""
        try:
            selections = self.initial_data.get('selections', {})
            if not selections:
                return
                
            # Iterar sobre los combos y establecer valores
            # Es importante hacerlo en orden para respetar dependencias padre-hijo
            # Primero las tablas raíz (sin padre)
            sorted_tables = []
            visited = set()
            
            def visit(tid):
                if tid in visited: return
                visited.add(tid)
                # Visitar padre primero si existe
                parent_id = self._tables[tid].get('parent_table_id')
                if parent_id and parent_id in self._tables:
                    visit(parent_id)
                sorted_tables.append(tid)
                
            for tid in self._tables:
                visit(tid)
                
            for tid in sorted_tables:
                val_id = selections.get(tid)
                if val_id is None:
                    val_id = selections.get(str(tid))
                
                if val_id is not None:
                    combo = self._combos.get(tid)
                    if combo:
                        # Buscar el índice del item con ese ID
                        idx = combo.findData(val_id)
                        if idx >= 0:
                            combo.setCurrentIndex(idx)
                            # Forzar actualización para cargar hijos
                            # Nota: _on_combo_change no existe como tal, usamos la lambda conectada
                            # Pero la lambda espera (idx).
                            # Podemos llamar manualmente a la logica si es necesario, 
                            # pero al hacer setCurrentIndex, la señal currentIndexChanged se dispara?
                            # Si, a menos que blockSignals(True) este activo.
                            # En __init__ no hemos bloqueado señales.
                            # PERO, las señales estan conectadas en _wire_logic() que se llama ANTES de _restore_state().
                            # Asi que setCurrentIndex disparará la logica.
                            pass
        except Exception as e:
            print(f"Error restaurando estado: {e}")

    # --- UI ---
    def _build_ui(self):
        root = QVBoxLayout(self)

        self.grp_params = QGroupBox("Parámetros", self)
        self.grid = QGridLayout(self.grp_params)
        root.addWidget(self.grp_params)

    # (el formulario ya no incluye 'Campos adicionales' ni 'Notas')

        self.grp_totals = QGroupBox("Totales", self)
        g2 = QGridLayout(self.grp_totals)
        g2.addWidget(QLabel("TOTAL ($):"), 0, 0)
        self.lbl_total = QLabel("0.00")
        g2.addWidget(self.lbl_total, 0, 1)
        root.addWidget(self.grp_totals)

        btns = QHBoxLayout()
        self.btn_save = QPushButton("Guardar")
        self.btn_cancel = QPushButton("Cancelar")
        btns.addStretch(1)
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_cancel)
        root.addLayout(btns)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._on_save)
        # (sin acciones extra)

    # --- Datos ---
    def _load_tables(self):
        if not _repo or not hasattr(_repo, 'get_product_parameter_tables'):
            return
        with self.session_factory() as s:
            tables = _repo.get_product_parameter_tables(s, self.product_id)

        row = 0
        # Crear combos por tabla
        for t in tables:
            label = QLabel(f"{t.get('display_name')}")
            cbo = QComboBox(self)
            cbo.addItem("-- seleccione --", None)
            self._combos[t['id']] = cbo
            self.grid.addWidget(label, row, 0)
            self.grid.addWidget(cbo, row, 1)
            row += 1

        # Poblar raíces y preparar dependencias
        self._tables = {t['id']: t for t in tables}
        self._children_by_parent = {}
        with self.session_factory() as s:
            for t in tables:
                pid = t.get('parent_table_id')
                if pid:
                    self._children_by_parent.setdefault(pid, []).append(t['id'])
                else:
                    # raíz
                    try:
                        for op in _repo.get_parent_table_options(s, t['id']):
                            # Guardar full_data para raíces
                            self._add_option_with_data(self._combos[t['id']], op['id'], op['text'], op.get('full_data') or {})
                    except Exception:
                        pass

        # Conectar dependencias
        for parent_id, child_ids in self._children_by_parent.items():
            parent_cbo = self._combos.get(parent_id)
            if not parent_cbo:
                continue
            for child_id in child_ids:
                child_cbo = self._combos.get(child_id)
                if not child_cbo:
                    continue

                def on_parent_change(idx, *, _pid=parent_id, _cid=child_id, _pcbo=parent_cbo, _ccbo=child_cbo):
                    sel = _pcbo.currentData()
                    _ccbo.blockSignals(True)
                    _ccbo.clear(); _ccbo.addItem("-- seleccione --", None)
                    if isinstance(sel, int) and _repo and hasattr(_repo, 'get_filtered_data_by_parent'):
                        with self.session_factory() as s2:
                            tinfo = self._tables.get(_cid)
                            rel_col = (tinfo.get('relationship_column') or 'parent_id') if tinfo else 'parent_id'
                            rows = _repo.get_filtered_data_by_parent(s2, _cid, _pid, rel_col, sel)
                            for r in rows:
                                data = r.get('data', {})
                                text = self._best_label(data)
                                self._add_option_with_data(_ccbo, r.get('id'), text, data)
                    _ccbo.blockSignals(False)
                    self._recalc()

                parent_cbo.currentIndexChanged.connect(on_parent_change)

    def _add_option_with_data(self, combo: QComboBox, row_id: Optional[int], text: str, data: Dict[str, Any]):
        combo.addItem(text, row_id)
        # Guardamos el dict data como propiedad Qt accessible por índice
        idx = combo.count() - 1
        combo.setItemData(idx, data, role=Qt.ItemDataRole.UserRole + 1)  # type: ignore

    def _best_label(self, data: Dict[str, Any]) -> str:
        if 'nombre' in data and str(data['nombre']).strip():
            return str(data['nombre'])
        for k, v in data.items():
            if k != 'id' and str(v).strip():
                return str(v)
        return "Registro"

    # --- Lógica ---
    def _wire_logic(self):
        for table_id, cbo in self._combos.items():
            def on_changed(idx, *, _tid=table_id, _cbo=cbo):
                # Guardar data seleccionada
                data = _cbo.itemData(idx, role=Qt.ItemDataRole.UserRole + 1)  # type: ignore
                if isinstance(data, dict):
                    self._selected_data[_tid] = data
                else:
                    self._selected_data.pop(_tid, None)
                self._recalc()
            cbo.currentIndexChanged.connect(on_changed)

    def _recalc(self):
        total = 0.0
        try:
            for data in self._selected_data.values():
                # Sumar heurísticamente cualquier clave de precio conocida
                for k in self.PRICE_KEYS:
                    if k in data:
                        try:
                            total += float(data[k])
                            break
                        except Exception:
                            continue
        except Exception:
            total = 0.0
        self.lbl_total.setText(f"{total:.2f}")

    # (sin helpers de extras)

    # --- API ---
    def get_pricing_summary(self) -> dict:
        # Descripción: concatenar textos visibles seleccionados
        parts = []
        for tid, cbo in self._combos.items():
            txt = cbo.currentText()
            if txt and not txt.startswith("--"):
                parts.append(txt)
        desc = " | ".join(parts)
        try:
            total = float(self.lbl_total.text())
        except Exception:
            total = 0.0
        return {
            'total': total,
            'descripcion': desc,
        }

    def _on_save(self):
        # Al guardar, generar resumen y config serializable
        summary = self.get_pricing_summary()
        self._last_config_summary = summary.get('descripcion', '')
        self._last_config_data = self.serialize_config()
        self.accept()

    def get_config_summary(self) -> str:
        """Devuelve el resumen legible generado al guardar."""
        return self._last_config_summary or ''

    def get_config_data(self) -> dict:
        """Devuelve la configuración serializada para persistencia/edición."""
        return self._last_config_data or {}

    def serialize_config(self) -> dict:
        """Serializa la selección actual para guardar/reconstruir la configuración."""
        # Por defecto, serializa los ids seleccionados en cada combo
        return {tid: cbo.currentData() for tid, cbo in self._combos.items()}

    def load_config(self, config: dict):
        """Carga una configuración serializada (por ejemplo, al editar una venta)."""
        for tid, val in (config or {}).items():
            cbo = self._combos.get(tid)
            if cbo:
                idx = cbo.findData(val)
                if idx >= 0:
                    cbo.setCurrentIndex(idx)
