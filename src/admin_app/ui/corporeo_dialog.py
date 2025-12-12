"""Corporeo configurator dialog (restored, clean).

This file provides a compact but compatible implementation of the
CorporeoDialog widget used by tests and the application. It expects a
`session_factory` (callable) and a `type_id` for EAV-driven option loading.

The dialog exposes the widgets and methods the rest of the codebase and
tests expect (for example: cbo_corte, cbo_material, cbo_espesor, spin_diam,
spin_esp_precio, _recalc, get_pricing_summary,
build_config_summary, btn_ok, btn_cancel, etc.).

The implementation is intentionally defensive: if EAV is not available the
widgets keep sensible defaults and the dialog still functions for calculations.
"""

from typing import Optional, List, Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDoubleSpinBox,
    QComboBox, QPushButton, QCheckBox, QWidget, QGroupBox, QGridLayout,
    QScrollArea, QTextEdit, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt
from .. import repository as _repo
from ..repository import get_system_config
from ..exchange import get_bcv_rate
import logging

# module logger
logger = logging.getLogger(__name__)


class CorporeoDialog(QDialog):
    # forward-declare method so callers in __init__ are recognized by static analyzers
    def _load_tipo_corporeo_from_product(self, product_identifier: int | dict | None) -> None:
        return
    def __init__(self, session_factory, *, type_id: int, product_id: Optional[int] = None, initial_payload: dict | None = None, form_id: int | None = None, user_id: int | None = None):
        # Inicializar la clase base QDialog
        super().__init__()
        logger.info(f"CorporeoDialog.__init__ received: product_id={product_id}")
        logger.debug("CorporeoDialog.__init__ start type_id=%r product_id=%r", type_id, product_id)
        # Guardar referencias a sesión/producto/tipo para uso posterior
        self.session_factory = session_factory
        self.type_id = type_id
        self.product_id = product_id
        self.form_id = form_id
        self.user_id = user_id

        # Últimos valores calculados para reutilizar en payload/resumen
        self._last_precio_final_usd: float = 0.0
        self._last_precio_final_bs: float = 0.0
        self._last_tasa_corporeo: float = 0.0
        self._last_tasa_bcv: float = 0.0

        # Only populate espesor from child tables related to the selected material.
        # No global fallback: if nothing matched, cbo_espesor stays with the default option.

        # Luces: single combobox with types and a QLabel that shows the selected price
        # Keep compatibility widgets (cbo_luz_tipo, spin_luz_precio) and add a visible price label
        self.cbo_luz_tipo: QComboBox = QComboBox()
        self.lbl_luz_price: QLabel = QLabel("")
        # Color/posición de luz manejados por EAV
        self.cbo_luz_color: QComboBox = QComboBox()
        self.cbo_pos_luz: QComboBox = QComboBox()
        # Compatibility widgets expected by legacy loaders: ensure objects exist (avoid None)
        try:
            self.spin_luz_precio: QDoubleSpinBox = QDoubleSpinBox()
            self.spin_luz_precio.setDecimals(2)
            self.spin_luz_precio.setMaximum(1_000_000.0)
        except Exception:
            # If configuration fails, keep a functional object to satisfy static checks
            self.spin_luz_precio = QDoubleSpinBox()
        # Tipo de corte: mantener compatibilidad con tests (cbo_corte)
        self.cbo_corte = QComboBox()
        # además, mostrarlo como conjunto dinámico de checkboxes
        self.cut_buttons_container = QWidget()
        # Usar QGridLayout para permitir wrapping en varias filas (evita scrollbar horizontal)
        from PySide6.QtWidgets import QGridLayout as _QGridLayout
        self.cut_buttons_layout = _QGridLayout(self.cut_buttons_container)
        self.cut_buttons_layout.setContentsMargins(0, 0, 0, 0)
        # número máximo de columnas antes de hacer wrap
        self.cut_buttons_max_cols = 6
        # Lista de QCheckBox que representarán cada tipo de corte (selección múltiple)
        self.cut_checkboxes = []

        
        # Tipo de Corpóreo: contenedor dinámico de checkboxes con label de precio m2
        self.tipo_corp_container = QWidget()
        # use QGridLayout (imported at module level)
        self.tipo_corp_layout = QGridLayout(self.tipo_corp_container)
        self.tipo_corp_layout.setContentsMargins(0, 0, 0, 0)
        # pv_id may be None for some rows
        self.tipo_corp_checkboxes = []  # list of (checkbox, price_label, pv_id)

        # Campo detalle para 'Otros'
        self.txt_corte_otros = QLineEdit()
        self.txt_corte_otros.setPlaceholderText("Especificar")
        self.txt_corte_otros.setEnabled(False)
        # Checkbox 'Otros' (colocado debajo de Detalle más abajo en el layout)
        self.chk_corte_otros = QCheckBox('Otros')
        self.chk_corte_otros.setChecked(False)
        try:
            self.chk_corte_otros.stateChanged.connect(lambda s: self.txt_corte_otros.setEnabled(bool(s)))
        except Exception:
            pass
        # Label para mostrar el precio de silueta (mostrado a la derecha del area de cortes)
        self.lbl_costo_silueta = QLabel("")
        # hide by default; only show when user selects the 'Silueta' checkbox
        try:
            self.lbl_costo_silueta.setVisible(False)
        except Exception:
            pass
        # numeric value for silueta price (per m2) - default 0.0
        self._silueta_price_val = 0.0
        # Conectar cambios de combo con comportamientos de selección (compatibilidad)
        try:
            self.cbo_corte.currentIndexChanged.connect(self._on_cbo_corte_changed)
        except Exception:
            pass

        # Regulador / caja
        self.cbo_reg_amp = QComboBox()
        self.spin_reg_cant = QDoubleSpinBox()
        self.spin_reg_cant.setDecimals(0)
        # label to display price per regulator
        self.lbl_reg_precio = QLabel("")
        self.chk_caja = QCheckBox("Caja de luz")
        self.cbo_caja_base = QComboBox()
        self.cbo_caja_faja = QComboBox()
        self.spin_caja_pct = QDoubleSpinBox()

        # Extras / mods
        self._mods_dynamic = []

        # Buttons
        self.btn_ok = QPushButton("Aceptar")
        self.btn_cancel = QPushButton("Cancelar")
        # storage for accepted payload (used by caller to retrieve values after dialog.accept())
        self.accepted_data = None

        # Widgets usados en _build_ui: inicializarlos aquí para evitar AttributeError
        self.txt_name = QLineEdit()
        self.txt_desc = QTextEdit()

        # Medidas
        self.spin_alto = QDoubleSpinBox()
        self.spin_alto.setRange(0.0, 10000.0)
        self.spin_alto.setDecimals(2)
        try:
            # avoid committing value on every keystroke (improves ability to clear/replace text)
            self.spin_alto.setKeyboardTracking(False)
            le = self.spin_alto.lineEdit()
            if le is not None:
                try:
                    le.setClearButtonEnabled(True)
                except Exception:
                    pass
        except Exception:
            pass
        self.spin_ancho = QDoubleSpinBox()
        self.spin_ancho.setRange(0.0, 10000.0)
        self.spin_ancho.setDecimals(2)
        try:
            self.spin_ancho.setKeyboardTracking(False)
            le = self.spin_ancho.lineEdit()
            if le is not None:
                try:
                    le.setClearButtonEnabled(True)
                except Exception:
                    pass
        except Exception:
            pass
        self.spin_diam = QDoubleSpinBox()
        self.spin_diam.setRange(0.0, 100000.0)
        self.spin_diam.setDecimals(2)
        try:
            self.spin_diam.setKeyboardTracking(False)
            le = self.spin_diam.lineEdit()
            if le is not None:
                try:
                    le.setClearButtonEnabled(True)
                except Exception:
                    pass
        except Exception:
            pass
        self.lbl_area_section = QLabel("")

        # Material / espesor
        self.cbo_material = QComboBox()
        self.cbo_espesor = QComboBox()
        # compatibility: allow tests to set a spin for espesor price
        try:
            self.spin_esp_precio = QDoubleSpinBox()
            self.spin_esp_precio.setDecimals(2)
            self.spin_esp_precio.setMaximum(1_000_000.0)
        except Exception:
            self.spin_esp_precio = None
        # precio del espesor mostrado como label (no editable)
        self.lbl_esp_precio = QLabel("")
        # Allow larger prices (default QDoubleSpinBox max is often 99.99)
        try:
            # connect espesor change handler early so it's always wired
            self.cbo_espesor.currentIndexChanged.connect(self._on_espesor_changed)
        except Exception:
            pass

        # Base / color
        self.txt_base_color = QLineEdit()
        self.txt_base_color_cod = QLineEdit()
        self.chk_base_crudo = QCheckBox("Crudo")
        self.chk_base_transp = QCheckBox("Transparente")

        # Soportes
        self.cbo_soporte_item = QComboBox()
        self.cbo_soporte_size = QComboBox()
        self.spin_soporte_qty = QDoubleSpinBox()
        self.spin_soporte_qty.setDecimals(0)
        self.lbl_soporte_precio = QLabel("")

        # Totals labels
        self.lbl_area = QLabel("0.0000")
        self.lbl_subtotal = QLabel("0.00")
        self.lbl_total = QLabel("0.00")
        self.lbl_precio_final_corporeo_usd = QLabel("0.00")  # Precio final USD con tasa corpóreo
        self.lbl_perim = QLabel("0.0000")
        # Breakdown subtotals (initialized)
        self.lbl_sub_base = QLabel("0.00")
        self.lbl_sub_tipo_corp = QLabel("0.00")
        self.lbl_sub_silueta = QLabel("0.00")
        self.lbl_sub_bases = QLabel("0.00")
        self.lbl_sub_luces = QLabel("0.00")
        self.lbl_sub_regulador = QLabel("0.00")
        self.lbl_sub_caja_pct = QLabel("0.00")

        # finalize init: build UI and wire signals
        self._build_ui()
        self._wire_signals()
        
        # If a product_id was given, load product-specific parameter tables FIRST
        # (estos tienen prioridad sobre los datos del EAV)
        try:
            if self.product_id:
                logger.info(f"Loading product-specific parameters for product_id={self.product_id}")
                self._load_cut_types_from_product(self.product_id)
                self._load_materials_from_product(self.product_id)
                self._load_tipo_corporeo_from_product(self.product_id)
                self._load_bases_separadores_from_product(self.product_id)
                self._load_luces_from_product(self.product_id)
                self._load_regulador_from_product(self.product_id)
            else:
                logger.warning("No product_id provided, attempting to infer from initial_payload or using global parameter loading.")
                # Intentar inferir product_id del payload inicial
                inferred_pid = None
                if initial_payload and isinstance(initial_payload, dict):
                    inferred_pid = initial_payload.get('product_id')
                    if not inferred_pid:
                        meta = initial_payload.get('meta') if isinstance(initial_payload.get('meta'), dict) else {}
                        inferred_pid = meta.get('product_id') if meta else None
                
                if inferred_pid:
                    try:
                        inferred_pid = int(inferred_pid)
                        logger.info(f"Inferred product_id={inferred_pid} from payload, loading parameters...")
                        self._load_cut_types_from_product(inferred_pid)
                        self._load_materials_from_product(inferred_pid)
                        self._load_tipo_corporeo_from_product(inferred_pid)
                        self._load_bases_separadores_from_product(inferred_pid)
                        self._load_luces_from_product(inferred_pid)
                        self._load_regulador_from_product(inferred_pid)
                    except Exception as e:
                        logger.error(f"Failed to load parameters with inferred product_id: {e}")
                        self._load_tipo_corporeo_from_product(None)
                else:
                    logger.warning("Could not infer product_id, loading global parameters.")
                    self._load_tipo_corporeo_from_product(None)
        except Exception as e:
            logger.error(f"Failed to load product parameters: {e}", exc_info=True)
        
        # Cargar opciones del EAV solo si no hay product_id 
        # (las tablas de parámetros tienen prioridad)
        if not self.product_id:
            try:
                logger.info("No product_id, loading from EAV as fallback")
                self._load_from_eav()
            except Exception as e:
                logger.error(f"Failed to load from EAV: {e}", exc_info=True)
        
        # Si se pasa form_id, cargar el payload guardado automáticamente
        try:
            if self.form_id is not None:
                from ..repository import load_corporeo_form
                sf = self.session_factory
                with sf() as session:
                    payload = load_corporeo_form(session, self.form_id)
                    if payload:
                        self._load_initial_payload(payload)
            elif initial_payload:
                self._load_initial_payload(initial_payload)
        except Exception:
            logger.exception("failed to load corporeo form payload")
        logger.debug("CorporeoDialog.__init__ finished")

    def _build_ui(self) -> None:
        """Construye la interfaz del diálogo de Corporeo (compacta y coherente)."""
        root = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QWidget(self)
        scroll.setWidget(container)
        root.addWidget(scroll)

        body = QVBoxLayout(container)
        body.setContentsMargins(6, 6, 6, 6)
        body.setSpacing(8)

        # Section 1 - Información
        g1 = QGroupBox("1 Información")
        g1l = QGridLayout(g1)
        g1l.addWidget(QLabel("Nombre:"), 0, 0)
        g1l.addWidget(self.txt_name, 0, 1)
        g1l.addWidget(QLabel("Descripción:"), 1, 0)
        g1l.addWidget(self.txt_desc, 1, 1)
        body.addWidget(g1)

        # Section 2 - Tipos de Corte
        g2 = QGroupBox("2 Tipos de Corte")
        g2l = QGridLayout(g2)
        cut_scroll = QScrollArea()
        cut_scroll.setWidgetResizable(True)
        cut_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cut_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        cut_scroll.setWidget(self.cut_buttons_container)
        cut_scroll.setFixedHeight(72)
        g2l.addWidget(cut_scroll, 0, 0, 1, 6)
        # Otros
        g2l.addWidget(self.chk_corte_otros, 1, 0)
        g2l.addWidget(QLabel("Detalle Otros:"), 1, 1)
        g2l.addWidget(self.txt_corte_otros, 1, 2, 1, 4)
        body.addWidget(g2)

        # Section 3 - Medidas
        g3 = QGroupBox("3 Medidas")
        g3l = QGridLayout(g3)
        g3l.addWidget(QLabel("Alto (cm):"), 0, 0)
        g3l.addWidget(self.spin_alto, 0, 1)
        g3l.addWidget(QLabel("Ancho (cm):"), 0, 2)
        g3l.addWidget(self.spin_ancho, 0, 3)
        g3l.addWidget(QLabel("Área:"), 1, 0)
        g3l.addWidget(self.lbl_area_section, 1, 1)
    # Diámetro removed: not shown in UI
        body.addWidget(g3)

        # Section 4 - Base / Material
        g4 = QGroupBox("4 Base / Material")
        g4l = QGridLayout(g4)
        g4l.addWidget(QLabel("Material:"), 0, 0)
        g4l.addWidget(self.cbo_material, 0, 1)
        g4l.addWidget(QLabel("Espesor:"), 0, 2)
        g4l.addWidget(self.cbo_espesor, 0, 3)
        g4l.addWidget(QLabel("Precio m²:"), 1, 0)
        g4l.addWidget(self.lbl_esp_precio, 1, 1)
        color_row = QWidget()
        color_row_l = QHBoxLayout(color_row)
        color_row_l.setContentsMargins(0, 0, 0, 0)
        color_row_l.addWidget(self.txt_base_color)
        try:
            from PySide6.QtWidgets import QLabel as _QLabel
            # Place the COD. label before the code field
            color_row_l.addWidget(_QLabel("COD."))
        except Exception:
            pass
        color_row_l.addWidget(self.txt_base_color_cod)
        color_row_l.addWidget(self.chk_base_crudo)
        color_row_l.addWidget(self.chk_base_transp)
        g4l.addWidget(QLabel("Color:"), 2, 0)
        g4l.addWidget(color_row, 2, 1, 1, 3)
        # Tipo de Corporeo placed under Color
        g4l.addWidget(QLabel("Tipo de Corporeo:"), 3, 0)
        g4l.addWidget(self.tipo_corp_container, 3, 1, 1, 3)
        body.addWidget(g4)

        # Section 5 - Soportes
        g5 = QGroupBox("5 Bases / Separadores")
        g5l = QGridLayout(g5)
        g5l.addWidget(QLabel("Modelo:"), 0, 0)
        g5l.addWidget(self.cbo_soporte_item, 0, 1)
        g5l.addWidget(QLabel("Tamaño:"), 0, 2)
        g5l.addWidget(self.cbo_soporte_size, 0, 3)
        g5l.addWidget(QLabel("Cantidad:"), 1, 0)
        g5l.addWidget(self.spin_soporte_qty, 1, 1)
        g5l.addWidget(QLabel("Precio soporte:"), 1, 2)
        g5l.addWidget(self.lbl_soporte_precio, 1, 3)
        body.addWidget(g5)

        # Section 6 - Luces (clean layout: checkboxes + price labels)
        g6 = QGroupBox("6 Luces")
        g6l = QGridLayout(g6)
        try:
            g6l.setHorizontalSpacing(8)
            g6l.setVerticalSpacing(6)
        except Exception:
            pass

        # Row 0: single combo for light type and a label showing selected price
        g6l.addWidget(QLabel("Tipo de luz:"), 0, 0)
        g6l.addWidget(self.cbo_luz_tipo, 0, 1)
        # static label for price
        g6l.addWidget(QLabel("Precio:"), 0, 2)
        g6l.addWidget(self.lbl_luz_price, 0, 3)

        # minor layout tuning
        try:
            for lbl in (self.lbl_luz_price, self.lbl_reg_precio, self.lbl_soporte_precio):
                # Use AlignmentFlag for explicit attributes
                lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        except Exception:
            pass
        try:
            g6l.setColumnStretch(5, 1)
        except Exception:
            pass

        # Controls: tipo, precio unitario, color, posición
    # Tipo de luz removed from UI (we keep color/position combos)
        g6l.addWidget(QLabel("Color de luz:"), 3, 0)
        g6l.addWidget(self.cbo_luz_color, 3, 1)
        g6l.addWidget(QLabel("Posición luz:"), 3, 2)
        g6l.addWidget(self.cbo_pos_luz, 3, 3)

        # Ensure cbo_pos_luz has default options so restoration can select values even
        # when EAV/product tables didn't populate them yet.
        try:
            if self.cbo_pos_luz.count() <= 0:
                self.cbo_pos_luz.addItem('-- seleccione --', None)
                for d in ('Borde Frente', 'Borde Detras', 'Retroiluminado Frente', 'Retroiluminado Detras'):
                    try:
                        self.cbo_pos_luz.addItem(d, None)
                    except Exception:
                        pass
        except Exception:
            pass

        # Regulador moved into Sección 6 (Regulador y Cantidad pertenecen a Luces)
        g6l.addWidget(QLabel("Regulador (Amp):"), 4, 0)
        g6l.addWidget(self.cbo_reg_amp, 4, 1)
        g6l.addWidget(QLabel("Precio reg:"), 4, 2)
        g6l.addWidget(self.lbl_reg_precio, 4, 3)
        g6l.addWidget(QLabel("Cant. Regulador:"), 5, 0)
        g6l.addWidget(self.spin_reg_cant, 5, 1)
        body.addWidget(g6)

        # Section 7 - Caja (sin regulador: regulador ahora está en Sección 6)
        g7 = QGroupBox("7 Caja de Luz")
        g7l = QGridLayout(g7)
        g7l.addWidget(self.chk_caja, 0, 0)
        g7l.addWidget(QLabel("Base caja:"), 0, 1)
        g7l.addWidget(self.cbo_caja_base, 0, 2)
        # default options for caja base
        try:
            self.cbo_caja_base.clear()
            self.cbo_caja_base.addItem('-- seleccione --', None)
            self.cbo_caja_base.addItem('MDF', '1_mdf')
        except Exception:
            pass
        g7l.addWidget(QLabel("Faja:"), 0, 3)
        g7l.addWidget(self.cbo_caja_faja, 0, 4)
        # default options for faja
        try:
            self.cbo_caja_faja.clear()
            self.cbo_caja_faja.addItem('-- seleccione --', None)
            self.cbo_caja_faja.addItem('5cm', '1_5cm')
            self.cbo_caja_faja.addItem('7cm', '2_7cm')
        except Exception:
            pass
        g7l.addWidget(QLabel("% Extra Caja"), 1, 0)
        g7l.addWidget(self.spin_caja_pct, 1, 1)
        body.addWidget(g7)

        # Initially disable caja controls until checkbox is checked
        try:
            self._update_caja_controls_enabled()
        except Exception:
            pass

        # Totals
        gT = QGroupBox("Totales")
        gTl = QGridLayout(gT)
        gTl.addWidget(QLabel("Área (m²):"), 0, 0)
        gTl.addWidget(self.lbl_area, 0, 1)
        # Breakdown rows
        gTl.addWidget(QLabel("Subtotal Base:"), 1, 0)
        gTl.addWidget(self.lbl_sub_base, 1, 1)
        gTl.addWidget(QLabel("Subtotal Tipos Corporeo:"), 2, 0)
        gTl.addWidget(self.lbl_sub_tipo_corp, 2, 1)
        gTl.addWidget(QLabel("Subtotal Silueta:"), 3, 0)
        gTl.addWidget(self.lbl_sub_silueta, 3, 1)
        gTl.addWidget(QLabel("Subtotal Bases:"), 4, 0)
        gTl.addWidget(self.lbl_sub_bases, 4, 1)
        gTl.addWidget(QLabel("Subtotal Luces:"), 5, 0)
        gTl.addWidget(self.lbl_sub_luces, 5, 1)
        gTl.addWidget(QLabel("Subtotal Regulador:"), 6, 0)
        gTl.addWidget(self.lbl_sub_regulador, 6, 1)
        gTl.addWidget(QLabel("Subtotal % Caja:"), 7, 0)
        gTl.addWidget(self.lbl_sub_caja_pct, 7, 1)

        gTl.addWidget(QLabel("Subtotal:"), 8, 0)
        gTl.addWidget(self.lbl_subtotal, 8, 1)
        gTl.addWidget(QLabel("Total:"), 8, 2)
        gTl.addWidget(self.lbl_total, 8, 3)
        gTl.addWidget(QLabel("Precio Final Corpóreo USD:"), 9, 0)
        gTl.addWidget(self.lbl_precio_final_corporeo_usd, 9, 1)
        body.addWidget(gT)

        # Action buttons
        btns = QWidget()
        btns_l = QHBoxLayout(btns)
        btns_l.addStretch(1)
        btns_l.addWidget(self.btn_ok)
        btns_l.addWidget(self.btn_cancel)
        body.addWidget(btns)

    def _set_cut_options_from_list(self, items: list) -> None:
        """Recibe una lista de tuples (label, id) y crea checkboxes en la UI.

        Esta versión es una implementación más compacta y con indentación
        consistente para evitar errores de sintaxis por mezcla de espacios/tabs
        o bloques incompletos.
        """
        import json

        # limpiar botones previos de forma defensiva
        try:
            for cb in list(getattr(self, 'cut_checkboxes', []) or []):
                try:
                    cb.stateChanged.disconnect()
                except Exception:
                    pass
                try:
                    self.cut_buttons_layout.removeWidget(cb)
                    cb.deleteLater()
                except Exception:
                    pass
            self.cut_checkboxes = []
        except Exception:
            self.cut_checkboxes = []

        # crear nuevos checkboxes
        for idx, it in enumerate(items or []):
            if isinstance(it, (list, tuple)):
                label, oid = it[0], it[1]
            else:
                label, oid = str(it), None

            friendly = '' if label is None else str(label)

            # intentar obtener un label "friendly" desde DB/EAV si tenemos oid
            price_from_pv = None
            if oid is not None:
                try:
                    sf = getattr(self, 'session_factory', None)
                    if sf:
                        with sf() as s:
                            try:
                                from ..models import ProductParameterValue
                                pv = s.get(ProductParameterValue, int(oid))
                            except Exception:
                                pv = None

                            if pv:
                                try:
                                    data = json.loads(pv.row_data_json or '{}')
                                except Exception:
                                    data = {}
                                if isinstance(data, dict):
                                    try:
                                        lower_map = {str(k).lower(): v for k, v in data.items()}
                                        for key in ('precio_silueta', 'precio_m2', 'precio', 'price', 'valor', 'valor_m2'):
                                            if key in lower_map:
                                                raw_val = lower_map.get(key)
                                                if raw_val is None:
                                                    continue
                                                try:
                                                    price_from_pv = float(str(raw_val).replace('$', '').replace(',', '').strip())
                                                    break
                                                except Exception:
                                                    try:
                                                        price_from_pv = float(raw_val)
                                                        break
                                                    except Exception:
                                                        price_from_pv = None
                                    except Exception:
                                        price_from_pv = price_from_pv
                                    if price_from_pv is None:
                                        for key in ('Precio', 'Price', 'Valor'):
                                            if key in data:
                                                try:
                                                    price_from_pv = float(str(data.get(key)).replace('$', '').replace(',', '').strip())
                                                    break
                                                except Exception:
                                                    price_from_pv = None
                                    # prioridad de claves donde puede aparecer el nombre para tipos de corte
                                    for k in ('tipo de corte', 'tipo_de_corte', 'Tipo de Corte', 'Tipo', 'tipo', 'name', 'nombre', 'label', 'display', 'descripcion'):
                                        v = data.get(k)
                                        if isinstance(v, str) and v.strip():
                                            friendly = v.strip()
                                            break
                            # si no encontramos friendly, intentar EavAttributeOption
                            if (not friendly or friendly.strip() == str(oid)):
                                try:
                                    from ..models import EavAttributeOption
                                    opt = s.get(EavAttributeOption, int(oid))
                                    if opt:
                                        friendly = getattr(opt, 'label', None) or getattr(opt, 'code', None) or friendly
                                except Exception:
                                    pass
                except Exception:
                    # ignorar errores de DB
                    pass

            if not friendly:
                friendly = str(oid) if oid is not None else str(label)
            # si aún es numérico, mostrar texto más legible
            if (not friendly) or friendly.strip().isdigit():
                friendly = f"Corte {str(oid or label).strip()}"

            cb = QCheckBox(str(friendly))
            cb.setProperty('opt_id', oid)
            if price_from_pv is not None:
                try:
                    cb.setProperty('price_m2', float(price_from_pv))
                except Exception:
                    cb.setProperty('price_m2', price_from_pv)

            # tooltip: preferir JSON bruto si existe
            try:
                # Build a concise tooltip: prefer showing key fields instead of raw JSON
                tooltip = ''
                sf = getattr(self, 'session_factory', None)
                if sf and oid is not None:
                    try:
                        with sf() as s:
                            from ..models import ProductParameterValue
                            pv = s.get(ProductParameterValue, int(oid))
                            if pv:
                                try:
                                    pdata = json.loads(pv.row_data_json or '{}')
                                except Exception:
                                    pdata = {}
                                if isinstance(pdata, dict):
                                    parts = []
                                    for k in ('Tipo de Corte', 'Tipo', 'tipo', 'label', 'display', 'descripcion', 'name'):
                                        v = pdata.get(k)
                                        if v is None:
                                            continue
                                        # keep short values only
                                        try:
                                            sv = str(v)
                                        except Exception:
                                            sv = ''
                                        if sv:
                                            parts.append(f"{k}: {sv}")
                                    if price_from_pv is None:
                                        try:
                                            lower_map = {str(k).lower(): val for k, val in pdata.items()}
                                            for key in ('precio_silueta', 'precio_m2', 'precio', 'price', 'valor', 'valor_m2'):
                                                if key in lower_map:
                                                    raw_val = lower_map.get(key)
                                                    if raw_val is None:
                                                        continue
                                                    try:
                                                        price_from_pv = float(str(raw_val).replace('$', '').replace(',', '').strip())
                                                    except Exception:
                                                        price_from_pv = float(raw_val)
                                                    try:
                                                        cb.setProperty('price_m2', float(price_from_pv))
                                                    except Exception:
                                                        cb.setProperty('price_m2', price_from_pv)
                                                    break
                                        except Exception:
                                            pass
                                    if parts:
                                        tooltip = ' | '.join(parts[:3])
                                # fallback minimal: include id
                                if not tooltip:
                                    tooltip = f"id: {getattr(pv,'id', oid)}"
                    except Exception:
                        tooltip = ''
                if not tooltip:
                    tooltip = str(label or '')
                if tooltip:
                    # limit tooltip length to avoid extremely long displays
                    if len(tooltip) > 240:
                        tooltip = tooltip[:237] + '...'
                    cb.setToolTip(tooltip)
            except Exception:
                pass

            try:
                cb.stateChanged.connect(lambda state, cb=cb: self._on_cut_changed(cb, state))
            except Exception:
                pass

            # colocar en grid con wrapping
            try:
                col = idx % getattr(self, 'cut_buttons_max_cols', 6)
                row = idx // getattr(self, 'cut_buttons_max_cols', 6)

                is_silueta = False
                try:
                    txt_low = (str(friendly) or '').lower()
                    tt = (cb.toolTip() or '').lower()
                    if 'silueta' in txt_low or 'silueta' in tt:
                        is_silueta = True
                except Exception:
                    is_silueta = False

                if is_silueta:
                    if price_from_pv is not None:
                        try:
                            self._set_silueta_price(price_from_pv)
                        except Exception:
                            pass
                    try:
                        wrapper = QWidget()
                        wl = QHBoxLayout(wrapper)
                        wl.setContentsMargins(0, 0, 0, 0)
                        wl.setSpacing(6)
                        wl.addWidget(cb)
                        wl.addWidget(self.lbl_costo_silueta)
                        self.cut_buttons_layout.addWidget(wrapper, row, col)
                    except Exception:
                        try:
                            self.cut_buttons_layout.addWidget(cb, row, col)
                        except Exception:
                            try:
                                self.cut_buttons_layout.addWidget(cb)
                            except Exception:
                                pass
                else:
                    try:
                        self.cut_buttons_layout.addWidget(cb, row, col)
                    except Exception:
                        try:
                            self.cut_buttons_layout.addWidget(cb)
                        except Exception:
                            pass
            except Exception:
                try:
                    self.cut_buttons_layout.addWidget(cb)
                except Exception:
                    pass

            self.cut_checkboxes.append(cb)

        # mantener compatibilidad con cbo_corte
        try:
            self.cbo_corte.clear()
            self.cbo_corte.addItem('-- seleccione --', None)
            for lbl, oid in (items or []):
                display = '' if lbl is None else str(lbl)
                if display.strip().isdigit() and oid is not None:
                    try:
                        sf = getattr(self, 'session_factory', None)
                        if sf:
                            with sf() as s:
                                from ..models import ProductParameterValue
                                pv = s.get(ProductParameterValue, int(oid))
                                if pv:
                                    try:
                                        data = json.loads(pv.row_data_json or '{}')
                                    except Exception:
                                        data = None
                                    if isinstance(data, dict):
                                        display = data.get('name') or data.get('label') or data.get('descripcion') or data.get('display') or display
                    except Exception:
                        pass
                if display.strip().isdigit():
                    display = f"Corte {display.strip()}"
                self.cbo_corte.addItem(str(display), oid)

            if not any(((lbl or '').strip().lower() in ('otro', 'otros')) for lbl, _ in (items or [])):
                self.cbo_corte.addItem('Otros', None)
        except Exception:
            pass

        # No hay un único grupo; los checkboxes manejan su propio estado mediante
        # conexiones stateChanged creadas arriba.

    def _on_cbo_corte_changed(self, index: int) -> None:
        try:
            # index 0 is '-- seleccione --'
            if index <= 0:
                # desmarcar todos (checkboxes)
                for b in self.cut_checkboxes:
                    try:
                        b.setChecked(False)
                    except Exception:
                        pass
                self.txt_corte_otros.setEnabled(False)
                return
            # al seleccionar un elemento en el combo, marcar el checkbox correspondiente
            # buscamos por data (oid)
            try:
                oid = self.cbo_corte.itemData(index)
            except Exception:
                oid = None
            found = False
            # marcar el checkbox correspondiente y desmarcar los demás (selección única)
            for cb in self.cut_checkboxes:
                try:
                    if cb.property('opt_id') == oid:
                        cb.setChecked(True)
                        found = True
                    else:
                        try:
                            cb.setChecked(False)
                        except Exception:
                            pass
                except Exception:
                    pass
            # si es 'Otros' habilitar el campo
            if found:
                # enable 'Otros' if the selected item corresponds to 'Otros'
                if (self.cut_checkboxes and hasattr(self.cut_checkboxes[-1], 'text') and
                        (self.cut_checkboxes[-1].text() or '').strip().lower() in ('otro', 'otros') and
                        self.cut_checkboxes[-1].property('opt_id') is None and
                        self.cut_checkboxes[-1].isChecked()):
                    self.txt_corte_otros.setEnabled(True)
                else:
                    self.txt_corte_otros.setEnabled(False)
            else:
                self.txt_corte_otros.setEnabled(False)
            # recalc when corte selection changes
            try:
                # update silueta label visibility (if the change selected 'Silueta')
                try:
                    self._update_silueta_label_visibility()
                except Exception:
                    pass
                self._recalc()
            except Exception:
                pass
        except Exception:
            pass

    def _on_cut_selected(self, button) -> None:
        try:
            text = (button.text() or '').strip().lower()
            if 'otro' in text or 'otros' in text:
                self.txt_corte_otros.setEnabled(True)
            else:
                self.txt_corte_otros.setEnabled(False)
        except Exception:
            pass
        # NOTE: do not reload product cut types here to avoid UI reflow; loaded once at init

    def _on_cut_changed(self, checkbox: QCheckBox, state: int) -> None:
        """Handler called when a cut-type checkbox changes state.

        Mantiene el estado del campo 'Otros' y otras acciones dependientes de la selección.
        """
        try:
            text = (checkbox.text() or '').strip().lower()
            if 'otro' in text or 'otros' in text:
                # si el checkbox 'Otros' está activo, habilitar el campo
                self.txt_corte_otros.setEnabled(checkbox.isChecked())
        except Exception:
            pass
        # En modo de selección única: cuando un checkbox se marca, desmarcar los demás
        try:
            if checkbox.isChecked():
                for cb in getattr(self, 'cut_checkboxes', []) or []:
                    try:
                        if cb is not checkbox:
                            cb.setChecked(False)
                    except Exception:
                        pass
        except Exception:
            pass

        # Recalculate pricing/measurements when cut selection changes
        try:
            try:
                self._update_silueta_label_visibility()
            except Exception:
                pass
            self._recalc()
        except Exception:
            pass

    def _update_silueta_label_visibility(self) -> None:
        """Muestra u oculta `lbl_costo_silueta` si la checkbox correspondiente contiene 'silueta' y está marcada.

        Busca entre `self.cut_checkboxes` la(s) checkbox(es) cuyo texto o tooltip contenga la palabra
        'silueta' y, si alguna está marcada, hace visible la etiqueta; en caso contrario la oculta.
        """
        try:
            show = False
            for cb in getattr(self, 'cut_checkboxes', []) or []:
                try:
                    txt = (cb.text() or '').lower()
                    tt = (cb.toolTip() or '').lower()
                    if 'silueta' in txt or 'silueta' in tt:
                        if cb.isChecked():
                            show = True
                            break
                except Exception:
                    pass
            try:
                self.lbl_costo_silueta.setVisible(bool(show))
            except Exception:
                pass
        except Exception:
            pass

    def _set_silueta_price(self, price: float | None) -> None:
        """Actualiza el precio por m² asociado al corte silueta y refresca la etiqueta informativa."""
        try:
            val = float(price or 0.0)
        except Exception:
            val = 0.0
        try:
            self._silueta_price_val = val
        except Exception:
            self._silueta_price_val = 0.0
        try:
            if val > 0.0:
                self.lbl_costo_silueta.setText(f"Costo silueta: ${val:.2f}/m²")
            else:
                self.lbl_costo_silueta.setText("")
        except Exception:
            pass

    def _is_round_cut(self) -> bool:
        """Best-effort: determine if the currently selected cut type is round.

        Checks checked cut_checkboxes first, then the combo `cbo_corte`.
        """
        try:
            # keywords indicating round shapes
            keys = ('redond', 'círc', 'circle', 'circular', 'round')
            # check checkboxes
            for cb in getattr(self, 'cut_checkboxes', []) or []:
                try:
                    if cb.isChecked():
                        txt = (cb.text() or '').lower()
                        for k in keys:
                            if k in txt:
                                return True
                except Exception:
                    pass
            # fallback: check combo text
            try:
                t = (self.cbo_corte.currentText() or '').lower()
                for k in keys:
                    if k in t:
                        return True
            except Exception:
                pass
        except Exception:
            pass
        return False

    def _wire_signals(self) -> None:
        try:
            self.spin_alto.valueChanged.connect(self._recalc)
            self.spin_ancho.valueChanged.connect(self._recalc)
            self.spin_diam.valueChanged.connect(self._recalc)
            self.spin_soporte_qty.valueChanged.connect(self._recalc)
            # spin_esp_precio removed; recalc will read price from self._esp_precio_val
            # regulator quantity affects totals
            self.spin_reg_cant.valueChanged.connect(self._recalc)
            # wire compatibility esp price spin if present
            try:
                if getattr(self, 'spin_esp_precio', None) is not None:
                    self.spin_esp_precio.valueChanged.connect(self._recalc)
            except Exception:
                pass
            # ensure caja pct changes recalc immediately
            try:
                if hasattr(self, 'spin_caja_pct'):
                    self.spin_caja_pct.valueChanged.connect(self._recalc)
            except Exception:
                pass
        except Exception:
            pass

        # caja checkbox should enable/disable caja-related controls
        try:
            self.chk_caja.stateChanged.connect(lambda s: (self._update_caja_controls_enabled(), self._recalc()))
        except Exception:
            pass

        self.btn_cancel.clicked.connect(self.reject)
        try:
            self.btn_ok.clicked.connect(self._on_accept)
        except Exception:
            pass
        # update luz price when selection changes
        try:
            if getattr(self, 'cbo_luz_tipo', None) is not None:
                self.cbo_luz_tipo.currentIndexChanged.connect(lambda idx: (self._update_luz_price(), self._recalc()))
        except Exception:
            pass
        # connect regulator change to handler to show price label
        try:
            self.cbo_reg_amp.currentIndexChanged.connect(self._on_regulador_changed)
        except Exception:
            pass

        # Connect material change to populate espesor
        try:
            self.cbo_material.currentIndexChanged.connect(self._on_material_changed)
        except Exception:
            pass

        # Connect soporte item change to populate sizes
        try:
            self.cbo_soporte_item.currentIndexChanged.connect(self._on_soporte_item_changed)
        except Exception:
            pass

        # Connect soporte size change to update price
        try:
            self.cbo_soporte_size.currentIndexChanged.connect(self._on_soporte_size_changed)
        except Exception:
            pass

    def _update_caja_controls_enabled(self) -> None:
        """Habilita o deshabilita los controles de la Sección 7 según el checkbox `chk_caja`."""
        try:
            enabled = bool(getattr(self, 'chk_caja', None) and self.chk_caja.isChecked())
        except Exception:
            enabled = False
        try:
            # controls to toggle: cbo_caja_base, cbo_caja_faja, spin_caja_pct
            if hasattr(self, 'cbo_caja_base'):
                try:
                    self.cbo_caja_base.setEnabled(enabled)
                except Exception:
                    pass
            if hasattr(self, 'cbo_caja_faja'):
                try:
                    self.cbo_caja_faja.setEnabled(enabled)
                except Exception:
                    pass
            if hasattr(self, 'spin_caja_pct'):
                try:
                    self.spin_caja_pct.setEnabled(enabled)
                except Exception:
                    pass
        except Exception:
            pass

    def _update_luz_price(self) -> None:
        """Set `lbl_luz_price` based on the selected item in `cbo_luz_tipo`.

        Expects itemData to be a tuple/list (pv_id, price, unit).
        """
        try:
            sel = None
            try:
                sel = self.cbo_luz_tipo.itemData(self.cbo_luz_tipo.currentIndex()) if getattr(self, 'cbo_luz_tipo', None) is not None else None
            except Exception:
                sel = None
            if isinstance(sel, (list, tuple)) and len(sel) >= 3:
                try:
                    price_val = float(sel[1] or 0.0)
                except Exception:
                    price_val = 0.0
                try:
                    self.lbl_luz_price.setText(f"${float(price_val):.2f}" if price_val else "")
                except Exception:
                    pass
            else:
                try:
                    self.lbl_luz_price.setText("")
                except Exception:
                    pass
        except Exception:
            pass

    def _on_accept(self) -> None:
        """Handler for the OK button: extrae datos seleccionados y los guarda en `self.accepted_data`.

        Los campos extraídos:
        - nombre (self.txt_name.text())
        - descripcion (self.txt_desc.toPlainText())
        - subtotal (float(self.lbl_subtotal.text()))
        - total (float(self.lbl_total.text()))

        Después de almacenar los datos, llama a `accept()` para cerrar el diálogo con éxito.
        """
        try:
            # basics
            nombre = self.txt_name.text().strip() if hasattr(self, 'txt_name') else ''
            descripcion = self.txt_desc.toPlainText().strip() if hasattr(self, 'txt_desc') else ''

            def _parse_price(txt: str) -> float:
                try:
                    if not txt:
                        return 0.0
                    t = str(txt).replace('$', '').replace(',', '').strip()
                    return float(t) if t else 0.0
                except Exception:
                    return 0.0

            try:
                subtotal = float(self.lbl_subtotal.text())
            except Exception:
                subtotal = 0.0
            try:
                total = float(self.lbl_total.text())
            except Exception:
                total = subtotal

            # medidas
            try:
                alto = float(self.spin_alto.value())
            except Exception:
                alto = 0.0
            try:
                ancho = float(self.spin_ancho.value())
            except Exception:
                ancho = 0.0
            try:
                diam = float(self.spin_diam.value())
            except Exception:
                diam = 0.0
            area = 0.0
            try:
                area = float(self.lbl_area.text())
            except Exception:
                area = 0.0

            medidas = {'alto_cm': alto, 'ancho_cm': ancho, 'diam_mm': diam, 'area_m2': area}

            # tipo(s) de corte: checked boxes + combo (if selected)
            cortes = []
            try:
                for cb in getattr(self, 'cut_checkboxes', []) or []:
                    try:
                        if cb.isChecked():
                            # Usar 'tipo' en lugar de 'label' para consistencia con la nueva estructura
                            corte_entry = {
                                'tipo': cb.text(),
                                'tooltip': cb.toolTip(),
                                'opt_id': cb.property('opt_id'),
                            }
                            try:
                                price_prop = cb.property('price_m2')
                                if price_prop is not None:
                                    corte_entry['price_m2'] = float(price_prop)
                                    corte_entry['subtotal'] = float(price_prop) * float(self.lbl_area.text() or 0.0)
                            except Exception:
                                pass
                            cortes.append(corte_entry)
                    except Exception:
                        pass
            except Exception:
                cortes = []
            try:
                cbo_corte_text = self.cbo_corte.currentText() if hasattr(self, 'cbo_corte') else ''
                if cbo_corte_text and cbo_corte_text.strip() and not cbo_corte_text.strip().startswith('--'):
                    cortes.append({'tipo': cbo_corte_text, 'from_combo': True})
            except Exception:
                pass

            # material / espesor
            material = ''
            material_id = None
            espesor = ''
            espesor_id = None
            try:
                esp_precio = float(getattr(self, '_esp_precio_val', 0.0) or 0.0)
            except Exception:
                esp_precio = 0.0

            try:
                if hasattr(self, 'cbo_material'):
                    material = self.cbo_material.currentText()
                    material_id = self.cbo_material.itemData(self.cbo_material.currentIndex())
            except Exception:
                material = ''
                material_id = None

            try:
                if hasattr(self, 'cbo_espesor'):
                    espesor = self.cbo_espesor.currentText()
                    espesor_id = self.cbo_espesor.itemData(self.cbo_espesor.currentIndex())
                    # update price cache in case UI spinner holds a manual value
                    try:
                        if getattr(self, 'spin_esp_precio', None) is not None:
                            esp_precio = float(self.spin_esp_precio.value())
                    except Exception:
                        pass
            except Exception:
                espesor = ''
                espesor_id = None

            # base color flags
            try:
                base_color = self.txt_base_color.text() if hasattr(self, 'txt_base_color') else ''
                base_color_cod = self.txt_base_color_cod.text() if hasattr(self, 'txt_base_color_cod') else ''
                base_crudo = bool(getattr(self, 'chk_base_crudo', None) and self.chk_base_crudo.isChecked())
                base_transp = bool(getattr(self, 'chk_base_transp', None) and self.chk_base_transp.isChecked())
            except Exception:
                base_color = base_color_cod = ''
                base_crudo = base_transp = False

            # tipos de corporeo seleccionados
            tipos_corporeo = []
            try:
                for cb, price_lbl, oid in (getattr(self, 'tipo_corp_checkboxes', []) or []):
                    try:
                        if cb.isChecked():
                            price_txt = price_lbl.text() if price_lbl is not None else ''
                            tipos_corporeo.append({'label': cb.text(), 'pv_id': oid, 'price': _parse_price(price_txt)})
                    except Exception:
                        pass
            except Exception:
                tipos_corporeo = []

            # soporte/base seleccionado
            try:
                soporte_model = self.cbo_soporte_item.currentText() if hasattr(self, 'cbo_soporte_item') else ''
                soporte_size = self.cbo_soporte_size.currentText() if hasattr(self, 'cbo_soporte_size') else ''
                soporte_price = _parse_price(self.lbl_soporte_precio.text() if hasattr(self, 'lbl_soporte_precio') else '')
                soporte_qty = int(getattr(self, 'spin_soporte_qty', None).value()) if getattr(self, 'spin_soporte_qty', None) is not None else 0
            except Exception:
                soporte_model = soporte_size = ''
                soporte_price = 0.0
                soporte_qty = 0

            # luces: use the selected combo item (single selection)
            luces = []
            try:
                sel = None
                try:
                    sel = self.cbo_luz_tipo.itemData(self.cbo_luz_tipo.currentIndex()) if getattr(self, 'cbo_luz_tipo', None) is not None else None
                except Exception:
                    sel = None
                if isinstance(sel, (list, tuple)) and len(sel) >= 3:
                    # itemData stored as (pv_id, price, unit)
                    pv_id, price_val, unit = sel[0], sel[1], sel[2]
                    try:
                        price_val = float(price_val or 0.0)
                    except Exception:
                        price_val = 0.0
                    luces.append({'type': self.cbo_luz_tipo.currentText() or '', 'price': float(price_val), 'pv_id': pv_id, 'unit': unit})
                else:
                    # no selection -> empty list
                    luces = []
            except Exception:
                luces = []
            try:
                luz_color = self.cbo_luz_color.currentText() if hasattr(self, 'cbo_luz_color') else ''
            except Exception:
                luz_color = ''
            try:
                pos_luz = self.cbo_pos_luz.currentText() if hasattr(self, 'cbo_pos_luz') else ''
            except Exception:
                pos_luz = ''

            # regulador
            try:
                regulador = self.cbo_reg_amp.currentText() if hasattr(self, 'cbo_reg_amp') else ''
                regulador_id = self.cbo_reg_amp.itemData(self.cbo_reg_amp.currentIndex()) if hasattr(self, 'cbo_reg_amp') else None
                regulador_price = _parse_price(self.lbl_reg_precio.text() if hasattr(self, 'lbl_reg_precio') else '')
                regulador_qty = int(self.spin_reg_cant.value()) if hasattr(self, 'spin_reg_cant') else 0
            except Exception:
                regulador = ''
                regulador_id = None
                regulador_price = 0.0
                regulador_qty = 0

            # caja info
            try:
                caja_enabled = bool(getattr(self, 'chk_caja', None) and self.chk_caja.isChecked())
                caja_base = self.cbo_caja_base.currentText() if hasattr(self, 'cbo_caja_base') else ''
                caja_faja = self.cbo_caja_faja.currentText() if hasattr(self, 'cbo_caja_faja') else ''
                caja_pct = float(self.spin_caja_pct.value()) if hasattr(self, 'spin_caja_pct') else 0.0
            except Exception:
                caja_enabled = False
                caja_base = caja_faja = ''
                caja_pct = 0.0

            try:
                precio_final_usd = float(getattr(self, '_last_precio_final_usd', 0.0) or float(self.lbl_precio_final_corporeo_usd.text() or 0.0))
            except Exception:
                precio_final_usd = 0.0
            try:
                precio_final_bs = float(getattr(self, '_last_precio_final_bs', 0.0))
            except Exception:
                precio_final_bs = 0.0
            try:
                tasa_corp = float(getattr(self, '_last_tasa_corporeo', 0.0))
            except Exception:
                tasa_corp = 0.0
            try:
                tasa_bcv_val = float(getattr(self, '_last_tasa_bcv', 0.0))
                if not tasa_bcv_val:
                    tasa_bcv_val = float(self._get_tasa_bcv())
            except Exception:
                tasa_bcv_val = 0.0

            payload = {
                'nombre': nombre,
                'descripcion': descripcion,
                'medidas': medidas,
                'cortes': cortes,
                'material': {'label': material, 'id': material_id},
                'espesor': {'label': espesor, 'id': espesor_id, 'price': float(esp_precio)},
                'base_color': {'color': base_color, 'code': base_color_cod, 'crudo': base_crudo, 'transparente': base_transp},
                'tipos_corporeo': tipos_corporeo,
                'soporte': {'model': soporte_model, 'size': soporte_size, 'price': float(soporte_price), 'qty': int(soporte_qty)},
                'luces': {'selected': luces, 'color': luz_color, 'posicion': pos_luz},
                'regulador': {'label': regulador, 'id': regulador_id, 'price': float(regulador_price), 'qty': int(regulador_qty)},
                'caja': {'enabled': bool(caja_enabled), 'base': caja_base, 'faja': caja_faja, 'pct': float(caja_pct)},
                'silueta': {
                    'price_m2': float(getattr(self, '_silueta_price_val', 0.0) or 0.0),
                    'subtotal': float(getattr(self, '_last_silueta_subtotal', 0.0) or 0.0),
                },
                'subtotal': float(subtotal),
                'total': float(total),
                'precio_final_usd': float(precio_final_usd),
                'precio_final_bs': float(precio_final_bs),
                'tasa_corporeo': float(tasa_corp),
                'tasa_bcv': float(tasa_bcv_val),
                'product_id': self.product_id,  # Guardar product_id para futuras ediciones
            }
            payload['totals'] = {
                'total_usd': float(precio_final_usd),
                'total_bs': float(precio_final_bs),
                'tasa_bcv': float(tasa_bcv_val),
                'tasa_corporeo': float(tasa_corp),
            }
            # preserve user-provided description separately
            try:
                payload['descripcion_user'] = descripcion
            except Exception:
                payload['descripcion_user'] = ''
            # build a presentation description for the sales form (exclude area and diameter)
            try:
                payload['descripcion'] = self._format_description_for_sale(payload)
            except Exception:
                # fallback to user description
                payload['descripcion'] = descripcion

            try:
                self.accepted_data = payload
                try:
                    import json as _json
                    print(f"[DEBUG CorporeoDialog] accepted_data generado: {_json.dumps(payload, ensure_ascii=False)}")
                except Exception:
                    print("[DEBUG CorporeoDialog] accepted_data generado pero no se pudo serializar para debug")
            except Exception:
                pass
            try:
                self.accept()
            except Exception:
                return
        except Exception:
            try:
                self.accepted_data = None
                self.accept()
            except Exception:
                pass

    def _format_description_for_sale(self, payload: dict) -> str:
        """Crea una descripción corta para pegar en el formulario de venta.

        La descripción incluirá (cuando estén presentes): medidas (alto x ancho en cm),
        tipos de corte (labels), material y espesor, flags de color/base, tipos de corporeo
        seleccionados, soporte (modelo/tamaño), tipo/color/pos de luz, regulador y cantidad,
        y si se convirtió a caja (base + faja).

        Importante: NO incluye área ni diámetro.
        """
        try:
            parts = []
            # medidas
            med = payload.get('medidas') or {}
            try:
                a = float(med.get('alto_cm') or 0.0)
                b = float(med.get('ancho_cm') or 0.0)
                if a or b:
                    parts.append(f"Medidas: {a:.1f} x {b:.1f} cm")
            except Exception:
                pass

            # cortes
            cortes = payload.get('cortes') or []
            if cortes:
                # Ahora la columna es 'tipo', no 'label'
                labels = [c.get('tipo') or str(c.get('opt_id') or '') for c in cortes if c]
                if labels:
                    parts.append(f"Corte: {', '.join(labels)}")

            # material / espesor
            mat = payload.get('material') or {}
            esp = payload.get('espesor') or {}
            if mat.get('label'):
                mat_part = f"Material: {mat.get('label')}"
                if esp.get('label'):
                    mat_part += f" Espesor: {esp.get('label')}"
                parts.append(mat_part)

            # base color
            bc = payload.get('base_color') or {}
            flags = []
            if bc.get('crudo'):
                flags.append('Crudo')
            if bc.get('transparente'):
                flags.append('Transp.')
            if flags:
                parts.append('Base: ' + ' '.join(flags))

            # tipos corporeo
            tipos = payload.get('tipos_corporeo') or []
            if tipos:
                labels = [t.get('label') for t in tipos if t and t.get('label')]
                if labels:
                    parts.append('Tipos: ' + ', '.join(labels))

            # soporte
            s = payload.get('soporte') or {}
            if s.get('model') or s.get('size'):
                parts.append(f"Soporte: {s.get('model','') or ''} {s.get('size','') or ''}".strip())

            # luces
            l = payload.get('luces') or {}
            luces_sel = l.get('selected') or []
            if luces_sel:
                lt = ','.join([str(x.get('type')) for x in luces_sel])
                details = f"Luz: {lt}"
                if l.get('color'):
                    details += f" Color: {l.get('color')}"
                if l.get('posicion'):
                    details += f" Pos: {l.get('posicion')}"
                parts.append(details)

            # regulador
            reg = payload.get('regulador') or {}
            if reg.get('label') or reg.get('qty'):
                parts.append(f"Reg: {reg.get('label', '')} x{int(reg.get('qty',0))}")

            # caja
            caja = payload.get('caja') or {}
            if caja.get('enabled'):
                parts.append(f"Caja: {caja.get('base','')} {caja.get('faja','')}")

            # subtotal/total appended at end
            try:
                parts.append(f"Subtotal: {float(payload.get('subtotal',0.0)):.2f}")
                parts.append(f"Total: {float(payload.get('total',0.0)):.2f}")
            except Exception:
                pass

            return '  '.join([p for p in parts if p])
        except Exception:
            return payload.get('descripcion_user') or ''

    def _load_from_eav(self) -> None:
        """Carga atributos/opciones desde EAV para poblar comboboxes.

        Requiere que `self.session_factory` y `self.type_id` estén definidos.
        """
        sf = getattr(self, 'session_factory', None)
        t_id = getattr(self, 'type_id', None)
        if sf is None or not isinstance(t_id, int):
            return
        try:
            with sf() as s:
                attrs = _repo.eav_list_attributes_for_type(s, t_id)
                # attrs: list of (EavAttribute, [EavAttributeOption,...])
                for atr, options in attrs:
                    code = (getattr(atr, 'code', '') or '').strip()
                    if not code:
                        continue
                    # map known codes to comboboxes
                    if code in ('material',):
                        cb = self.cbo_material
                    elif code in ('espesor_mm', 'espesor'):
                        cb = self.cbo_espesor
                    elif code in ('luces_color',):
                        cb = self.cbo_luz_color
                    elif code in ('posicion_luz', 'posicion_luz'):
                        cb = self.cbo_pos_luz
                    elif code in ('regulador_amp',):
                        cb = self.cbo_reg_amp
                    elif code in ('corte_tipo',):
                        # poblar radio buttons para tipos de corte
                        opts_from_eav = []
                        for op in (options or []):
                            label = getattr(op, 'label', None) or getattr(op, 'code', None) or str(getattr(op, 'id', ''))
                            opts_from_eav.append((label, getattr(op, 'id', None)))
                        # create radio buttons
                        try:
                            self._set_cut_options_from_list(opts_from_eav)
                        except Exception:
                            pass
                        cb = None
                    elif code in ('luces_tipo',):
                        # populate combo combo for luces_tipo (compatibility with tests)
                        cb = self.cbo_luz_tipo
                    else:
                        cb = None
                    if cb is not None:
                        # clear and add default
                        cb.clear()
                        cb.addItem("-- seleccione --", None)
                        for op in (options or []):
                            label = getattr(op, 'label', None) or getattr(op, 'code', None) or str(getattr(op, 'id', ''))
                            cb.addItem(str(label), getattr(op, 'id', None))
        except Exception:
            # no fallas críticas: silenciosamente no cargar si hay problema
            return

    def _load_cut_types_from_product(self, product_identifier: int | dict | None) -> None:
        """Cargar opciones de 'Tipos de corte' desde las tablas de parámetros del producto.

        Busca tablas asociadas al producto (usando repository.get_product_parameter_tables)
        y si encuentra una tabla cuyo nombre o display_name contenga 'corte' o 'tipo',
        obtiene sus valores activos y los añade a `self.cbo_corte`.
        """
        # If no product_identifier provided, attempt global search across all parameter tables
        sf = getattr(self, 'session_factory', None)
        if sf is None:
            return
        try:
            with sf() as s:
                # Intentar obtener tablas de parámetros del producto
                # normalizar identificador a int (repo acepta int o dict con 'id')
                pid = None
                # normalize identifier that may be int, str or dict with 'id'
                if isinstance(product_identifier, dict):
                    pid_val = product_identifier.get('id')
                else:
                    pid_val = product_identifier
                try:
                    if pid_val is None:
                        pid = None
                    else:
                        pid = int(pid_val)
                except Exception:
                    pid = None
                if not pid:
                    return
                tables = _repo.get_product_parameter_tables(s, pid, include_inactive=False)
                logger.debug(f"_load_cut_types_from_product: found {len(tables)} tables for product {pid}")
                # Buscar tablas relacionadas con corte
                # Priorizar display_name exacto "cortes" o que contenga "_cortes_" en table_name
                corte_tables = []
                exact_match = None
                
                for t in tables:
                    tn = (t.get('table_name') or '').lower()
                    dn = (t.get('display_name') or '').lower()
                    logger.debug(f"  Evaluating table: display_name='{dn}', table_name='{tn}'")
                    
                    # Prioridad 1: display_name exactamente "cortes"
                    if dn == 'cortes':
                        logger.debug(f"    ✓ Exact match found: {t.get('display_name')}")
                        exact_match = t
                        break
                    
                    # Prioridad 2: table_name contiene "_cortes_" (evita "precio_corte_silueta")
                    if '_cortes_' in tn:
                        corte_tables.insert(0, t)
                    # Prioridad 3: display_name contiene "tipo" y "corte"
                    elif 'tipo' in dn and 'corte' in dn:
                        corte_tables.append(t)
                    # Prioridad 4: cualquier tabla que contenga "corte"
                    elif 'corte' in dn:
                        corte_tables.append(t)
                
                if exact_match:
                    corte_tables = [exact_match]
                
                logger.debug(f"_load_cut_types_from_product: selected {len(corte_tables)} corte table(s)")
                if corte_tables:
                    logger.debug(f"  First table: {corte_tables[0].get('display_name')} (ID: {corte_tables[0].get('id')})")
                
                if not corte_tables:
                    # No se encontraron tablas de 'corte' para este producto; no usar
                    # un fallback que pueda devolver tablas no relacionadas (p.ej. materiales).
                    logger.debug("_load_cut_types_from_product: no corte tables found for product %r — skipping", pid)
                    corte_tables = []

                # cargar valores desde product_parameter_values para la primera tabla encontrada
                if corte_tables:
                    table = corte_tables[0]
                    logger.info(f"Loading cut types from table: {table.get('display_name')} (ID: {table.get('id')})")
                    # obtener filas activas
                    from ..models import ProductParameterValue
                    rows = (
                        s.query(ProductParameterValue)
                        .filter(ProductParameterValue.parameter_table_id == table['id'])
                        .filter(ProductParameterValue.is_active == True)
                        .all()
                    )
                    opts = []
                    import json
                    for r in rows:
                        try:
                            data = json.loads(r.row_data_json)
                        except Exception:
                            data = None
                        label = None
                        if isinstance(data, dict):
                            # Priorizar 'tipo de corte' (nuevo nombre de columna en la tabla cortes)
                            for k in ('tipo de corte', 'tipo_de_corte', 'Tipo de Corte', 'Tipo', 'tipo', 'nombre', 'Nombre', 'name', 'label', 'descripcion', 'display'):
                                try:
                                    v = data.get(k)
                                    if isinstance(v, str) and v.strip():
                                        label = v.strip(); break
                                    # accept numeric labels as well
                                    if v is not None and not isinstance(v, dict):
                                        label = str(v); break
                                except Exception:
                                    continue
                            
                            # Si no encontramos label, buscar relaciones (columnas id_xxx o xxx_id)
                            if not label:
                                for k, v in data.items():
                                    if (k.startswith('id_') or k.endswith('_id')) and isinstance(v, (int, str)):
                                        try:
                                            related_id = int(v)
                                            related_row = s.query(ProductParameterValue).filter(ProductParameterValue.id == related_id).first()
                                            if related_row:
                                                related_data = json.loads(related_row.row_data_json or '{}')
                                                # Buscar en el registro relacionado
                                                for kk in ('tipo de corte', 'tipo_de_corte', 'Tipo de Corte', 'Tipo', 'tipo', 'nombre', 'name', 'label'):
                                                    vv = related_data.get(kk)
                                                    if isinstance(vv, str) and vv.strip():
                                                        label = vv.strip()
                                                        break
                                                if label:
                                                    break
                                        except Exception:
                                            continue
                        if not label:
                            label = getattr(r, 'id', None) or str(getattr(r, 'id', ''))
                        opts.append((label, getattr(r, 'id', None)))
                    try:
                        self._set_cut_options_from_list(opts)
                    except Exception:
                        pass
                    # además, intentar detectar un precio de silueta en las filas o en una tabla hija
                    try:
                        # Primero intentar en la misma fila: buscar clave 'silueta_price' o 'precio_silueta' en row_data_json
                        sil_price = None
                        for r in rows:
                            try:
                                data = json.loads(r.row_data_json or '{}')
                            except Exception:
                                data = {}
                            if isinstance(data, dict):
                                # posibles keys
                                for key in ('silueta_price', 'precio_silueta', 'silueta_extra', 'costo_silueta', 'precio'):
                                    if key in data:
                                        try:
                                            sil_price = float(data.get(key) or 0.0)
                                            break
                                        except Exception:
                                            pass
                            if sil_price is not None:
                                break
                        # Si no se encontró, buscar en tablas hijas: por convención, puede existir una tabla cuyo display_name contenga 'precio' o 'silueta'
                        if sil_price is None:
                            child_tables = _repo.get_child_parameter_tables(s, table['id'], active_only=True)
                            for ct in (child_tables or []):
                                dn = (ct.get('display_name') or '').lower()
                                tn = (ct.get('table_name') or '').lower()
                                if 'silueta' in dn or 'silueta' in tn or 'precio' in dn or 'precio' in tn:
                                    # obtener la primera fila activa de la tabla hija
                                    subrows = (
                                        s.query(ProductParameterValue)
                                        .filter(ProductParameterValue.parameter_table_id == ct['id'])
                                        .filter(ProductParameterValue.is_active == True)
                                        .all()
                                    )
                                    for sr in subrows:
                                        try:
                                            sdata = json.loads(sr.row_data_json or '{}')
                                        except Exception:
                                            sdata = {}
                                        if isinstance(sdata, dict):
                                            for key in ('value', 'precio', 'precio_silueta', 'silueta_price', 'amount'):
                                                if key in sdata:
                                                    try:
                                                        sil_price = float(sdata.get(key) or 0.0)
                                                        break
                                                    except Exception:
                                                        pass
                                        if sil_price is not None:
                                            break
                                if sil_price is not None:
                                    break
                        # If still not found, try to find a dedicated table anywhere in the product
                        # whose display_name/table_name suggests it stores the "Precio Corte Silueta".
                        if sil_price is None:
                            try:
                                # 'tables' was loaded above; if present, scan them
                                for t in (tables or []):
                                    try:
                                        dn = (t.get('display_name') or '').lower()
                                        tn = (t.get('table_name') or '').lower()
                                        # match either the exact phrase or presence of both words
                                        if ('precio corte silueta' in dn) or ('precio corte silueta' in tn) or (('precio' in dn and 'silueta' in dn) or ('precio' in tn and 'silueta' in tn)):
                                            from ..models import ProductParameterValue
                                            subrows = (
                                                s.query(ProductParameterValue)
                                                .filter(ProductParameterValue.parameter_table_id == t['id'])
                                                .filter(ProductParameterValue.is_active == True)
                                                .all()
                                            )
                                            for sr in subrows:
                                                try:
                                                    sdata = json.loads(sr.row_data_json or '{}')
                                                except Exception:
                                                    sdata = {}
                                                if isinstance(sdata, dict):
                                                    # normalize keys to lowercase for case-insensitive matching
                                                    lower_map = {str(k).lower(): v for k, v in sdata.items()}
                                                    for key in ('precio', 'price', 'value', 'amount', 'precio_silueta', 'silueta_price'):
                                                        if key in lower_map:
                                                            try:
                                                                sil_price = float(lower_map.get(key) or 0.0)
                                                                break
                                                            except Exception:
                                                                pass
                                                if sil_price is not None:
                                                    break
                                    except Exception:
                                        pass
                                # if found, we'll use it; otherwise fall back to global params below
                            except Exception:
                                pass

                        # Si todavía no se encontró, mirar parámetros globales (price_params)
                        if sil_price is None:
                            try:
                                from ..price_params import get_param
                                sil_price = float(get_param('corte_silueta_extra_m2', 0.0) or 0.0)
                            except Exception:
                                sil_price = 0.0

                        # Update the silueta cost label if we found a price
                        try:
                            self._set_silueta_price(sil_price)
                            try:
                                self._update_silueta_label_visibility()
                            except Exception:
                                pass
                        except Exception:
                            pass
                    except Exception:
                        # no bloquear la carga si falla la lectura del precio
                        pass
        except Exception:
            # si falla, mantener el combo con su estado actual
            return

    def _on_regulador_changed(self, index: int) -> None:
        """Cuando cambia el regulador (amp), intentar mostrar precio por unidad en `lbl_reg_precio`.

        Busca en EAV o en ProductParameterValue (si el combo contiene itemData con id) y actualiza label.
        """
        try:
            try:
                oid = self.cbo_reg_amp.itemData(index)
            except Exception:
                oid = None
            price = None
            # try direct EAV/EAV options if available
            sf = getattr(self, 'session_factory', None)
            if sf and oid:
                with sf() as s:
                    try:
                        from ..models import ProductParameterValue
                        pv = s.get(ProductParameterValue, int(oid))
                        if pv:
                            import json
                            try:
                                data = json.loads(pv.row_data_json or '{}')
                            except Exception:
                                data = {}
                            if isinstance(data, dict):
                                for k in ('precio', 'Precio', 'price', 'valor'):
                                    v = data.get(k)
                                    if v is None:
                                        continue
                                    try:
                                        price = float(v)
                                        break
                                    except Exception:
                                        try:
                                            price = float(str(v).replace('$','').replace(',','').strip())
                                            break
                                        except Exception:
                                            pass
                    except Exception:
                        pass
            # fallback: no price found -> show empty
            try:
                if price is not None:
                    self.lbl_reg_precio.setText(f"${float(price):.2f}")
                else:
                    self.lbl_reg_precio.setText("")
            except Exception:
                pass
            # recalc totals on change
            try:
                self._recalc()
            except Exception:
                pass
        except Exception:
            pass

    def _load_materials_from_product(self, product_identifier: int | dict | None) -> None:
        """Cargar valores para el combo de Material desde tablas de parámetros del producto.

        Busca tablas asociadas al producto cuya table_name o display_name contenga 'material'
        o cuyo table_name sea exactamente 'materiales' o 'material' y rellena `self.cbo_material`
        con las filas activas encontradas. Si no se encuentran tablas o filas, no hace nada.
        """
        if not product_identifier:
            return
        sf = getattr(self, 'session_factory', None)
        if sf is None:
            return
        try:
            with sf() as s:
                # normalizar identificador
                pid = None
                if isinstance(product_identifier, dict):
                    pid_val = product_identifier.get('id')
                else:
                    pid_val = product_identifier
                try:
                    pid = int(pid_val) if pid_val is not None else None
                except Exception:
                    pid = None
                if not pid:
                    return
                tables = _repo.get_product_parameter_tables(s, pid, include_inactive=False)
                # buscar tabla de materiales
                mat_tables = []
                for t in (tables or []):
                    tn = (t.get('table_name') or '').lower()
                    dn = (t.get('display_name') or '').lower()
                    if tn in ('materiales', 'material'):
                        mat_tables = [t]
                        break
                    if 'material' in dn:
                        mat_tables.append(t)
                if not mat_tables:
                    return
                table = mat_tables[0]
                logger.debug("_load_materials_from_product: using table id=%r display=%r", table.get('id'), table.get('display_name'))
                from ..models import ProductParameterValue
                rows = (
                    s.query(ProductParameterValue)
                    .filter(ProductParameterValue.parameter_table_id == table['id'])
                    .filter(ProductParameterValue.is_active == True)
                    .all()
                )
                opts = []
                import json
                for r in rows:
                    try:
                        data = json.loads(r.row_data_json or '{}')
                    except Exception:
                        data = None
                    label = None
                    if isinstance(data, dict):
                        # Preferir claves que representen el nombre en varias capitalizaciones
                        for k in ('Nombre', 'nombre', 'Name', 'name', 'label', 'display', 'material', 'valor', 'value', 'descripcion'):
                            v = data.get(k)
                            if isinstance(v, str) and v.strip():
                                label = v.strip(); break
                    if not label:
                        label = str(getattr(r, 'id', ''))
                    opts.append((label, getattr(r, 'id', None)))
                # popular cbo_material (mantener compatibilidad añadiendo opción por defecto)
                try:
                    self.cbo_material.clear()
                    self.cbo_material.addItem('-- seleccione --', None)
                    for lbl, oid in opts:
                        self.cbo_material.addItem(str(lbl), oid)
                    # store reference to the parameter table used for materials so we can
                    # load dependent 'espesor' options when a material is selected
                    try:
                        self._materials_param_table = table
                        self._materials_param_table_id = table.get('id')
                    except Exception:
                        self._materials_param_table = None
                        self._materials_param_table_id = None
                    # connect change handler to populate espesor based on selected material
                    try:
                        self.cbo_material.currentIndexChanged.connect(self._on_material_changed)
                    except Exception:
                        pass
                    logger.debug("_load_materials_from_product: populated %d materials", len(opts))
                except Exception:
                    pass
        except Exception:
            # no bloquear la creación del dialogo si falla la lectura
            return

    def _load_bases_separadores_from_product(self, product_identifier: int | dict | None) -> None:
        """Cargar opciones de 'Bases y Separadores' desde tablas de parámetros del producto.

        Busca una tabla cuyo display_name o table_name contenga 'base' o 'separador'
        y pobla `self.cbo_soporte_item` y `self.cbo_soporte_size`. También establece
        el precio en `self.lbl_soporte_precio` al seleccionar una combinación.
        """
        sf = getattr(self, 'session_factory', None)
        if sf is None:
            return
        try:
            with sf() as s:
                logger.debug("_load_bases_separadores_from_product: start pid=%r", product_identifier)
                # normalize id
                pid = None
                if isinstance(product_identifier, dict):
                    pid_val = product_identifier.get('id')
                else:
                    pid_val = product_identifier
                try:
                    pid = int(pid_val) if pid_val is not None else None
                except Exception:
                    pid = None
                if not pid:
                    return
                tables = _repo.get_product_parameter_tables(s, pid, include_inactive=False)
                candidate = None
                for t in (tables or []):
                    tn = (t.get('table_name') or '').lower()
                    dn = (t.get('display_name') or '').lower()
                    if 'base' in dn or 'separador' in dn or 'bases' in dn:
                        candidate = t; break
                if not candidate:
                    return
                logger.debug("_load_bases_separadores_from_product: using table %r", candidate)
                from ..models import ProductParameterValue
                rows = (
                    s.query(ProductParameterValue)
                    .filter(ProductParameterValue.parameter_table_id == candidate.get('id'))
                    .filter(ProductParameterValue.is_active == True)
                    .all()
                )
                logger.debug("_load_bases_separadores_from_product: rows fetched=%d", len(rows or []))
                # Parse rows into a mapping: model -> list of (size, price, pv_id)
                import json
                mapping = {}
                for r in (rows or []):
                    try:
                        data = json.loads(r.row_data_json or '{}')
                    except Exception:
                        data = {}
                    model = None
                    size = None
                    price = None
                    if isinstance(data, dict):
                        # heuristics for keys
                        for k in ('Modelo', 'Modelo *', 'modelo', 'Modelo '):
                            if k in data and isinstance(data.get(k), str):
                                model = data.get(k).strip(); break
                        for k in ('Tamaño', 'Tamaño *', 'Tamano', 'tamaño', 'tamanio', 'Tamaño '):
                            if k in data and isinstance(data.get(k), str):
                                size = data.get(k).strip(); break
                        for k in ('Precio', 'precio', 'price', 'valor'):
                            if k in data:
                                try:
                                    price = float(data.get(k) or 0.0)
                                    break
                                except Exception:
                                    try:
                                        price = float(str(data.get(k)).replace('$','').replace(',','').strip())
                                        break
                                    except Exception:
                                        pass
                    # fallback: use id as model/size if not present
                    if not model:
                        model = str(getattr(r, 'id', ''))
                    if not size:
                        size = ''
                    if price is None:
                        price = 0.0
                    mapping.setdefault(model, []).append((size, price, getattr(r, 'id', None)))

                logger.debug("_load_bases_separadores_from_product: mapping keys before populate=%r", list(mapping.keys()))
                # populate combo boxes
                try:
                    self.cbo_soporte_item.clear()
                    self.cbo_soporte_item.addItem('-- seleccione --', None)
                    for mod, lst in mapping.items():
                        # store model name as data; actual sizes will be loaded into size combo
                        self.cbo_soporte_item.addItem(str(mod), str(mod))
                    # store mapping for later lookup
                    self._bases_mapping = mapping
                    # connect handler
                    try:
                        self.cbo_soporte_item.currentIndexChanged.connect(self._on_soporte_item_changed)
                        self.cbo_soporte_size.currentIndexChanged.connect(self._on_soporte_size_changed)
                    except Exception:
                        pass
                    logger.debug("_load_bases_separadores_from_product: populated %d models", len(mapping))
                except Exception:
                    pass
        except Exception:
            return

    def _on_soporte_item_changed(self, index: int) -> None:
        try:
            val = self.cbo_soporte_item.itemData(index)
        except Exception:
            val = None
        try:
            self.cbo_soporte_size.clear()
            self.cbo_soporte_size.addItem('-- seleccione --', None)
            if not val:
                return
            lst = getattr(self, '_bases_mapping', {}).get(str(val)) or []
            for size, price, oid in lst:
                self.cbo_soporte_size.addItem(str(size), oid)
        except Exception:
            pass

    def _on_soporte_size_changed(self, index: int) -> None:
        try:
            oid = self.cbo_soporte_size.itemData(index)
        except Exception:
            oid = None
        price = 0.0
        try:
            if oid and getattr(self, '_bases_mapping', None):
                # find price in mapping
                for mod, lst in getattr(self, '_bases_mapping', {}).items():
                    for size, p, idv in lst:
                        if idv == oid:
                            price = float(p or 0.0); break
                    if price:
                        break
        except Exception:
            price = 0.0
        # update label in a separate try block
        try:
            if price:
                self.lbl_soporte_precio.setText(f"${float(price):.2f}")
            else:
                self.lbl_soporte_precio.setText("")
        except Exception:
            pass

    def _load_luces_from_product(self, product_identifier: int | dict | None) -> None:
        """Cargar tipos de luz desde la tabla 'Luces' y asignar precios a los checkboxes/spinboxes.

        La tabla tiene columnas como 'Tipo de luz' y 'Precio'. Pobla `self.cbo_luz_tipo` y
        ajusta `self.spin_led_precio`, `self.spin_neon_m_precio`, `self.spin_ceo_precio`, `self.spin_neon_b_precio`
        según los ids/labels encontrados.
        """
        sf = getattr(self, 'session_factory', None)
        if sf is None:
            return
        try:
            with sf() as s:
                pid = None
                if isinstance(product_identifier, dict):
                    pid_val = product_identifier.get('id')
                else:
                    pid_val = product_identifier
                try:
                    pid = int(pid_val) if pid_val is not None else None
                except Exception:
                    pid = None
                if not pid:
                    return
                tables = _repo.get_product_parameter_tables(s, pid, include_inactive=False)
                candidate = None
                # prefer exact 'luces' match, otherwise 'luz'
                for t in (tables or []):
                    dn = (t.get('display_name') or '').lower()
                    tn = (t.get('table_name') or '').lower()
                    if 'luces' in dn or 'luces' in tn:
                        candidate = t; break
                if candidate is None:
                    for t in (tables or []):
                        dn = (t.get('display_name') or '').lower()
                        tn = (t.get('table_name') or '').lower()
                        if 'luz' in dn or 'luz' in tn:
                            candidate = t; break
                if not candidate:
                    logger.debug("_load_luces_from_product: no candidate table found for pid=%r", pid)
                    return
                logger.debug("_load_luces_from_product: using table %r", candidate)
                from ..models import ProductParameterValue
                rows = (
                    s.query(ProductParameterValue)
                    .filter(ProductParameterValue.parameter_table_id == candidate.get('id'))
                    .filter(ProductParameterValue.is_active == True)
                    .all()
                )
                logger.debug("_load_luces_from_product: fetched %d rows from table id=%r", len(rows or []), candidate.get('id'))
                import json
                # populate cbo_luz_tipo
                try:
                    self.cbo_luz_tipo.clear()
                    self.cbo_luz_tipo.addItem('-- seleccione --', None)
                except Exception:
                    pass

                def _norm(s: str) -> str:
                    if not s:
                        return ''
                    s = s.lower().strip()
                    for a,b in (('á','a'),('é','e'),('í','i'),('ó','o'),('ú','u'),('ñ','n')):
                        s = s.replace(a,b)
                    # keep alphanum and spaces
                    import re
                    s = re.sub(r'[^a-z0-9\s]','', s)
                    s = re.sub(r'\s+',' ', s).strip()
                    return s

                # mapping normalized label -> (label, price, id)
                label_map = {}
                # collect colors and build label_map
                colors_found = []
                # Try to find a dedicated 'Color de Luz' table for this product
                try:
                    color_table = None
                    tables_all = _repo.get_product_parameter_tables(s, pid, include_inactive=False)
                    for t in (tables_all or []):
                        dn = (t.get('display_name') or '').lower()
                        tn = (t.get('table_name') or '').lower()
                        if 'color' in dn and 'luz' in dn:
                            color_table = t; break
                    if color_table is not None:
                        from ..models import ProductParameterValue as PPV
                        color_rows = (
                            s.query(PPV)
                            .filter(PPV.parameter_table_id == color_table.get('id'))
                            .filter(PPV.is_active == True)
                            .all()
                        )
                        # populate combo directly from this table
                        try:
                            self.cbo_luz_color.clear()
                            self.cbo_luz_color.addItem('-- seleccione --', None)
                            for cr in (color_rows or []):
                                try:
                                    import json as _json
                                    d = _json.loads(cr.row_data_json or '{}')
                                except Exception:
                                    d = {}
                                cv = d.get('Color') or d.get('color')
                                if cv:
                                    self.cbo_luz_color.addItem(str(cv), None)
                        except Exception:
                            pass
                except Exception:
                    color_table = None

                for r in (rows or []):
                    try:
                        data = json.loads(r.row_data_json or '{}')
                    except Exception:
                        data = {}
                    label = None
                    price = None
                    if isinstance(data, dict):
                        for k in ('Tipo de luz', 'Tipo de Luz', 'Tipo', 'tipo', 'tipo_luz', 'Tipo Luz'):
                            v = data.get(k)
                            if isinstance(v, str) and v.strip():
                                label = v.strip(); break
                        for k in ('Precio', 'precio', 'price', 'valor'):
                            v = data.get(k)
                            if v is None:
                                continue
                            try:
                                price = float(v)
                                break
                            except Exception:
                                try:
                                    price = float(str(v).replace('$','').replace(',','').strip())
                                    break
                                except Exception:
                                    continue
                    if not label:
                        label = str(getattr(r, 'id', ''))
                    if price is None:
                        price = 0.0
                    n = _norm(label)
                    # try to detect explicit unit from the row data
                    unit = None
                    try:
                        for uk in ('Unidad', 'unidad', 'Unit', 'unit', 'medida', 'unidad_medida', 'medida_unidad'):
                            u = data.get(uk)
                            if isinstance(u, str) and u.strip():
                                unit = u.strip().lower()
                                break
                    except Exception:
                        unit = None
                    # heuristic fallback based on label: strips/tiras/manguera -> meter, otherwise m2
                    try:
                        if not unit:
                            if any(x in n for x in ('tira', 'strip', 'manguera', 'tubo', 'rollo', 'metro', 'ml', 'mt', 'lineal')):
                                unit = 'm'
                            else:
                                unit = 'm2'
                    except Exception:
                        unit = unit or 'm2'
                    label_map[n] = (label, float(price), getattr(r, 'id', None), unit)
                    # if dedicated color table wasn't found, try to collect color field from this row
                    try:
                        if color_table is None:
                            for ck in ('Color', 'color', 'Color de luz', 'color_luz'):
                                cv = data.get(ck)
                                if isinstance(cv, str) and cv.strip():
                                    colors_found.append(cv.strip())
                                    break
                    except Exception:
                        pass

                # populate color combo from product table values (unique, preserve order)
                # If color_table existed we already populated the combo. Only populate from collected colors if combo is empty
                try:
                    if self.cbo_luz_color.count() <= 1 and colors_found:
                        seen = set()
                        self.cbo_luz_color.clear()
                        self.cbo_luz_color.addItem('-- seleccione --', None)
                        for c in colors_found:
                            if not c:
                                continue
                            if c in seen:
                                continue
                            seen.add(c)
                            try:
                                self.cbo_luz_color.addItem(str(c), None)
                            except Exception:
                                pass
                except Exception:
                    pass

                # populate cbo_luz_tipo with the discovered label_map entries and store price/unit in itemData
                try:
                    if getattr(self, 'cbo_luz_tipo', None) is not None:
                        try:
                            self.cbo_luz_tipo.clear()
                            self.cbo_luz_tipo.addItem('-- seleccione --', None)
                        except Exception:
                            pass
                        for n, (label, price, oid, unit) in label_map.items():
                            try:
                                # store a tuple (pv_id, price, unit) in itemData for later retrieval
                                self.cbo_luz_tipo.addItem(str(label), (oid, float(price), unit))
                            except Exception:
                                try:
                                    self.cbo_luz_tipo.addItem(str(label))
                                except Exception:
                                    pass
                except Exception:
                    pass

                # ensure posicion options exist: if EAV/db didn't populate them, provide defaults
                try:
                    # Force the posicionamiento options to the requested set
                    defaults = [
                        'Borde Frente', 'Borde Detras',
                        'Retroiluminado Frente', 'Retroiluminado Detras'
                    ]
                    self.cbo_pos_luz.clear()
                    self.cbo_pos_luz.addItem('-- seleccione --', None)
                    for d in defaults:
                        self.cbo_pos_luz.addItem(d, None)
                except Exception:
                    pass

                # For compatibility with older logic, we set a generic _luz_price_val only if a single
                # generic price is present in label_map entries. Prefer leaving per-item price in combo.
                try:
                    # Clear any per-checkbox attrs no longer used
                    for attr in ('_led_price_val', '_neon_m_price_val', '_ceo_price_val', '_neon_b_price_val'):
                        try:
                            if hasattr(self, attr):
                                delattr(self, attr)
                        except Exception:
                            pass
                    # No further per-checkbox label updates needed; combo will show price in UI
                except Exception:
                    pass

                        # cbo_luz_tipo and spin_luz_precio were removed; labels are already set above
        except Exception:
            return

    def _load_regulador_from_product(self, product_identifier: int | dict | None) -> None:
        """Carga la tabla 'Regulador' (Tipo de AMP y Precio) en `cbo_reg_amp` y muestra precio en `lbl_reg_precio`."""
        sf = getattr(self, 'session_factory', None)
        if sf is None:
            return
        try:
            with sf() as s:
                pid = None
                if isinstance(product_identifier, dict):
                    pid_val = product_identifier.get('id')
                else:
                    pid_val = product_identifier
                try:
                    pid = int(pid_val) if pid_val is not None else None
                except Exception:
                    pid = None
                if not pid:
                    return
                tables = _repo.get_product_parameter_tables(s, pid, include_inactive=False)
                candidate = None
                for t in (tables or []):
                    dn = (t.get('display_name') or '').lower()
                    tn = (t.get('table_name') or '').lower()
                    if 'regulador' in dn or 'regulador' in tn:
                        candidate = t; break
                if not candidate:
                    return
                from ..models import ProductParameterValue
                rows = (
                    s.query(ProductParameterValue)
                    .filter(ProductParameterValue.parameter_table_id == candidate.get('id'))
                    .filter(ProductParameterValue.is_active == True)
                    .all()
                )
                import json
                try:
                    self.cbo_reg_amp.clear()
                    self.cbo_reg_amp.addItem('-- seleccione --', None)
                except Exception:
                    pass
                # store mapping id -> precio
                self._reg_map = {}
                for r in (rows or []):
                    try:
                        data = json.loads(r.row_data_json or '{}')
                    except Exception:
                        data = {}
                    amp = None
                    price = None
                    if isinstance(data, dict):
                        amp = data.get('Tipo de AMP') or data.get('Tipo AMP') or data.get('Amp') or data.get('tipo_amp')
                        p = data.get('Precio') or data.get('precio') or data.get('Price') or data.get('precio')
                        try:
                            if p is not None:
                                price = float(p)
                        except Exception:
                            try:
                                price = float(str(p).replace('$','').replace(',','').strip())
                            except Exception:
                                price = None
                    if amp is None:
                        amp = str(getattr(r,'id',None))
                    try:
                        self.cbo_reg_amp.addItem(str(amp), getattr(r,'id',None))
                        self._reg_map[getattr(r,'id',None)] = price if price is not None else 0.0
                    except Exception:
                        pass
                # connect selection
                try:
                    def _on_reg(idx:int) -> None:
                        try:
                            oid = self.cbo_reg_amp.itemData(idx)
                        except Exception:
                            oid = None
                        price = None
                        if oid is not None and hasattr(self, '_reg_map'):
                            price = self._reg_map.get(oid)
                        try:
                            if price is None:
                                self.lbl_reg_precio.setText("")
                            else:
                                self.lbl_reg_precio.setText(f"${float(price):.2f}")
                        except Exception:
                            pass
                    self.cbo_reg_amp.currentIndexChanged.connect(_on_reg)
                except Exception:
                    pass
        except Exception:
            return

    def _load_tipo_corporeo_from_product(self, product_identifier: int | dict | None) -> None:
        """Cargar dinámicamente los tipos de Corporeo como checkboxes con su precio por m2.

        Busca una tabla de parámetros cuyo display_name o table_name contenga 'tipo' y 'corp' o 'corporeo'.
        Para cada fila activa crea un QCheckBox y un QLabel con el precio y los añade a
        `self.tipo_corp_layout`. Guarda referencias en `self.tipo_corp_checkboxes`.
        """
        sf = getattr(self, 'session_factory', None)
        if sf is None:
            return
        try:
            with sf() as s:
                logger.debug("_load_tipo_corporeo_from_product start product_identifier=%r", product_identifier)
                # normalize id if provided
                pid = None
                if isinstance(product_identifier, dict):
                    pid_val = product_identifier.get('id')
                else:
                    pid_val = product_identifier
                try:
                    pid = int(pid_val) if pid_val is not None else None
                except Exception:
                    pid = None

                tipo_tables = []
                if pid:
                    # prefer product-specific parameter tables
                    tables = _repo.get_product_parameter_tables(s, pid, include_inactive=False)
                    try:
                        logger.debug("_load_tipo_corporeo_from_product: product-specific tables=%r", [(t.get('id'), t.get('display_name'), t.get('table_name')) for t in (tables or [])])
                    except Exception:
                        logger.debug("_load_tipo_corporeo_from_product: product-specific tables fetched (unable to format)")
                    for t in (tables or []):
                        tn = (t.get('table_name') or '').lower()
                        dn = (t.get('display_name') or '').lower()
                        if ('tipo' in dn and ('corp' in dn or 'corporeo' in dn)) or ('tipo' in tn and ('corp' in tn or 'corporeo' in tn)):
                            tipo_tables.append(t)
                    if not tipo_tables:
                        for t in (tables or []):
                            dn = (t.get('display_name') or '').lower()
                            if 'corp' in dn or 'corporeo' in dn:
                                tipo_tables.append(t)
                else:
                    # global search: inspect ProductParameterTable entries directly
                    from ..models import ProductParameterTable
                    candidates = (
                        s.query(ProductParameterTable)
                        .filter(ProductParameterTable.is_active == True)
                        .all()
                    )
                    logger.debug("_load_tipo_corporeo_from_product: global candidate tables=%r", [(getattr(t,'id',None), getattr(t,'display_name',None)) for t in (candidates or [])])
                    for t in (candidates or []):
                        tn = (getattr(t, 'table_name', '') or '').lower()
                        dn = (getattr(t, 'display_name', '') or '').lower()
                        if ('tipo' in dn and ('corp' in dn or 'corporeo' in dn)) or ('tipo' in tn and ('corp' in tn or 'corporeo' in tn)):
                            tipo_tables.append({'id': getattr(t, 'id', None), 'display_name': getattr(t, 'display_name', None), 'table_name': getattr(t, 'table_name', None)})
                    if not tipo_tables:
                        for t in (candidates or []):
                            dn = (getattr(t, 'display_name', '') or '').lower()
                            if 'corp' in dn or 'corporeo' in dn:
                                tipo_tables.append({'id': getattr(t, 'id', None), 'display_name': getattr(t, 'display_name', None), 'table_name': getattr(t, 'table_name', None)})
                try:
                    logger.debug("_load_tipo_corporeo_from_product: tipo_tables candidates=%r", tipo_tables)
                except Exception:
                    logger.debug("_load_tipo_corporeo_from_product: tipo_tables candidates (unprintable)")
                if not tipo_tables:
                    # nothing to load
                    logger.debug("_load_tipo_corporeo_from_product: no tipo corporeo table found for product %r", pid)
                    return
                table = tipo_tables[0]
                try:
                    logger.debug("_load_tipo_corporeo_from_product: using table id=%r display=%r table_name=%r", table.get('id'), table.get('display_name'), table.get('table_name'))
                except Exception:
                    logger.debug("_load_tipo_corporeo_from_product: using table (unprintable)")
                from ..models import ProductParameterValue
                rows = (
                    s.query(ProductParameterValue)
                    .filter(ProductParameterValue.parameter_table_id == table['id'])
                    .filter(ProductParameterValue.is_active == True)
                    .all()
                )
                try:
                    logger.debug("_load_tipo_corporeo_from_product: rows found=%d", len(rows or []))
                except Exception:
                    logger.debug("_load_tipo_corporeo_from_product: rows fetched (count unavailable)")
                import json
                # log samples to help debug incorrect labels
                try:
                    sample_jsons = []
                    for r in (rows or [])[:3]:
                        try:
                            sample_jsons.append((getattr(r,'id', None), (r.row_data_json or '')[:400]))
                        except Exception:
                            sample_jsons.append((getattr(r,'id', None), '<unreadable>'))
                    logger.debug("_load_tipo_corporeo_from_product: sample rows json (up to 3)=%r", sample_jsons)
                except Exception:
                    pass
                # clear existing widgets in layout and remove items
                try:
                    # remove widgets from layout
                    if hasattr(self, 'tipo_corp_layout') and self.tipo_corp_layout is not None:
                        while self.tipo_corp_layout.count():
                            item = self.tipo_corp_layout.takeAt(0)
                            if item is None:
                                break
                            w = item.widget()
                            if w is not None:
                                try:
                                    w.setParent(None)
                                except Exception:
                                    pass
                    # delete previous widgets if still referenced
                    for cb, lbl, oid in list(getattr(self, 'tipo_corp_checkboxes', []) or []):
                        try:
                            cb.stateChanged.disconnect()
                        except Exception:
                            pass
                        try:
                            cb.deleteLater()
                        except Exception:
                            pass
                        try:
                            lbl.deleteLater()
                        except Exception:
                            pass
                    self.tipo_corp_checkboxes = []
                except Exception:
                    self.tipo_corp_checkboxes = []

                for idx, r in enumerate(rows or []):
                    try:
                        data = json.loads(r.row_data_json or '{}')
                    except Exception:
                        data = {}
                    label = None
                    price = None
                    if isinstance(data, dict):
                        # label keys
                        for k in ('Tipo de Corporeo', 'Tipo', 'tipo', 'name', 'Nombre', 'nombre', 'label', 'display'):
                            v = data.get(k)
                            if isinstance(v, str) and v.strip():
                                label = v.strip(); break
                        # price keys
                        for k in ('Precio', 'precio', 'price', 'precio_m2', 'precio_metro', 'valor'):
                            v = data.get(k)
                            if v is None:
                                continue
                            try:
                                price = float(v)
                                break
                            except Exception:
                                try:
                                    sstr = str(v).replace('$', '').replace(',', '').strip()
                                    price = float(sstr)
                                    break
                                except Exception:
                                    continue
                    if not label:
                        label = str(getattr(r, 'id', ''))
                    if price is None:
                        price = 0.0
                    # create checkbox and price label
                    cb = QCheckBox(str(label))
                    cb.setProperty('opt_id', getattr(r, 'id', None))
                    price_lbl = QLabel(f"${float(price):.2f}")
                    price_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    # connect state change to recalc
                    try:
                        cb.stateChanged.connect(lambda s, _cb=cb: self._recalc())
                    except Exception:
                        pass
                    # place in grid: two columns per item (checkbox then label), wrapping
                    try:
                        col_count = 2
                        # compute row/col based on existing children
                        existing = len(self.tipo_corp_checkboxes)
                        col = (existing * 2) % 4  # allow two items per row (checkbox+label counts as 2 columns)
                        row = (existing * 2) // 4
                        # add checkbox and label side by side
                        try:
                            self.tipo_corp_layout.addWidget(cb, row, col)
                            self.tipo_corp_layout.addWidget(price_lbl, row, col + 1)
                        except Exception:
                            # fallback: add sequentially
                            self.tipo_corp_layout.addWidget(cb)
                            self.tipo_corp_layout.addWidget(price_lbl)
                    except Exception:
                        try:
                            self.tipo_corp_layout.addWidget(cb)
                            self.tipo_corp_layout.addWidget(price_lbl)
                        except Exception:
                            pass
                    self.tipo_corp_checkboxes.append((cb, price_lbl, getattr(r, 'id', None)))
                logger.debug("_load_tipo_corporeo_from_product: loaded %d tipos from table id=%r", len(self.tipo_corp_checkboxes), table.get('id'))
        except Exception:
            logger.exception("_load_tipo_corporeo_from_product failed")


    def _on_material_changed(self, index: int) -> None:
        """Poblar `cbo_espesor` con los espesores relacionados al material seleccionado.

        Busca tablas hijas de la tabla de materiales y filtra las filas cuyo campo
        de relación (relationship_column) apunte al id de la fila de material seleccionada.
        Si no se encuentra relationship_column, intenta emparejar usando claves comunes
        como 'material', 'material_id', 'parent_id', etc., dentro de `row_data_json`.
        """
        try:
            try:
                mat_oid = self.cbo_material.itemData(index)
            except Exception:
                mat_oid = None
            logger.debug("_on_material_changed: index=%r mat_oid=%r", index, mat_oid)
            try:
                self.cbo_espesor.clear()
                self.cbo_espesor.addItem('-- seleccione --', None)
            except Exception:
                pass
            if not mat_oid:
                return
            sf = getattr(self, 'session_factory', None)
            if sf is None:
                return
            with sf() as s:
                from ..models import ProductParameterTable, ProductParameterValue
                import json
                # load material row and its JSON
                try:
                    mat_row = s.get(ProductParameterValue, int(mat_oid))
                except Exception:
                    mat_row = None
                mat_data = {}
                try:
                    if mat_row:
                        mat_data = json.loads(mat_row.row_data_json or '{}')
                except Exception:
                    mat_data = {}

                ids_to_match = {str(mat_oid)}
                if isinstance(mat_data, dict):
                    for pk in ('id', 'ID', 'Id'):
                        v = mat_data.get(pk)
                        if v is not None:
                            ids_to_match.add(str(v))

                # explicit espesor ids referenced from material (material -> espesor)
                explicit_esp = set()
                if isinstance(mat_data, dict):
                    for fk in ('id_espesor', 'idEspesor', 'espesor_id', 'id_esp'):
                        v = mat_data.get(fk)
                        if v is not None:
                            try:
                                explicit_esp.add(int(v))
                            except Exception:
                                try:
                                    explicit_esp.add(int(str(v)))
                                except Exception:
                                    pass

                # search espesor parameter tables (by name/display)
                esp_tables = (
                    s.query(ProductParameterTable)
                    .filter(ProductParameterTable.is_active == True)
                    .filter(
                        (ProductParameterTable.display_name.ilike('%espesor%')) |
                        (ProductParameterTable.table_name.ilike('%espes%'))
                    )
                    .order_by(ProductParameterTable.display_name)
                    .all()
                )

                esp_opts = []
                for et in (esp_tables or []):
                    logger.debug("_on_material_changed: inspecting esp table id=%r name=%r", getattr(et, 'id', None), getattr(et, 'display_name', None))
                    try:
                        rows = (
                            s.query(ProductParameterValue)
                            .filter(ProductParameterValue.parameter_table_id == et.id)
                            .filter(ProductParameterValue.is_active == True)
                            .all()
                        )
                        for r in (rows or []):
                            try:
                                data = json.loads(r.row_data_json or '{}')
                            except Exception:
                                data = {}
                            matched = False
                            # prefer explicit id field on espesor rows that point to material
                            if isinstance(data, dict):
                                for ck in ('id_materiales', 'id_material', 'material_id', 'id_materia'):
                                    if ck in data:
                                        try:
                                            v = data.get(ck)
                                            if v is not None and any(str(v) == mid for mid in ids_to_match):
                                                matched = True; break
                                        except Exception:
                                            pass
                            # also accept if esp row id is explicitly referenced by material
                            if not matched:
                                try:
                                    if int(getattr(r, 'id', 0)) in explicit_esp:
                                        matched = True
                                except Exception:
                                    pass

                            if matched:
                                # extract espesor label
                                label = None
                                if isinstance(data, dict):
                                    for k in ('Espesor', 'espesor', 'espesor_mm', 'Numero espesor'):
                                        vv = data.get(k)
                                        if vv is None:
                                            continue
                                        if isinstance(vv, (str, int, float)):
                                            label = str(vv).strip(); break
                                if not label:
                                    label = str(getattr(r, 'id', ''))
                                esp_opts.append((label, getattr(r, 'id', None)))
                                logger.debug("_on_material_changed: matched esp row id=%r label=%r", getattr(r, 'id', None), label)
                    except Exception:
                        pass

                # also add explicit espesor rows referenced by material if not already included
                for eid in list(explicit_esp):
                    try:
                        if not any((oid == eid) for _, oid in esp_opts):
                            erv = s.get(ProductParameterValue, int(eid))
                            if erv:
                                try:
                                    ed = json.loads(erv.row_data_json or '{}')
                                except Exception:
                                    ed = {}
                                elab = None
                                if isinstance(ed, dict):
                                    for k in ('Espesor', 'espesor', 'espesor_mm', 'Numero espesor'):
                                        vv = ed.get(k)
                                        if vv is None:
                                            continue
                                        if isinstance(vv, (str, int, float)):
                                            elab = str(vv).strip(); break
                                if not elab:
                                    elab = str(getattr(erv, 'id', ''))
                                esp_opts.append((elab, getattr(erv, 'id', None)))
                    except Exception:
                        pass

                # populate combo
                try:
                    if esp_opts:
                        self.cbo_espesor.clear()
                        self.cbo_espesor.addItem('-- seleccione --', None)
                        for lbl, oid in esp_opts:
                            self.cbo_espesor.addItem(str(lbl), oid)
                        logger.debug("_on_material_changed: populated %d espesor options", len(esp_opts))
                        # optionally select first actual espesor option
                        try:
                            if self.cbo_espesor.count() > 1:
                                # keep index 0 as placeholder, do not auto-select
                                pass
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            return

    def _area_perimetro(self) -> Tuple[float, float]:
        try:
            # Si el usuario usó diámetro considerarlo (diámetro en mm)
            diam = float(self.spin_diam.value() or 0.0)
            if diam > 0.0:
                # convertir a metros
                r = (diam / 1000.0) / 2.0
                area = 3.141592653589793 * (r * r)
                perim = 2.0 * 3.141592653589793 * r
                return area, perim

            alto = max(self.spin_alto.value(), 0.0) / 100.0
            ancho = max(self.spin_ancho.value(), 0.0) / 100.0
            area = alto * ancho
            perim = 2.0 * (alto + ancho)
            return area, perim
        except Exception:
            return 0.0, 0.0

    def _on_espesor_changed(self, index: int) -> None:
        """Al cambiar el espesor seleccionado, intentar cargar su precio desde la fila de parámetros.

        Busca claves comunes como 'Precio', 'precio', 'Price', 'price' en el JSON de la fila
        y establece `self.spin_esp_precio` con ese valor (si se encuentra).
        """
        try:
            try:
                esp_oid = self.cbo_espesor.itemData(index)
            except Exception:
                esp_oid = None
            logger.debug("_on_espesor_changed: index=%r esp_oid=%r", index, esp_oid)
            if not esp_oid:
                return
            sf = getattr(self, 'session_factory', None)
            if sf is None:
                return
            with sf() as s:
                from ..models import ProductParameterValue
                import json
                try:
                    pv = s.get(ProductParameterValue, int(esp_oid))
                except Exception:
                    pv = None
                price_val = None
                if pv:
                    try:
                        data = json.loads(pv.row_data_json or '{}')
                    except Exception:
                        data = {}
                    if isinstance(data, dict):
                        for k in ('Precio', 'precio', 'Price', 'price', 'valor', 'Valor'):
                            v = data.get(k)
                            if v is None:
                                continue
                            try:
                                price_val = float(v)
                                break
                            except Exception:
                                # try to parse strings with currency or commas
                                try:
                                    sstr = str(v).replace('$', '').replace(',', '').strip()
                                    price_val = float(sstr)
                                    break
                                except Exception:
                                    continue
                # set label and internal value
                try:
                    if price_val is not None:
                        self._esp_precio_val = float(price_val)
                        try:
                            self.lbl_esp_precio.setText(f"${float(price_val):.2f}")
                        except Exception:
                            self.lbl_esp_precio.setText(str(price_val))
                except Exception:
                    pass
        except Exception:
            pass

    def _load_initial_payload(self, payload: dict) -> None:
        """Cargar valores desde un payload previamente guardado.

        El método intenta asignar los valores presentes en el payload a los widgets
        correspondientes. Es defensivo: ignora keys desconocidas y no lanza si falla.
        """
        try:
            import json as _json
            print(f"[DEBUG CorporeoDialog] _load_initial_payload llamado con tipo={type(payload)} keys={list(payload.keys()) if isinstance(payload, dict) else 'n/a'}")
            try:
                print(f"[DEBUG CorporeoDialog] Payload crudo: {_json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else payload}")
            except Exception:
                pass
        except Exception:
            pass
        try:
            if not isinstance(payload, dict):
                return
            # Restaurar precios finales y tasas si están presentes en el payload previo
            try:
                precio_final_usd = payload.get('precio_final_usd')
                if precio_final_usd is not None:
                    self._last_precio_final_usd = float(precio_final_usd)
                    self.lbl_precio_final_corporeo_usd.setText(f"{self._last_precio_final_usd:.2f}")
            except Exception:
                pass
            try:
                precio_final_bs = payload.get('precio_final_bs')
                if precio_final_bs is not None:
                    self._last_precio_final_bs = float(precio_final_bs)
            except Exception:
                pass
            try:
                totals_block = payload.get('totals') if isinstance(payload.get('totals'), dict) else {}
            except Exception:
                totals_block = {}
            try:
                tasa_corp = payload.get('tasa_corporeo', totals_block.get('tasa_corporeo'))
                if tasa_corp is not None:
                    self._last_tasa_corporeo = float(tasa_corp)
            except Exception:
                pass
            try:
                tasa_bcv_val = payload.get('tasa_bcv', totals_block.get('tasa_bcv'))
                if tasa_bcv_val is not None:
                    self._last_tasa_bcv = float(tasa_bcv_val)
            except Exception:
                pass
            # nombre y descripcion
            try:
                if 'nombre' in payload and hasattr(self, 'txt_name'):
                    self.txt_name.setText(str(payload.get('nombre') or ''))
            except Exception:
                pass
            try:
                # Do NOT overwrite the user's free-text description with the generated
                # presentation description. Use 'descripcion_user' (the user's original
                # description) if present. This preserves any text the user typed.
                if 'descripcion_user' in payload and hasattr(self, 'txt_desc'):
                    self.txt_desc.setPlainText(str(payload.get('descripcion_user') or ''))
            except Exception:
                pass

            # medidas
            try:
                med = payload.get('medidas') or {}
                if isinstance(med, dict):
                    if hasattr(self, 'spin_alto') and 'alto_cm' in med:
                        self.spin_alto.setValue(float(med.get('alto_cm') or 0.0))
                    if hasattr(self, 'spin_ancho') and 'ancho_cm' in med:
                        self.spin_ancho.setValue(float(med.get('ancho_cm') or 0.0))
                    if hasattr(self, 'spin_diam') and 'diam_mm' in med:
                        self.spin_diam.setValue(float(med.get('diam_mm') or 0.0))
            except Exception:
                pass

            # cortes: checkboxes by opt_id and combo
            try:
                cortes = payload.get('cortes') or []
                if cortes and getattr(self, 'cut_checkboxes', None):
                    # map by opt_id where possible
                    for c in cortes:
                        oid = c.get('opt_id')
                        # Buscar por 'tipo' (nuevo) o 'label' (legacy) para compatibilidad
                        tipo_texto = c.get('tipo') or c.get('label')
                        for cb in self.cut_checkboxes:
                            try:
                                if oid is not None and cb.property('opt_id') == oid:
                                    cb.setChecked(True)
                                    break
                                # fallback by text match (tipo o label)
                                if tipo_texto and (cb.text() or '').strip() == str(tipo_texto).strip():
                                    cb.setChecked(True)
                                    break
                            except Exception:
                                pass
                else:
                    # If payload contains cortes but cut_checkboxes is empty, attempt to
                    # (re)load cut types using data from payload: prefer using explicit opt_id
                    try:
                        if cortes and (not getattr(self, 'cut_checkboxes', None)):
                            # collect opt_ids referenced in payload
                            opt_ids = [int(c.get('opt_id')) for c in cortes if c.get('opt_id') is not None]
                            sf = getattr(self, 'session_factory', None)
                            if sf and opt_ids:
                                # find first existing ProductParameterValue to discover its parameter_table_id
                                with sf() as s:
                                    from ..models import ProductParameterValue
                                    first = None
                                    for oid in opt_ids:
                                        try:
                                            pv = s.get(ProductParameterValue, int(oid))
                                            if pv:
                                                first = pv
                                                break
                                        except Exception:
                                            continue
                                    if first is not None:
                                        table_id = getattr(first, 'parameter_table_id', None)
                                        if table_id:
                                            # load all active rows from that parameter table and populate options
                                            rows = (
                                                s.query(ProductParameterValue)
                                                .filter(ProductParameterValue.parameter_table_id == table_id)
                                                .filter(ProductParameterValue.is_active == True)
                                                .all()
                                            )
                                            opts = []
                                            import json as _json
                                            for r in rows:
                                                try:
                                                    data = _json.loads(r.row_data_json or '{}')
                                                except Exception:
                                                    data = {}
                                                label = None
                                                if isinstance(data, dict):
                                                    for k in ('Tipo de Corte','Tipo','tipo','name','nombre','label','display','descripcion'):
                                                        v = data.get(k)
                                                        if isinstance(v, str) and v.strip():
                                                            label = v.strip(); break
                                                    if not label:
                                                        # accept numeric or other values
                                                        for k,v in data.items():
                                                            if isinstance(v, (str, int, float)):
                                                                label = str(v); break
                                                if not label:
                                                    label = str(getattr(r,'id', None) or '')
                                                opts.append((label, getattr(r, 'id', None)))
                                            try:
                                                if opts:
                                                    self._set_cut_options_from_list(opts)
                                                    # After dynamically creating the checkboxes, re-apply
                                                    # the payload selection so the dialog reflects the
                                                    # user's previous choices (opt_id or label).
                                                    try:
                                                        for c in cortes:
                                                            try:
                                                                oid = c.get('opt_id')
                                                                lbl = c.get('tipo') or c.get('label')
                                                                for cb in getattr(self, 'cut_checkboxes', []) or []:
                                                                    try:
                                                                        if oid is not None and cb.property('opt_id') == oid:
                                                                            cb.setChecked(True); break
                                                                        if lbl and (cb.text() or '').strip() == str(lbl).strip():
                                                                            cb.setChecked(True); break
                                                                    except Exception:
                                                                        pass
                                                            except Exception:
                                                                pass
                                                    except Exception:
                                                        pass
                                            except Exception:
                                                pass
                    except Exception:
                        pass
                # if combo has an explicit value
                try:
                    cbo_text = None
                    if isinstance(payload.get('cortes'), list):
                        for c in payload.get('cortes'):
                            if c.get('from_combo'):
                                cbo_text = c.get('tipo') or c.get('label')
                                break
                    if cbo_text and hasattr(self, 'cbo_corte'):
                        # try to select a matching item
                        for i in range(self.cbo_corte.count()):
                            try:
                                if str(self.cbo_corte.itemText(i)).strip() == str(cbo_text).strip():
                                    self.cbo_corte.setCurrentIndex(i)
                                    break
                            except Exception:
                                pass
                except Exception:
                    pass
            except Exception:
                pass

            # material / espesor selection by id or label
            try:
                mat = payload.get('material') or {}
                if isinstance(mat, dict) and hasattr(self, 'cbo_material'):
                    mid = mat.get('id')
                    mlabel = mat.get('label')
                    if mid is not None:
                        for i in range(self.cbo_material.count()):
                            try:
                                if self.cbo_material.itemData(i) == mid:
                                    self.cbo_material.setCurrentIndex(i)
                                    break
                            except Exception:
                                pass
                    elif mlabel is not None:
                        for i in range(self.cbo_material.count()):
                            try:
                                if self.cbo_material.itemText(i).strip() == str(mlabel).strip():
                                    self.cbo_material.setCurrentIndex(i)
                                    break
                            except Exception:
                                pass
            except Exception:
                pass

            # silueta price stored in payload (para ediciones sin metadata)
            try:
                silueta_info = payload.get('silueta') if isinstance(payload, dict) else None
                if isinstance(silueta_info, dict):
                    price_m2 = silueta_info.get('price_m2')
                    if price_m2 is not None:
                        self._set_silueta_price(price_m2)
                        try:
                            self._update_silueta_label_visibility()
                        except Exception:
                            pass
            except Exception:
                pass

            # restore base flags (crudo / transparente) if present in payload (global base_color)
            try:
                base_info = payload.get('base_color') or {}
                if isinstance(base_info, dict):
                    if 'crudo' in base_info and hasattr(self, 'chk_base_crudo'):
                        try:
                            self.chk_base_crudo.setChecked(bool(base_info.get('crudo')))
                        except Exception:
                            pass
                    if 'transparente' in base_info and hasattr(self, 'chk_base_transp'):
                        try:
                            self.chk_base_transp.setChecked(bool(base_info.get('transparente')))
                        except Exception:
                            pass
            except Exception:
                pass

            # espesor
            try:
                esp = payload.get('espesor') or {}
                if isinstance(esp, dict) and hasattr(self, 'cbo_espesor'):
                    eid = esp.get('id')
                    elabel = esp.get('label')
                    if eid is not None:
                        for i in range(self.cbo_espesor.count()):
                            try:
                                if self.cbo_espesor.itemData(i) == eid:
                                    self.cbo_espesor.setCurrentIndex(i)
                                    break
                            except Exception:
                                pass
                    elif elabel is not None:
                        for i in range(self.cbo_espesor.count()):
                            try:
                                if self.cbo_espesor.itemText(i).strip() == str(elabel).strip():
                                    self.cbo_espesor.setCurrentIndex(i)
                                    break
                            except Exception:
                                pass
            except Exception:
                pass

            # tipos_corporeo
            try:
                tipos = payload.get('tipos_corporeo') or []
                if tipos and getattr(self, 'tipo_corp_checkboxes', None):
                    for t in tipos:
                        try:
                            tid = t.get('pv_id')
                            lbl = t.get('label')
                            for cb, price_lbl, oid in self.tipo_corp_checkboxes:
                                if oid is not None and tid is not None and oid == tid:
                                    cb.setChecked(True); break
                                if lbl and cb.text().strip() == str(lbl).strip():
                                    cb.setChecked(True); break
                        except Exception:
                            pass
            except Exception:
                pass

            # soporte / bases: try to restore modelo and tamaño
            try:
                soporte = payload.get('soporte') or {}
                if isinstance(soporte, dict) and hasattr(self, 'cbo_soporte_item'):
                    model = soporte.get('model')
                    size = soporte.get('size')
                    matched = False
                    if model is not None:
                        # try match by itemData first
                        try:
                            for i in range(self.cbo_soporte_item.count()):
                                try:
                                    if self.cbo_soporte_item.itemData(i) == model:
                                        self.cbo_soporte_item.setCurrentIndex(i)
                                        matched = True
                                        break
                                except Exception:
                                    pass
                        except Exception:
                            matched = False
                        # fallback: match by visible text
                        if not matched:
                            try:
                                for i in range(self.cbo_soporte_item.count()):
                                    try:
                                        if str(self.cbo_soporte_item.itemText(i)).strip() == str(model).strip():
                                            self.cbo_soporte_item.setCurrentIndex(i)
                                            matched = True
                                            break
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                    # set quantity if present
                    try:
                        qty_val = soporte.get('qty') if isinstance(soporte, dict) else None
                        if qty_val is None:
                            qty_val = soporte.get('cantidad') if isinstance(soporte, dict) else None
                        if qty_val is not None and hasattr(self, 'spin_soporte_qty'):
                            try:
                                self.spin_soporte_qty.setValue(int(qty_val))
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # ensure sizes are populated for the selected model
                    try:
                        if matched:
                            try:
                                # call handler to fill sizes
                                self._on_soporte_item_changed(self.cbo_soporte_item.currentIndex())
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # set size by pv_id or by label
                    try:
                        if size and hasattr(self, 'cbo_soporte_size'):
                            for j in range(self.cbo_soporte_size.count()):
                                try:
                                    if self.cbo_soporte_size.itemData(j) == size or str(self.cbo_soporte_size.itemText(j)).strip() == str(size).strip():
                                        self.cbo_soporte_size.setCurrentIndex(j)
                                        break
                                except Exception:
                                    pass
                    except Exception:
                        pass
            except Exception:
                pass

            # luces
            try:
                l = payload.get('luces') or {}
                if isinstance(l, dict):
                    # Selected types (map to checkboxes by label)
                    sel = l.get('selected') or []
                    for s in sel:
                        try:
                            typ = s.get('type')
                            for chk in (
                                getattr(self, 'chk_led', None),
                                getattr(self, 'chk_neon_m', None),
                                getattr(self, 'chk_ceo', None),
                                getattr(self, 'chk_neon_b', None),
                            ):
                                try:
                                    if chk and str((chk.text() or '')).strip() == str(typ or '').strip():
                                        chk.setChecked(True)
                                        break
                                except Exception:
                                    pass
                        except Exception:
                            pass

                    # color/position selection
                    try:
                        if 'color' in l and hasattr(self, 'cbo_luz_color'):
                            txt = l.get('color')
                            for i in range(self.cbo_luz_color.count()):
                                try:
                                    if str(self.cbo_luz_color.itemText(i)).strip() == str(txt).strip():
                                        self.cbo_luz_color.setCurrentIndex(i)
                                        break
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    # tipo de luz: try to select by pv_id stored in payload (first selected item)
                    try:
                        if hasattr(self, 'cbo_luz_tipo') and isinstance(sel, list) and sel:
                            first = sel[0]
                            pv_id = first.get('pv_id') if isinstance(first, dict) else None
                            label_txt = first.get('type') if isinstance(first, dict) else None
                            if pv_id is not None:
                                # find itemData with matching pv_id
                                for i in range(self.cbo_luz_tipo.count()):
                                    try:
                                        data = self.cbo_luz_tipo.itemData(i)
                                        if isinstance(data, (list, tuple)) and len(data) >= 1 and data[0] == pv_id:
                                            self.cbo_luz_tipo.setCurrentIndex(i)
                                            break
                                    except Exception:
                                        pass
                            elif label_txt:
                                for i in range(self.cbo_luz_tipo.count()):
                                    try:
                                        if str(self.cbo_luz_tipo.itemText(i)).strip() == str(label_txt).strip():
                                            self.cbo_luz_tipo.setCurrentIndex(i)
                                            break
                                    except Exception:
                                        pass
                    except Exception:
                        pass
                    # restore luz posicion into cbo_pos_luz if present
                    try:
                        pos = l.get('posicion')
                        if pos and hasattr(self, 'cbo_pos_luz'):
                            for j in range(self.cbo_pos_luz.count()):
                                try:
                                    if str(self.cbo_pos_luz.itemText(j)).strip() == str(pos).strip():
                                        self.cbo_pos_luz.setCurrentIndex(j)
                                        break
                                except Exception:
                                    pass
                    except Exception:
                        pass
            except Exception:
                pass

            # regulador
            try:
                reg = payload.get('regulador') or {}
                if isinstance(reg, dict) and hasattr(self, 'cbo_reg_amp'):
                    rid = reg.get('id')
                    if rid is not None:
                        for i in range(self.cbo_reg_amp.count()):
                            try:
                                if self.cbo_reg_amp.itemData(i) == rid:
                                    self.cbo_reg_amp.setCurrentIndex(i); break
                            except Exception:
                                pass
                    qty = int(reg.get('qty') or 0)
                    try:
                        if qty and hasattr(self, 'spin_reg_cant'):
                            self.spin_reg_cant.setValue(qty)
                    except Exception:
                        pass
            except Exception:
                pass

            # caja
            try:
                caja = payload.get('caja') or {}
                if isinstance(caja, dict) and bool(caja.get('enabled')):
                    try:
                        if hasattr(self, 'chk_caja'):
                            self.chk_caja.setChecked(True)
                        if hasattr(self, 'cbo_caja_base') and caja.get('base'):
                            for i in range(self.cbo_caja_base.count()):
                                try:
                                    if self.cbo_caja_base.itemText(i).strip() == str(caja.get('base')).strip():
                                        self.cbo_caja_base.setCurrentIndex(i); break
                                except Exception:
                                    pass
                        if hasattr(self, 'cbo_caja_faja') and caja.get('faja'):
                            for i in range(self.cbo_caja_faja.count()):
                                try:
                                    if self.cbo_caja_faja.itemText(i).strip() == str(caja.get('faja')).strip():
                                        self.cbo_caja_faja.setCurrentIndex(i); break
                                except Exception:
                                    pass
                        if hasattr(self, 'spin_caja_pct') and caja.get('pct') is not None:
                            try:
                                self.spin_caja_pct.setValue(float(caja.get('pct') or 0.0))
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass

            # Finally, recalc to reflect loaded values
            try:
                self._recalc()
            except Exception:
                pass
        except Exception:
            pass

    def _recalc(self) -> None:
        try:
            area, perim = self._area_perimetro()
            # update both totals area label and the section area label
            self.lbl_area.setText(f"{area:.4f}")
            try:
                self.lbl_area_section.setText(f"{area:.4f}")
            except Exception:
                pass
            self.lbl_perim.setText(f"{perim:.4f}")

            # Diameter calculation retained for internal use (not shown in UI)
            try:
                if self._is_round_cut():
                    # prefer explicit diameter spinner (mm)
                    diam_mm = float(self.spin_diam.value() or 0.0)
                    if diam_mm <= 0.0:
                        # derive diameter from calculated area using circle formula
                        # area is in m²; diameter (m) = 2 * sqrt(area / pi)
                        try:
                            if area and float(area) > 0.0:
                                import math
                                diam_m = 2.0 * math.sqrt(float(area) / 3.141592653589793)
                                diam_mm = diam_m * 1000.0
                            else:
                                diam_mm = 0.0
                        except Exception:
                            diam_mm = 0.0
                    # diam_mm is calculated but not displayed in UI (label removed)
                else:
                    diam_mm = 0.0
            except Exception:
                diam_mm = 0.0

            # get espesor price from internal attr or from label
            try:
                # prefer compatibility spin_esp_precio if present (tests may set it)
                precio_m2 = 0.0
                if getattr(self, 'spin_esp_precio', None) is not None:
                    try:
                        val = float(self.spin_esp_precio.value() or 0.0)
                    except Exception:
                        val = 0.0
                    # treat zero as "not provided" and fallback to other sources
                    if val and float(val) > 0.0:
                        precio_m2 = float(val)
                    else:
                        # fallback to internal attr or label
                        try:
                            precio_m2 = float(getattr(self, '_esp_precio_val', 0.0) or 0.0)
                        except Exception:
                            precio_m2 = 0.0
                        if not precio_m2:
                            try:
                                txt = (self.lbl_esp_precio.text() or '').replace('$', '').replace(',', '').strip()
                                precio_m2 = float(txt) if txt else 0.0
                            except Exception:
                                precio_m2 = 0.0
                else:
                    # ensure attribute exists or parse label
                    try:
                        precio_m2 = float(getattr(self, '_esp_precio_val', 0.0) or 0.0)
                    except Exception:
                        precio_m2 = 0.0
                    if not precio_m2:
                        try:
                            txt = (self.lbl_esp_precio.text() or '').replace('$', '').replace(',', '').strip()
                            precio_m2 = float(txt) if txt else 0.0
                        except Exception:
                            precio_m2 = 0.0
            except Exception:
                try:
                    txt = (self.lbl_esp_precio.text() or '').replace('$', '').replace(',','').strip()
                    precio_m2 = float(txt) if txt else 0.0
                except Exception:
                    precio_m2 = 0.0

            # base subtotal (material * area)
            sub_base = area * precio_m2
            # ensure label shows the computed base subtotal immediately (defensive)
            try:
                self.lbl_sub_base.setText(f"{float(sub_base or 0.0):.2f}")
            except Exception:
                try:
                    self.lbl_sub_base.setText("0.00")
                except Exception:
                    pass
            subtotal = float(sub_base or 0.0)
            # soportes
            try:
                soporte_qty = int(self.spin_soporte_qty.value())
                soporte_precio_txt = (self.lbl_soporte_precio.text() or '').replace(',', '').strip()
                if soporte_precio_txt.startswith('$'):
                    soporte_precio_txt = soporte_precio_txt[1:]
                soporte_precio = float(soporte_precio_txt) if soporte_precio_txt else 0.0
            except Exception:
                soporte_qty = 0
                soporte_precio = 0.0
            sub_bases = float(soporte_qty * soporte_precio)
            subtotal += sub_bases

            # regulador: cantidad * precio por regulador (leer de lbl_reg_precio)
            try:
                reg_qty = int(self.spin_reg_cant.value() or 0)
                reg_price_txt = (self.lbl_reg_precio.text() or '').replace('$', '').replace(',', '').strip()
                reg_price = float(reg_price_txt) if reg_price_txt else 0.0
            except Exception:
                reg_qty = 0
                reg_price = 0.0
            sub_reg = float(reg_qty * reg_price)
            subtotal += sub_reg

            # luces: calcular por unidad declarada (m2 o m). Se usa el atributo *_price_val_unit
            # read dimensions from the UI controls (defensive)
            try:
                alto = float(getattr(self, 'spin_alto', None).value() or 0.0)
            except Exception:
                alto = 0.0
            try:
                ancho = float(getattr(self, 'spin_ancho', None).value() or 0.0)
            except Exception:
                ancho = 0.0
            try:
                diam = float(getattr(self, 'spin_diam', None).value() or 0.0)
            except Exception:
                diam = 0.0

            # determine shape hints: round or square
            try:
                is_round = False
                try:
                    is_round = bool(self._is_round_cut())
                except Exception:
                    is_round = False
                # detect explicit 'cuadr' in cut labels or combo text
                is_square = False
                try:
                    for cb in getattr(self, 'cut_checkboxes', []) or []:
                        try:
                            if cb.isChecked() and 'cuadr' in (cb.text() or '').lower():
                                is_square = True
                                break
                        except Exception:
                            pass
                except Exception:
                    is_square = False
                try:
                    if not is_square:
                        txt = (getattr(self, 'cbo_corte', None).currentText() or '').lower() if getattr(self, 'cbo_corte', None) is not None else ''
                        if 'cuadr' in txt:
                            is_square = True
                except Exception:
                    pass
                # fallback: consider square when alto ~= ancho (within 0.5 cm)
                try:
                    if not is_square and not is_round and alto and ancho:
                        if abs(float(alto) - float(ancho)) <= 0.5:
                            is_square = True
                except Exception:
                    pass

                # compute linear meters for perimeter/circumference depending on shape
                if is_round:
                    # round shapes: prefer explicit diameter (mm) -> circumference
                    if float(diam or 0.0) > 0.0:
                        linear_m = 3.141592653589793 * (float(diam or 0.0) / 1000.0)
                    else:
                        # try derive from area
                        try:
                            import math
                            if area and float(area) > 0.0:
                                diam_m = 2.0 * math.sqrt(float(area) / 3.141592653589793)
                                linear_m = 3.141592653589793 * diam_m
                            else:
                                linear_m = 0.0
                        except Exception:
                            linear_m = 0.0
                else:
                    # rect / square: perimeter in meters (alto/ancho are cm)
                    try:
                        linear_m = 2.0 * ((float(alto or 0.0) + float(ancho or 0.0)) / 100.0)
                    except Exception:
                        linear_m = 0.0
            except Exception:
                linear_m = 0.0

            sub_luces = 0.0

            # diagnostics removed

            # helper to add contribution for a light item
            def _add_light_contrib(price_val, price_unit):
                """Compute contribution for a light type.

                Primary rule: lights are charged per linear meter (perímetro).
                If linear_m is 0 (missing dimensions), fallback to area-based calculation.
                """
                try:
                    if not price_val:
                        return 0.0
                    # prefer linear meters for lights
                    lm = float(linear_m or 0.0)
                    if lm and float(price_val):
                        return float(price_val) * lm
                    # fallback: use area (apply pi factor for round shapes)
                    try:
                        area_factor = 3.141592653589793 if self._is_round_cut() else 1.0
                    except Exception:
                        area_factor = 1.0
                    return float(price_val) * float(area or 0.0) * float(area_factor or 1.0)
                except Exception:
                    return 0.0

            # diagnostics removed

            # helper to resolve a price value: prefer internal numeric attr, fallback to parsing label text
            def _resolve_price(attr_name: str, label_widget) -> float:
                try:
                    val = getattr(self, attr_name, None)
                    if val is not None and float(val):
                        return float(val)
                except Exception:
                    pass
                # fallback: parse from label like "$10.00"
                try:
                    txt = (label_widget.text() or '').replace('$', '').replace(',', '').strip()
                    return float(txt) if txt else 0.0
                except Exception:
                    return 0.0

            # Determine lights contribution from selected combo item (preferred) or compatibility spin
            spin_luz = getattr(self, 'spin_luz_precio', None)
            spin_price = None
            if spin_luz is not None:
                try:
                    spin_price = float(spin_luz.value() or 0.0)
                except Exception:
                    try:
                        spin_price = float(spin_luz)
                    except Exception:
                        spin_price = 0.0

            # Prefer combo selection: itemData stored as (pv_id, price, unit)
            try:
                sel = None
                try:
                    sel = self.cbo_luz_tipo.itemData(self.cbo_luz_tipo.currentIndex()) if getattr(self, 'cbo_luz_tipo', None) is not None else None
                except Exception:
                    sel = None
                if isinstance(sel, (list, tuple)) and len(sel) >= 3:
                    _, price_val, price_unit = sel[0], sel[1], sel[2]
                    try:
                        price_val = float(price_val or 0.0)
                    except Exception:
                        price_val = 0.0
                    # update visible price label
                    try:
                        self.lbl_luz_price.setText(f"${float(price_val):.2f}" if price_val else "")
                    except Exception:
                        pass
                    sub_luces = _add_light_contrib(price_val, price_unit)
                elif spin_price is not None and float(spin_price or 0.0) > 0.0:
                    # fallback to spinner-based calculation
                    try:
                        sub_luces = _add_light_contrib(float(spin_price), getattr(self, '_luz_price_val_unit', None))
                        try:
                            self.lbl_luz_price.setText(f"${float(spin_price):.2f}" if spin_price else "")
                        except Exception:
                            pass
                    except Exception:
                        sub_luces = 0.0
                else:
                    # no selection and no spinner price
                    sub_luces = 0.0
                    try:
                        self.lbl_luz_price.setText("")
                    except Exception:
                        pass
            except Exception:
                sub_luces = 0.0

            # extras por chequeos simples (solo elementos que NO sean las luces ya calculadas arriba)
            # NOTE: spin_* attributes were removed from the UI; access them defensively
            extras_sum = 0.0
            lights_checks = (
                getattr(self, 'chk_led', None),
                getattr(self, 'chk_neon_m', None),
                getattr(self, 'chk_ceo', None),
                getattr(self, 'chk_neon_b', None),
            )
            extras_list = [
                (getattr(self, 'chk_led', None), getattr(self, 'spin_led_precio', None)),
                (getattr(self, 'chk_neon_m', None), getattr(self, 'spin_neon_m_precio', None)),
                (getattr(self, 'chk_ceo', None), getattr(self, 'spin_ceo_precio', None)),
                (getattr(self, 'chk_neon_b', None), getattr(self, 'spin_neon_b_precio', None)),
            ]
            for chk, spin in extras_list:
                try:
                    if chk is None:
                        continue
                    # skip light checkboxes here because lights were already computed using perimeter/circumference
                    if chk in lights_checks:
                        continue
                    if not chk.isChecked():
                        continue
                    if spin is None:
                        # no spin control: try to read a numeric attribute with the same name
                        val = None
                        for attr in ('_led_price_val', '_neon_m_price_val', '_ceo_price_val', '_neon_b_price_val'):
                            if hasattr(self, attr):
                                try:
                                    val = float(getattr(self, attr) or 0.0)
                                    break
                                except Exception:
                                    val = None
                        if val is not None:
                            # price per unit -> multiply by area (m2)
                            try:
                                extras_sum += float(val) * float(area or 0.0)
                            except Exception:
                                extras_sum += float(val)
                        continue
                    # if spin exists, prefer using its value() method
                    try:
                        # spin holds a unit price; multiply by area to obtain contribution
                        extras_sum += float(spin.value()) * float(area or 0.0)
                    except Exception:
                        # if spin is a plain number, try to convert
                        try:
                            extras_sum += float(spin) * float(area or 0.0)
                        except Exception:
                            pass
                except Exception:
                    pass
            # add extras (non-light) contributions once
            subtotal += float(extras_sum or 0.0)

            # Tipos de Corporeo: sumar area * precio_tipo para cada tipo seleccionado
            # Tipos de Corporeo: sumar area * precio_tipo para cada tipo seleccionado
            sub_tipo = 0.0
            try:
                for cb, price_lbl, oid in (getattr(self, 'tipo_corp_checkboxes', []) or []):
                    try:
                        if getattr(cb, 'isChecked') and cb.isChecked():
                            # parse price from label (format $xx.yy)
                            txt = (price_lbl.text() or '').replace('$', '').replace(',', '').strip()
                            try:
                                p = float(txt) if txt else 0.0
                            except Exception:
                                try:
                                    p = float(txt.split()[0])
                                except Exception:
                                    p = 0.0
                            sub_tipo += area * float(p)
                            subtotal += area * float(p)
                    except Exception:
                        pass
            except Exception:
                pass

            # ensure luces contribution is included in subtotal (in case it wasn't added earlier)
            try:
                subtotal += float(sub_luces or 0.0)
            except Exception:
                pass

            # Silueta: si la checkbox correspondiente está marcada sumar area * _silueta_price_val
            try:
                sil_selected = False
                for cb in getattr(self, 'cut_checkboxes', []) or []:
                    try:
                        txt = (cb.text() or '').lower()
                        tt = (cb.toolTip() or '').lower()
                        if 'silueta' in txt or 'silueta' in tt:
                            if cb.isChecked():
                                sil_selected = True
                                break
                    except Exception:
                        pass
                if sil_selected and getattr(self, '_silueta_price_val', 0.0):
                    try:
                        sub_silueta = area * float(getattr(self, '_silueta_price_val', 0.0) or 0.0)
                        subtotal += sub_silueta
                    except Exception:
                        sub_silueta = 0.0
                else:
                    sub_silueta = 0.0
            except Exception:
                sub_silueta = 0.0
            try:
                self._last_silueta_subtotal = float(sub_silueta or 0.0)
            except Exception:
                self._last_silueta_subtotal = 0.0

            # compute caja pct extra
            try:
                pct = float(self.spin_caja_pct.value())
            except Exception:
                pct = 0.0
            sub_caja_pct = subtotal * (pct / 100.0) if pct and getattr(self, 'chk_caja', None) and self.chk_caja.isChecked() else 0.0
            total = subtotal + float(sub_caja_pct or 0.0)

            # set breakdown labels
            try:
                # mostrar subtotal base: SOLO area * precio_espesor (no incluir tipos de corpóreo)
                try:
                    display_sub_base = float(sub_base or 0.0)
                except Exception:
                    display_sub_base = 0.0
                self.lbl_sub_base.setText(f"{display_sub_base:.2f}")
            except Exception:
                pass
            try:
                try:
                    silueta_extra = float(getattr(self, '_last_silueta_subtotal', 0.0) or 0.0)
                except Exception:
                    silueta_extra = 0.0
                try:
                    self.lbl_sub_silueta.setText(f"{silueta_extra:.2f}")
                except Exception:
                    pass
                self.lbl_sub_tipo_corp.setText(f"{float(sub_tipo or 0.0):.2f}")
            except Exception:
                pass
            try:
                # set luces subtotal label
                self.lbl_sub_luces.setText(f"{sub_luces:.2f}")
            except Exception:
                pass
            try:
                self.lbl_sub_bases.setText(f"{sub_bases:.2f}")
            except Exception:
                pass
            try:
                self.lbl_sub_luces.setText(f"{sub_luces:.2f}")
            except Exception:
                pass
            try:
                self.lbl_sub_regulador.setText(f"{sub_reg:.2f}")
            except Exception:
                pass
            try:
                self.lbl_sub_caja_pct.setText(f"{sub_caja_pct:.2f}")
            except Exception:
                pass

            self.lbl_subtotal.setText(f"{subtotal:.2f}")
            self.lbl_total.setText(f"{total:.2f}")
            
            # Calcular Precio Final Corpóreo USD: (subtotal * tasa_corporeo) / tasa_bcv
            try:
                tasa_corporeo = self._get_tasa_corporeo()
                tasa_bcv = self._get_tasa_bcv()
                precio_final_usd = ((subtotal * tasa_corporeo) / tasa_bcv) if tasa_bcv > 0 else 0.0
                self.lbl_precio_final_corporeo_usd.setText(f"{precio_final_usd:.2f}")
                self._last_precio_final_usd = float(precio_final_usd)
                self._last_tasa_corporeo = float(tasa_corporeo or 0.0)
                self._last_tasa_bcv = float(tasa_bcv or 0.0)
                self._last_precio_final_bs = float(precio_final_usd * tasa_bcv) if tasa_bcv else 0.0
            except Exception:
                self.lbl_precio_final_corporeo_usd.setText("0.00")
                self._last_precio_final_usd = 0.0
                self._last_precio_final_bs = 0.0
                self._last_tasa_corporeo = 0.0
                self._last_tasa_bcv = 0.0
        except Exception:
            pass

    def _get_tasa_corporeo(self) -> float:
        """Obtener la tasa corpóreo configurada en el sistema."""
        try:
            with self.session_factory() as session:
                tasa = get_system_config(session, "tasa_corporeo", "1.0")
                return float(tasa)
        except Exception:
            return 1.0  # Valor por defecto
    
    def _get_tasa_bcv(self) -> float:
        """Obtener la tasa BCV actual."""
        try:
            rate = get_bcv_rate(timeout=2.0)
            return float(rate) if rate else 36.0
        except Exception:
            return 36.0  # Valor por defecto

    def build_config_summary(self) -> str:
        parts = []

        # 1. Cortes (Impresion, Relieve, etc) - Moved to start
        cortes = []
        if hasattr(self, 'cut_checkboxes'):
            for cb in self.cut_checkboxes:
                if cb.isChecked():
                    cortes.append(cb.text())
        # Legacy combo
        if hasattr(self, 'cbo_corte') and self.cbo_corte.currentIndex() > 0:
            t = self.cbo_corte.currentText()
            if t and not t.startswith('--') and t not in cortes:
                cortes.append(t)
        if cortes:
            parts.append(", ".join(cortes))

        # 2. Medidas
        alto = self.spin_alto.value()
        ancho = self.spin_ancho.value()
        parts.append(f"{alto:.0f}x{ancho:.0f} cm")

        # 3. Material
        mat = ""
        if hasattr(self, 'cbo_material'):
            t = self.cbo_material.currentText()
            if t and not t.startswith('--'):
                mat = t
        esp = ""
        if hasattr(self, 'cbo_espesor'):
            t = self.cbo_espesor.currentText()
            if t and not t.startswith('--'):
                esp = t
        if mat or esp:
            parts.append(f"{mat} {esp}".strip())

        # 4. Acabado / Color
        finish_parts = []
        if hasattr(self, 'chk_base_transp') and self.chk_base_transp.isChecked():
            finish_parts.append("Transparente")
        if hasattr(self, 'chk_base_crudo') and self.chk_base_crudo.isChecked():
            finish_parts.append("Crudo")
        if hasattr(self, 'txt_base_color'):
            c = self.txt_base_color.text().strip()
            if c:
                finish_parts.append(c)
        if finish_parts:
            parts.append(", ".join(finish_parts))

        # 5. Tipo (Shape) - Moved here, multiple allowed
        tipos = []
        if hasattr(self, 'tipo_corp_checkboxes'):
            for cb, _, _ in self.tipo_corp_checkboxes:
                if cb.isChecked():
                    tipos.append(cb.text())
        
        if not tipos:
             # Fallback if nothing checked
             name = self.txt_name.text().strip()
             if name:
                 tipos.append(name)
             else:
                 tipos.append("Corpóreo")
        
        parts.append(", ".join(tipos))

        # 6. Soportes
        sop_str = ""
        if hasattr(self, 'cbo_soporte_item'):
            item = self.cbo_soporte_item.currentText()
            if item and not item.startswith('--'):
                size = ""
                if hasattr(self, 'cbo_soporte_size'):
                    s = self.cbo_soporte_size.currentText()
                    if s and not s.startswith('--'):
                        size = s
                qty = 0
                if hasattr(self, 'spin_soporte_qty'):
                    qty = int(self.spin_soporte_qty.value())
                
                if qty > 0:
                    sop_str = f"{item} {size} x{qty}".strip()
        if sop_str:
            parts.append(sop_str)

        # 7. Luces
        luz_str = ""
        if hasattr(self, 'cbo_luz_tipo'):
            tipo = self.cbo_luz_tipo.currentText()
            if tipo and not tipo.startswith('--'):
                luz_parts = [tipo]
                
                if hasattr(self, 'cbo_luz_color'):
                    c = self.cbo_luz_color.currentText()
                    if c and not c.startswith('--'):
                        luz_parts.append(c)
                        
                if hasattr(self, 'cbo_pos_luz'):
                    p = self.cbo_pos_luz.currentText()
                    if p and not p.startswith('--'):
                        luz_parts.append(p)
                        
                # Regulador
                if hasattr(self, 'cbo_reg_amp'):
                    reg = self.cbo_reg_amp.currentText()
                    if reg and not reg.startswith('--'):
                        qty_reg = 0
                        if hasattr(self, 'spin_reg_cant'):
                            qty_reg = int(self.spin_reg_cant.value())
                        if qty_reg > 0:
                            luz_parts.append(f"{reg} x{qty_reg}")
                            
                luz_str = ", ".join(luz_parts)
        if luz_str:
            parts.append(luz_str)

        # 8. Caja de Luz
        caja_str = "Caja de Luz: No"
        if hasattr(self, 'chk_caja') and self.chk_caja.isChecked():
            caja_parts = ["Caja de Luz: Si"]
            
            if hasattr(self, 'cbo_caja_base'):
                base = self.cbo_caja_base.currentText()
                if base and not base.startswith('--'):
                    caja_parts.append(base)
            
            if hasattr(self, 'cbo_caja_faja'):
                faja = self.cbo_caja_faja.currentText()
                if faja and not faja.startswith('--'):
                    caja_parts.append(faja)
            
            caja_str = ", ".join(caja_parts)
        
        parts.append(caja_str)

        return " | ".join(parts)

    def get_pricing_summary(self) -> dict:
        try:
            area = float(self.lbl_area.text())
        except Exception:
            area = 0.0
        try:
            subtotal = float(self.lbl_subtotal.text())
        except Exception:
            subtotal = 0.0
        try:
            total = float(self.lbl_total.text())
        except Exception:
            total = 0.0
        try:
            precio_final_usd = float(self.lbl_precio_final_corporeo_usd.text())
        except Exception:
            precio_final_usd = 0.0
        try:
            precio_final_bs = float(getattr(self, '_last_precio_final_bs', 0.0))
        except Exception:
            precio_final_bs = 0.0
        try:
            tasa_corp = float(getattr(self, '_last_tasa_corporeo', 0.0))
        except Exception:
            tasa_corp = 0.0
        try:
            tasa_bcv_val = float(getattr(self, '_last_tasa_bcv', 0.0))
        except Exception:
            tasa_bcv_val = 0.0
        # El precio unitario es el subtotal (sin diseño ni extras)
        precio_unitario = subtotal
        # La cantidad por defecto es 1 (puede ajustarse si el configurador lo soporta)
        cantidad = 1.0
        return {
            'area': area,
            'subtotal': subtotal,
            'total': total,
            'precio_unitario': precio_unitario,
            'precio_final_usd': precio_final_usd,  # Nuevo campo
            'precio_final_bs': precio_final_bs,
            'tasa_corporeo': tasa_corp,
            'tasa_bcv': tasa_bcv_val,
            'cantidad': cantidad,
            'descripcion': self.txt_desc.toPlainText().strip(),
        }

    def get_full_payload(self) -> dict:
        """Retorna el estado completo del diálogo para persistencia."""
        # 1. Cortes seleccionados
        cortes = []
        # Checkboxes
        if hasattr(self, 'cut_checkboxes'):
            for cb in self.cut_checkboxes:
                if cb.isChecked():
                    oid = cb.property('opt_id')
                    cortes.append({
                        'opt_id': oid,
                        'tipo': cb.text(),
                        'label': cb.text(),
                        'from_combo': False
                    })
        # Combo (legacy/compatibilidad)
        if hasattr(self, 'cbo_corte') and self.cbo_corte.currentIndex() > 0:
            try:
                oid = self.cbo_corte.currentData()
                txt = self.cbo_corte.currentText()
                cortes.append({
                    'opt_id': oid,
                    'tipo': txt,
                    'label': txt,
                    'from_combo': True
                })
            except Exception:
                pass

        # 2. Tipos de Corporeo
        tipos_corporeo = []
        if hasattr(self, 'tipo_corp_checkboxes'):
            for cb, _, oid in self.tipo_corp_checkboxes:
                if cb.isChecked():
                    tipos_corporeo.append({
                        'pv_id': oid,
                        'label': cb.text()
                    })

        # 3. Material y Espesor
        mat_id = None
        mat_text = ""
        if hasattr(self, 'cbo_material'):
            mat_id = self.cbo_material.currentData()
            mat_text = self.cbo_material.currentText()
            if mat_text.startswith('--'): mat_text = ""
            
        esp_id = None
        esp_text = ""
        if hasattr(self, 'cbo_espesor'):
            esp_id = self.cbo_espesor.currentData()
            esp_text = self.cbo_espesor.currentText()
            if esp_text.startswith('--'): esp_text = ""

        # 4. Luces
        luz_selected = []
        if hasattr(self, 'cbo_luz_tipo'):
            try:
                val = self.cbo_luz_tipo.currentData()
                luz_id = val[0] if isinstance(val, (list, tuple)) and len(val) >= 1 else val
                luz_text = self.cbo_luz_tipo.currentText()
                if not luz_text.startswith('--'):
                    luz_selected.append({'type': luz_text, 'pv_id': luz_id})
            except Exception:
                pass
        
        # Checkboxes de luces (legacy/extras)
        for chk in (getattr(self, 'chk_led', None), getattr(self, 'chk_neon_m', None), getattr(self, 'chk_ceo', None), getattr(self, 'chk_neon_b', None)):
            if chk and chk.isChecked():
                luz_selected.append({'type': chk.text()})

        luz_color = ""
        if hasattr(self, 'cbo_luz_color'):
            luz_color = self.cbo_luz_color.currentText()
            if luz_color.startswith('--'): luz_color = ""
            
        luz_pos = ""
        if hasattr(self, 'cbo_pos_luz'):
            luz_pos = self.cbo_pos_luz.currentText()
            if luz_pos.startswith('--'): luz_pos = ""

        # 5. Soporte
        sop_model = None
        sop_text = ""
        if hasattr(self, 'cbo_soporte_item'):
            sop_model = self.cbo_soporte_item.currentData()
            sop_text = self.cbo_soporte_item.currentText()
            if sop_text.startswith('--'): sop_text = ""
            
        sop_size = None
        if hasattr(self, 'cbo_soporte_size'):
            sop_size = self.cbo_soporte_size.currentData() # Or text if data is missing
            if not sop_size:
                sop_size = self.cbo_soporte_size.currentText()
            if str(sop_size).startswith('--'): sop_size = ""
            
        sop_qty = 0
        if hasattr(self, 'spin_soporte_qty'):
            sop_qty = self.spin_soporte_qty.value()

        # 6. Regulador
        reg_id = None
        if hasattr(self, 'cbo_reg_amp'):
            reg_id = self.cbo_reg_amp.currentData()
        reg_qty = 0
        if hasattr(self, 'spin_reg_cant'):
            reg_qty = self.spin_reg_cant.value()

        # 7. Caja
        caja_enabled = False
        caja_base = ""
        caja_faja = ""
        if hasattr(self, 'chk_caja'):
            caja_enabled = self.chk_caja.isChecked()
        if hasattr(self, 'cbo_caja_base'):
            caja_base = self.cbo_caja_base.currentText()
            if caja_base.startswith('--'): caja_base = ""
        if hasattr(self, 'cbo_caja_faja'):
            caja_faja = self.cbo_caja_faja.currentText()
            if caja_faja.startswith('--'): caja_faja = ""

        # 8. Base Color
        base_crudo = False
        base_transp = False
        base_color_val = ""
        if hasattr(self, 'chk_base_crudo'): base_crudo = self.chk_base_crudo.isChecked()
        if hasattr(self, 'chk_base_transp'): base_transp = self.chk_base_transp.isChecked()
        if hasattr(self, 'txt_base_color'): base_color_val = self.txt_base_color.text()

        summary = self.get_pricing_summary()
        
        return {
            'product_id': self.product_id,
            'nombre': self.txt_name.text(),
            'descripcion_user': self.txt_desc.toPlainText(),
            'medidas': {
                'alto_cm': self.spin_alto.value(),
                'ancho_cm': self.spin_ancho.value(),
                'diam_mm': self.spin_diam.value() if hasattr(self, 'spin_diam') else 0.0
            },
            'cortes': cortes,
            'tipos_corporeo': tipos_corporeo,
            'material': {
                'id': mat_id,
                'label': mat_text
            },
            'espesor': {
                'id': esp_id,
                'label': esp_text
            },
            'luces': {
                'selected': luz_selected,
                'color': luz_color,
                'posicion': luz_pos
            },
            'soporte': {
                'model': sop_model, # ID or text
                'size': sop_size,
                'qty': sop_qty
            },
            'regulador': {
                'id': reg_id,
                'qty': reg_qty
            },
            'caja': {
                'enabled': caja_enabled,
                'base': caja_base,
                'faja': caja_faja
            },
            'base_color': {
                'crudo': base_crudo,
                'transparente': base_transp,
                'color': base_color_val
            },
            'totals': summary,
            'precio_final_usd': summary.get('precio_final_usd', 0.0),
            'precio_final_bs': summary.get('precio_final_bs', 0.0),
            'tasa_corporeo': summary.get('tasa_corporeo', 0.0),
            'tasa_bcv': summary.get('tasa_bcv', 0.0),
            'summary': {
                'descripcion': self.build_config_summary()
            },
            # Legacy flat fields for compatibility if needed
            'material_id': mat_id,
            'material_text': mat_text,
            'espesor_id': esp_id,
            'espesor_text': esp_text,
        }

