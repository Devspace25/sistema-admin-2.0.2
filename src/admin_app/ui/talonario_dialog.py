"""Diálogo de configuración de Talonarios.

Permite seleccionar Producto, Tipo de Talonario e Impresión,
cargando dinámicamente las columnas relacionadas al producto seleccionado.
"""

from __future__ import annotations
from typing import Optional
import json

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QPushButton, QGroupBox, QLineEdit,
    QDialogButtonBox, QMessageBox, QWidget, QCheckBox
)
from PySide6.QtCore import Qt
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func

from ..models import (
    Product, TipoTalonario, Impresion, 
    ConfigurableProduct, ProductParameterTable, ProductParameterValue
)
from .. import repository as _repo


class TalonarioDialog(QDialog):
    """Diálogo para configurar talonarios según el diseño solicitado."""

    def __init__(
        self,
        session_factory: sessionmaker,
        parent: Optional[QWidget] = None,
        *,
        initial_data: dict | None = None
    ):
        super().__init__(parent)
        self.session_factory = session_factory
        self.initial_data = initial_data or {}
        
        # Payload aceptado
        self.accepted_data: dict | None = None
        
        # Datos cargados
        self._productos: dict[int, Product] = {}
        
        # Mapeo de tablas de parámetros
        self._param_tables: dict[str, int] = {} # nombre -> table_id
        self._param_values: dict[int, list[dict]] = {} # table_id -> lista de valores
        
        # Cache de precios: (id_papel, id_tamano) -> { cantidad_int: precio_float }
        self._pricing_matrix: dict[tuple[int, int], dict[int, float]] = {}
        
        # ID del producto configurable "talonario"
        self._talonario_config_id: int | None = None
        
        self.setWindowTitle("Configurar Talonario")
        self.setMinimumSize(500, 600)
        
        self._build_ui()
        self._load_data()
        self._setup_signals()
        
        if self.initial_data:
            self._load_initial_values()
            
        # Calcular totales iniciales
        self._recalc_total()
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Grupo Principal
        grp_main = QGroupBox("Detalles del Talonario")
        form_layout = QFormLayout(grp_main)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form_layout.setSpacing(12)
        
        # 1. Descripción
        self.edt_descripcion = QLineEdit()
        self.edt_descripcion.setPlaceholderText("Descripción del trabajo (ej. Facturas Serie A)")
        form_layout.addRow("Descripción:", self.edt_descripcion)
        
        # 2. Impresión
        self.cbo_impresion = QComboBox()
        form_layout.addRow("Impresión:", self.cbo_impresion)
        
        # 3. Tipo de Talonario
        self.cbo_tipo_talonario = QComboBox()
        form_layout.addRow("Tipo de Talonario:", self.cbo_tipo_talonario)
        
        # 4. Tamaño
        self.cbo_tamano = QComboBox()
        form_layout.addRow("Tamaño:", self.cbo_tamano)
        
        # 5. Tipo de Papel
        self.cbo_papel = QComboBox()
        form_layout.addRow("Tipo de Papel:", self.cbo_papel)
        
        # 6. Cantidad (SpinBox para cantidad libre)
        self.spin_cantidad = QSpinBox()
        self.spin_cantidad.setRange(1, 10000)
        self.spin_cantidad.setValue(1)
        form_layout.addRow("Cantidad:", self.spin_cantidad)
        
        layout.addWidget(grp_main)
        
        # Grupo de Opciones Adicionales
        grp_opts = QGroupBox("Opciones")
        opts_layout = QVBoxLayout(grp_opts)
        
        # 8. Copia Adicional
        self.chk_copia = QCheckBox("Copia adicional (+20%)")
        opts_layout.addWidget(self.chk_copia)
        
        layout.addWidget(grp_opts)
        
        # Grupo de Totales
        grp_totals = QGroupBox("Resumen de Costos")
        totals_layout = QFormLayout(grp_totals)
        totals_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.lbl_precio_unitario = QLabel("$0.00")
        totals_layout.addRow("Precio Unitario:", self.lbl_precio_unitario)
        
        self.lbl_subtotal = QLabel("$0.00")
        totals_layout.addRow("Subtotal:", self.lbl_subtotal)
        
        self.lbl_recargo = QLabel("$0.00")
        totals_layout.addRow("Recargo (Copia):", self.lbl_recargo)
        
        self.lbl_total = QLabel("$0.00")
        self.lbl_total.setStyleSheet("font-size: 18px; font-weight: bold; color: #2ecc71;")
        totals_layout.addRow("TOTAL:", self.lbl_total)
        
        layout.addWidget(grp_totals)
        
        # Botones
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _load_data(self) -> None:
        try:
            with self.session_factory() as session:
                # 1. Buscar ConfigurableProduct "talonario"
                # Intentar buscar exactamente "talonario" primero (ID 12)
                conf_prod = session.query(ConfigurableProduct).filter(
                    ConfigurableProduct.name == "talonario"
                ).first()
                
                # Si no, buscar cualquiera que contenga "talonario" (fallback)
                if not conf_prod:
                    conf_prod = session.query(ConfigurableProduct).filter(
                        func.lower(ConfigurableProduct.name).like("%talonario%")
                    ).first()
                
                if not conf_prod:
                    # Fallback si no existe el producto configurable
                    self._load_fallback_data(session)
                    return
                
                self._talonario_config_id = conf_prod.id
                
                # 2. Cargar Tablas de Parámetros
                tables = session.query(ProductParameterTable).filter_by(product_id=conf_prod.id).all()
                
                for t in tables:
                    name = t.display_name.lower().strip()
                    self._param_tables[name] = t.id
                    
                    # Cargar valores
                    vals = session.query(ProductParameterValue).filter_by(parameter_table_id=t.id).all()
                    parsed_vals = []
                    for v in vals:
                        try:
                            data = json.loads(v.row_data_json)
                            data['_id'] = v.id # Guardar ID interno
                            parsed_vals.append(data)
                        except:
                            pass
                    self._param_values[t.id] = parsed_vals

                # 3. Poblar Combos
                self._populate_combo(self.cbo_impresion, "impresion", "impresion") 
                self._populate_combo(self.cbo_tipo_talonario, "tipo de talonario", "tipo de talonario")
                self._populate_combo(self.cbo_tamano, "tamaño", "tamaño")
                self._populate_combo(self.cbo_papel, "tipo de papel", "tipo de papel")
                
                # 4. Construir Matriz de Precios
                self._build_pricing_matrix()
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al cargar datos: {e}")

    def _build_pricing_matrix(self) -> None:
        """Construye un mapa de precios optimizado para búsquedas rápidas."""
        # 1. Encontrar IDs de tablas relevantes
        tid_precio = self._param_tables.get("talonario") # Nombre de la tabla de precios
        tid_cantidad = self._param_tables.get("cantidad")
        
        if not tid_precio or not tid_cantidad:
            return

        # 2. Crear mapa de ID Cantidad -> Valor Entero
        qty_map = {}
        for row in self._param_values.get(tid_cantidad, []):
            try:
                qty_val = int(row.get('cantidad', 0))
                qty_id = row.get('_id')
                if qty_id:
                    qty_map[qty_id] = qty_val
            except:
                pass
                
        # 3. Procesar tabla de precios
        # Estructura esperada: id_cantidad, id_tipo_de_papel, id_tamaño, precio
        for row in self._param_values.get(tid_precio, []):
            try:
                r_qty_id = int(row.get('id_cantidad', 0))
                r_papel_id = int(row.get('id_tipo_de_papel', 0))
                
                # Manejar posible variación en nombre de columna tamaño
                r_tamano_id = row.get('id_tamaño')
                if r_tamano_id is None:
                    for k, v in row.items():
                        if 'tamano' in k or 'tamaño' in k:
                            r_tamano_id = v
                            break
                r_tamano_id = int(r_tamano_id) if r_tamano_id else 0
                
                precio = float(row.get('precio', 0.0))
                
                qty_val = qty_map.get(r_qty_id)
                
                if qty_val and r_papel_id and r_tamano_id:
                    key = (r_papel_id, r_tamano_id)
                    if key not in self._pricing_matrix:
                        self._pricing_matrix[key] = {}
                    self._pricing_matrix[key][qty_val] = precio
            except Exception:
                continue

    def _populate_combo(self, combo: QComboBox, table_name_part: str, json_key_part: str) -> None:
        """Helper para poblar combos buscando tablas y claves de forma flexible."""
        combo.clear()
        combo.addItem("-- Seleccionar --", None)
        
        # Buscar ID de tabla
        table_id = None
        for name, tid in self._param_tables.items():
            if table_name_part in name:
                table_id = tid
                break
        
        if not table_id:
            return
            
        values = self._param_values.get(table_id, [])
        for v in values:
            # Buscar la clave que contenga el texto esperado (ej. "tamaño" en "tamaño")
            # O simplemente tomar el primer valor string si no se encuentra
            label = "Desconocido"
            
            # Intento 1: Clave exacta o parcial
            found_key = None
            for k in v.keys():
                if k == '_id': continue
                if json_key_part in k.lower():
                    found_key = k
                    break
            
            if found_key:
                label = str(v[found_key])
            else:
                # Intento 2: Primer valor string
                for k, val in v.items():
                    if k != '_id' and isinstance(val, str):
                        label = val
                        break
                # Intento 3: Primer valor cualquiera
                if label == "Desconocido":
                     for k, val in v.items():
                        if k != '_id':
                            label = str(val)
                            break
            
            combo.addItem(label, v['_id'])

    def _load_fallback_data(self, session):
        """Carga datos legacy si no se encuentra la configuración dinámica."""
        # Tipos de Talonario
        tipos = session.query(TipoTalonario).filter_by(is_active=True).all()
        for t in tipos:
            self.cbo_tipo_talonario.addItem(f"{t.nombre} (${t.precio_base:.2f})", t.id)
        
        # Impresiones
        impresiones = session.query(Impresion).filter_by(is_active=True).all()
        for imp in impresiones:
            costo = f"+${imp.costo_adicional:.2f}" if imp.costo_adicional > 0 else ""
            self.cbo_impresion.addItem(f"{imp.nombre} {costo}", imp.id)
            
        # Hardcoded fallbacks
        self.cbo_tamano.addItems(["Carta", "Media Carta", "Oficio"])
        self.cbo_papel.addItems(["Bond", "Químico"])
        # self.cbo_cantidad.addItem("1", 1) # Eliminado

    def _setup_signals(self) -> None:
        self.cbo_tipo_talonario.currentIndexChanged.connect(self._recalc_total)
        self.cbo_impresion.currentIndexChanged.connect(self._recalc_total)
        self.cbo_tamano.currentIndexChanged.connect(self._recalc_total)
        self.cbo_papel.currentIndexChanged.connect(self._recalc_total)
        self.spin_cantidad.valueChanged.connect(self._recalc_total)
        self.chk_copia.toggled.connect(self._recalc_total)

    def _recalc_total(self) -> None:
        # Obtener IDs seleccionados
        id_papel = self.cbo_papel.currentData()
        id_tamano = self.cbo_tamano.currentData()
        cantidad_input = self.spin_cantidad.value()
        
        subtotal = 0.0
        
        # Lógica de precios escalonada / greedy
        if id_papel and id_tamano and cantidad_input > 0:
            # Obtener mapa de precios para esta combinación (Papel, Tamaño)
            # key = (id_papel, id_tamano)
            # value = { 1: 20.0, 5: 70.0, 10: 120.0 }
            precios_qty = self._pricing_matrix.get((int(id_papel), int(id_tamano)), {})
            
            if precios_qty:
                # Ordenar cantidades disponibles de mayor a menor (ej. 10, 5, 1)
                cantidades_disponibles = sorted(precios_qty.keys(), reverse=True)
                
                remanente = cantidad_input
                costo_acumulado = 0.0
                
                for q_break in cantidades_disponibles:
                    if remanente <= 0:
                        break
                    
                    if remanente >= q_break:
                        num_paquetes = remanente // q_break
                        precio_paquete = precios_qty[q_break]
                        
                        costo_acumulado += num_paquetes * precio_paquete
                        remanente = remanente % q_break
                
                # Si queda remanente y no hay unidad 1 definida, 
                # podríamos cobrar el remanente al precio de la unidad más pequeña disponible 
                # o asumir precio unitario proporcional.
                # Por ahora, asumimos que existe la unidad 1 o similar en la base de datos.
                # Si queda remanente, significa que no se pudo cubrir con los breaks disponibles.
                if remanente > 0:
                    # Fallback: buscar el precio más bajo unitario disponible
                    min_q = cantidades_disponibles[-1] # El más pequeño (ej. 1)
                    precio_min = precios_qty[min_q]
                    # Calcular proporcional si min_q > 1 (aunque idealmente min_q debería ser 1)
                    unitario_fallback = precio_min / min_q
                    costo_acumulado += remanente * unitario_fallback
                
                subtotal = costo_acumulado
        
        # Recargo copia
        recargo = 0.0
        if self.chk_copia.isChecked():
            recargo = subtotal * 0.20
            
        total = subtotal + recargo
        
        # Calcular unitario referencial
        unitario = subtotal / cantidad_input if cantidad_input > 0 else 0
        
        # Actualizar UI
        self.lbl_precio_unitario.setText(f"${unitario:.2f}")
        self.lbl_subtotal.setText(f"${subtotal:.2f}")
        self.lbl_recargo.setText(f"${recargo:.2f}")
        self.lbl_total.setText(f"${total:.2f}")
        
        # Actualizar texto del checkbox con el monto
        self.chk_copia.setText(f"Copia adicional (+20%) - ${recargo:.2f}")

    def _load_initial_values(self) -> None:
        # Cargar detalles JSON si existen
        detalles = self.initial_data.get('detalles', {})
        if 'descripcion' in detalles:
            self.edt_descripcion.setText(detalles['descripcion'])
            
        ids = detalles.get('ids_seleccionados', {})
        
        # Helper para setear combo
        def set_combo(cbo: QComboBox, key_text: str, key_id: str):
            # Intentar por ID primero
            if ids and key_id in ids:
                val = ids[key_id]
                idx = cbo.findData(val)
                if idx >= 0:
                    cbo.setCurrentIndex(idx)
                    return
            # Fallback por texto
            if key_text in detalles:
                txt = detalles[key_text]
                idx = cbo.findText(txt)
                if idx >= 0:
                    cbo.setCurrentIndex(idx)
                else:
                    cbo.setCurrentText(txt)

        set_combo(self.cbo_impresion, 'impresion', 'impresion')
        set_combo(self.cbo_tipo_talonario, 'tipo_talonario', 'tipo')
        set_combo(self.cbo_tamano, 'tamano', 'tamano')
        set_combo(self.cbo_papel, 'papel', 'papel')

        if 'cantidad' in detalles:
            try:
                self.spin_cantidad.setValue(int(detalles['cantidad']))
            except:
                pass
            
        if 'copia_adicional' in detalles:
            self.chk_copia.setChecked(detalles['copia_adicional'])

    def accept(self) -> None:
        # Validaciones
        if not self.cbo_tipo_talonario.currentData():
            QMessageBox.warning(self, "Error", "Seleccione un tipo de talonario.")
            return
            
        # Recalcular final para asegurar consistencia
        self._recalc_total()
        
        # Extraer valores
        cantidad_val = self.spin_cantidad.value()
            
        total_str = self.lbl_total.text().replace('$', '')
        try:
            total = float(total_str)
        except:
            total = 0.0
            
        # Construir resultado
        self.accepted_data = {
            'product_id': None, # No hay producto seleccionado explícitamente
            'product_name': "Talonario",
            'cantidad': cantidad_val,
            'precio_total': total,
            'detalles': {
                'descripcion': self.edt_descripcion.text(),
                'tamano': self.cbo_tamano.currentText(),
                'papel': self.cbo_papel.currentText(),
                'impresion': self.cbo_impresion.currentText(),
                'tipo_talonario': self.cbo_tipo_talonario.currentText(),
                'cantidad': cantidad_val,
                'copia_adicional': self.chk_copia.isChecked(),
                'ids_seleccionados': {
                    'papel': self.cbo_papel.currentData(),
                    'tamano': self.cbo_tamano.currentData(),
                    'cantidad': None, # Ya no es un ID de combo
                    'impresion': self.cbo_impresion.currentData(),
                    'tipo': self.cbo_tipo_talonario.currentData()
                }
            }
        }
        
        super().accept()

    def get_pricing_summary(self) -> dict:
        if not self.accepted_data:
            return {'total': 0.0}
        return {
            'total': self.accepted_data.get('precio_total', 0.0),
            'cantidad': self.accepted_data.get('cantidad', 1)
        }

    def build_config_summary(self) -> str:
        """Genera un resumen legible de la configuración."""
        if not self.accepted_data:
            return ""
        
        detalles = self.accepted_data.get('detalles', {})
        parts = []
        
        tipo = detalles.get('tipo_talonario')
        if tipo and not tipo.startswith('--'):
            parts.append(tipo)
            
        tamano = detalles.get('tamano')
        if tamano and not tamano.startswith('--'):
            parts.append(tamano)
            
        papel = detalles.get('papel')
        if papel and not papel.startswith('--'):
            parts.append(papel)
            
        impresion = detalles.get('impresion')
        if impresion and not impresion.startswith('--'):
            parts.append(impresion)
            
        cant = detalles.get('cantidad')
        if cant:
            parts.append(f"{cant} unds")
            
        if detalles.get('copia_adicional'):
            parts.append("Con Copia")
            
        desc = detalles.get('descripcion')
        if desc:
            parts.append(f"({desc})")
            
        return " - ".join(parts)
