
from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.dialects.sqlite import JSON as SqliteJSON

from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, Float, ForeignKey, Boolean, Table
from typing import List

class Base(DeclarativeBase):
    """Base declarativa común para todos los modelos."""
    pass

# --- Modelo para formulario Corpóreo ---
class CorporeoForm(Base):
    __tablename__ = "corporeo_forms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    product_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("products.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    payload_json: Mapped[dict] = mapped_column(SqliteJSON, nullable=False)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


# --- Auth (Usuarios/Roles/Permisos) ---

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_role_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("roles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"User(id={self.id!r}, username={self.username!r})"


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Role(id={self.id!r}, name={self.name!r})"


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Permission(id={self.id!r}, code={self.code!r})"


class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    permission_id: Mapped[int] = mapped_column(Integer, ForeignKey("permissions.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


    


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    document: Mapped[str | None] = mapped_column(String(50))  # C.I./Rif.
    short_address: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Customer(id={self.id!r}, name={self.name!r})"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


# --- Eliminados todos los modelos relacionados con Corporeo ---


# --- Categorías y Modelos por Producto ---

class ProductCategory(Base):
    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"ProductCategory(id={self.id!r}, product_id={self.product_id!r}, name={self.name!r})"


class ProductModel(Base):
    __tablename__ = "product_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("product_categories.id"), nullable=False)
    code: Mapped[str | None] = mapped_column(String(120))  # p.ej. 901, 912, 940-D
    size_text: Mapped[str | None] = mapped_column(String(120))  # p.ej. 18x38mm
    label: Mapped[str | None] = mapped_column(String(200))  # descripción adicional
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"ProductModel(id={self.id!r}, category_id={self.category_id!r}, code={self.code!r}, price={self.price!r})"



# --- Modelo legacy para compatibilidad con productos antiguos ---
class LegacyMaterial(Base):
    __tablename__ = "legacy_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30))  # p.ej., m, m2, und, kg, l
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)



class ProductMaterial(Base):
    __tablename__ = "product_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    material_id: Mapped[int] = mapped_column(Integer, ForeignKey("legacy_materials.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    waste_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # merma (%)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"ProductMaterial(product_id={self.product_id!r}, material_id={self.material_id!r}, qty={self.quantity!r})"


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Campos básicos de la venta
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)  # Fecha
    numero_orden: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)  # Número de orden
    articulo: Mapped[str] = mapped_column(String(200), nullable=False)  # Artículo
    asesor: Mapped[str] = mapped_column(String(120), nullable=False)  # Asesor (usuario logueado)
    
    # Montos y pagos
    venta_usd: Mapped[float] = mapped_column(Float, nullable=False)  # Venta $ (total de la venta)
    forma_pago: Mapped[str | None] = mapped_column(String(80))  # Forma de pago
    serial_billete: Mapped[str | None] = mapped_column(String(200))  # Serial Billete (si pago es efectivo $)
    banco: Mapped[str | None] = mapped_column(String(120))  # Banco (si pago es Pago móvil/transferencia bs)
    referencia: Mapped[str | None] = mapped_column(String(120))  # Referencia (si pago es Pago móvil/transferencia bs)
    fecha_pago: Mapped[datetime | None] = mapped_column(DateTime)  # Fecha de pago
    
    # Montos en bolívares
    monto_bs: Mapped[float | None] = mapped_column(Float)  # Monto Bs.D
    monto_usd_calculado: Mapped[float | None] = mapped_column(Float)  # Monto $ (calculado desde Bs.D según tasa BCV)
    tasa_bcv: Mapped[float | None] = mapped_column(Float)  # Tasa BCV utilizada para el cálculo
    
    # Abonos y restante
    abono_usd: Mapped[float | None] = mapped_column(Float)  # Abono $ (cuánto abonó el cliente)
    restante: Mapped[float | None] = mapped_column(Float)  # Restante (venta_usd - abono_usd)
    
    # Impuestos y servicios adicionales
    iva: Mapped[float | None] = mapped_column(Float)  # IVA (solo se completa si se cobra IVA en ventas bs)
    diseno_usd: Mapped[float | None] = mapped_column(Float)  # Diseño $ (si la venta lleva diseño)
    ingresos_usd: Mapped[float | None] = mapped_column(Float)  # Ingresos $ (si venta en divisas, cantidad que ingresó)
    
    # Campos adicionales
    notes: Mapped[str | None] = mapped_column(String(1000))  # Notas adicionales
    cliente: Mapped[str | None] = mapped_column(String(200))  # Nombre/etiqueta del cliente
    cliente_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # ID externo de cliente
    descripcion: Mapped[str | None] = mapped_column(String(2000))  # Descripción libre/compacta
    cantidad: Mapped[float | None] = mapped_column(Float)  # Cantidad del item
    precio_unitario: Mapped[float | None] = mapped_column(Float)  # Precio unitario (USD)
    total_bs: Mapped[float | None] = mapped_column(Float)  # Total en Bs
    details_json: Mapped[str | None] = mapped_column(String(4000))  # JSON con detalles de la venta (serializado)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    items: Mapped[List["SaleItem"]] = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    payments: Mapped[List["SalePayment"]] = relationship("SalePayment", back_populates="sale", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"Sale(id={self.id!r}, numero_orden={self.numero_orden!r}, articulo={self.articulo!r}, venta_usd={self.venta_usd!r})"


class SaleItem(Base):
    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(Integer, ForeignKey("sales.id"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    details_json: Mapped[str | None] = mapped_column(String(4000))
    
    sale: Mapped["Sale"] = relationship("Sale", back_populates="items")

    def __repr__(self) -> str:
        return f"SaleItem(id={self.id!r}, product={self.product_name!r}, qty={self.quantity!r})"


class SalePayment(Base):
    __tablename__ = "sale_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(Integer, ForeignKey("sales.id"), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(80), nullable=False)
    amount_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    amount_bs: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    exchange_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    bank: Mapped[str | None] = mapped_column(String(120))
    payment_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    sale: Mapped["Sale"] = relationship("Sale", back_populates="payments")

    def __repr__(self) -> str:
        return f"SalePayment(id={self.id!r}, method={self.payment_method!r}, amount=${self.amount_usd!r})"




# --- EAV (Entity-Attribute-Value) para productos dinámicos ---

class EavProductType(Base):
    __tablename__ = "eav_product_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)  # p.ej. CORPOREO, SELLO
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class EavAttribute(Base):
    __tablename__ = "eav_attributes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)  # p.ej. corte_tipo, alto
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    data_type: Mapped[str] = mapped_column(String(30), nullable=False)  # text|number|option|multi|checkbox|money|calc
    unit: Mapped[str | None] = mapped_column(String(30))  # m, m2, mm, etc.
    price_per_unit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    price_affects: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    visible_expr: Mapped[str | None] = mapped_column(String(500))  # condición opcional para mostrar (expresión simple)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class EavTypeAttribute(Base):
    __tablename__ = "eav_type_attributes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_id: Mapped[int] = mapped_column(Integer, ForeignKey("eav_product_types.id"), nullable=False)
    attribute_id: Mapped[int] = mapped_column(Integer, ForeignKey("eav_attributes.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class EavAttributeOption(Base):
    __tablename__ = "eav_attribute_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attribute_id: Mapped[int] = mapped_column(Integer, ForeignKey("eav_attributes.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    price_per_unit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class EavProduct(Base):
    __tablename__ = "eav_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_id: Mapped[int] = mapped_column(Integer, ForeignKey("eav_product_types.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class EavValue(Base):
    __tablename__ = "eav_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("eav_products.id"), nullable=False)
    attribute_id: Mapped[int] = mapped_column(Integer, ForeignKey("eav_attributes.id"), nullable=False)
    value_text: Mapped[str | None] = mapped_column(String(500))
    value_number: Mapped[float | None] = mapped_column(Float)
    option_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("eav_attribute_options.id"))
    value_bool: Mapped[bool | None] = mapped_column(Boolean)
    subtotal_money: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


# --- Orders (Pedidos) ---

# --- Sequence counters for order numbering ---
class OrderSequence(Base):
    __tablename__ = "order_sequences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    last_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"OrderSequence(year={self.year!r}, last_number={self.last_number!r})"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(Integer, ForeignKey("sales.id"), nullable=False)
    order_number: Mapped[str] = mapped_column(String(50), nullable=False)  # Número de orden legible (ORD-2025-001)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    details_json: Mapped[str] = mapped_column(String(4000), nullable=False)  # JSON con parámetros
    status: Mapped[str | None] = mapped_column(String(50))  # p.ej., NUEVO, EN_PROCESO, LISTO
    designer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    sale: Mapped["Sale"] = relationship("Sale")
    designer: Mapped["User"] = relationship("User", foreign_keys=[designer_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"Order(id={self.id!r}, order_number={self.order_number!r}, sale_id={self.sale_id!r}, product_name={self.product_name!r})"


class CorporeoConfig(Base):
    __tablename__ = "corporeo_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id"))
    # Número legible de orden/venta (p. ej., ORD-2025-001 o V-20251020-001)
    order_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sale_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sales.id"))
    product_id: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    cliente_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    soporte_model_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    soporte_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    luz_pv_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    luz_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    posicion_luz: Mapped[str | None] = mapped_column(String(128))
    precio_total_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    precio_total_bs: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(String(10000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"CorporeoConfig(id={self.id!r}, order_id={self.order_id!r}, sale_id={self.sale_id!r})"


class CorporeoPayload(Base):
    """Almacena de forma normalizada los campos del `payload` generado por
    `CorporeoDialog._on_accept`.

    Esta tabla contiene columnas para las propiedades más consultadas y
    mantiene el JSON completo en `payload_json` para flexibilidad.
    """
    __tablename__ = "corporeo_payloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id"))
    order_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sale_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sales.id"))

    # Datos identificadores y texto
    nombre: Mapped[str | None] = mapped_column(String(300))
    descripcion_user: Mapped[str | None] = mapped_column(String(2000))

    # Medidas
    alto_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ancho_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    diam_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Corte / Tipos
    cortes_json: Mapped[str | None] = mapped_column(String(2000))  # JSON list
    corte_combo_text: Mapped[str | None] = mapped_column(String(200))

    # Material / espesor
    material_label: Mapped[str | None] = mapped_column(String(200))
    material_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    espesor_label: Mapped[str | None] = mapped_column(String(200))
    espesor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    espesor_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Base / color
    base_color: Mapped[str | None] = mapped_column(String(200))
    base_color_code: Mapped[str | None] = mapped_column(String(120))
    base_crudo: Mapped[bool | None] = mapped_column(Boolean)
    base_transparente: Mapped[bool | None] = mapped_column(Boolean)

    # Tipos corporeo (lista) — almacenado como JSON por simplicidad
    tipos_corporeo_json: Mapped[str | None] = mapped_column(String(4000))

    # Soporte
    soporte_model: Mapped[str | None] = mapped_column(String(200))
    soporte_size: Mapped[str | None] = mapped_column(String(200))
    soporte_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    soporte_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Luces
    luces_json: Mapped[str | None] = mapped_column(String(2000))
    luz_color: Mapped[str | None] = mapped_column(String(120))
    posicion_luz: Mapped[str | None] = mapped_column(String(128))
    luz_pv_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    luz_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Regulador
    regulador_label: Mapped[str | None] = mapped_column(String(120))
    regulador_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    regulador_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    regulador_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Caja
    caja_enabled: Mapped[bool | None] = mapped_column(Boolean)
    caja_base: Mapped[str | None] = mapped_column(String(120))
    caja_faja: Mapped[str | None] = mapped_column(String(120))
    caja_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Totales
    subtotal: Mapped[float | None] = mapped_column(Float, nullable=True)
    total: Mapped[float | None] = mapped_column(Float, nullable=True)

    # JSON completo para flexibilidad y recuperación completa
    payload_json: Mapped[str | None] = mapped_column(String(10000))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"CorporeoPayload(id={self.id!r}, order_number={self.order_number!r}, sale_id={self.sale_id!r})"


class DailyReport(Base):
    """Modelo para registrar los reportes diarios de ventas."""
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, unique=True)  # Fecha del reporte (única por día)
    generated_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)  # Usuario que generó el reporte
    total_sales: Mapped[int] = mapped_column(Integer, default=0)  # Cantidad de ventas del día
    total_amount_usd: Mapped[float] = mapped_column(Float, default=0.0)  # Total en USD del día
    total_amount_bs: Mapped[float] = mapped_column(Float, default=0.0)  # Total en Bs del día
    total_ingresos_usd: Mapped[float] = mapped_column(Float, default=0.0)  # Total ingresos reales en USD
    report_status: Mapped[str] = mapped_column(String(20), default="PENDIENTE")  # PENDIENTE, GENERADO, CERRADO
    report_data_json: Mapped[str | None] = mapped_column(String(10000))  # JSON con datos detallados del reporte
    notes: Mapped[str | None] = mapped_column(String(1000))  # Notas adicionales del administrador
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"DailyReport(id={self.id!r}, report_date={self.report_date.date()!r}, status={self.report_status!r})"


# --- Configuraciones del Sistema ---

class SystemConfig(Base):
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)  # Clave de configuración
    config_value: Mapped[str] = mapped_column(String(500), nullable=False)  # Valor de configuración (JSON string)
    description: Mapped[str | None] = mapped_column(String(200))  # Descripción de la configuración
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"SystemConfig(id={self.id!r}, key={self.config_key!r}, value={self.config_value!r})"


# --- Módulo de Parámetros y Materiales ---

class ConfigurableProduct(Base):
    """Productos configurables con parámetros dinámicos."""
    __tablename__ = "configurable_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)  # Nombre del producto
    description: Mapped[str | None] = mapped_column(String(500))  # Descripción opcional
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # Estado activo/inactivo
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)  # Usuario que creó
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"ConfigurableProduct(id={self.id!r}, name={self.name!r}, active={self.is_active!r})"


class ProductParameterTable(Base):
    """Tablas de parámetros dinámicas asociadas a productos configurables."""
    __tablename__ = "product_parameter_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("configurable_products.id"), nullable=False)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)  # Nombre de la tabla SQL generada
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)  # Nombre para mostrar en UI
    description: Mapped[str | None] = mapped_column(String(500))  # Descripción de la tabla
    schema_json: Mapped[str] = mapped_column(String(5000), nullable=False)  # Schema de columnas en JSON
    has_auto_id: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # Si incluye columna ID automática
    parent_table_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("product_parameter_tables.id"))  # Tabla padre para relaciones
    relationship_column: Mapped[str | None] = mapped_column(String(100))  # Nombre de la columna de relación (FK)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"ProductParameterTable(id={self.id!r}, product_id={self.product_id!r}, table={self.table_name!r})"


class ProductParameterValue(Base):
    """Valores almacenados en las tablas de parámetros dinámicas."""
    __tablename__ = "product_parameter_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parameter_table_id: Mapped[int] = mapped_column(Integer, ForeignKey("product_parameter_tables.id"), nullable=False)
    row_data_json: Mapped[str] = mapped_column(String(2000), nullable=False)  # Datos de la fila en JSON
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"ProductParameterValue(id={self.id!r}, table_id={self.parameter_table_id!r})"


# --- Módulo de Talonarios ---

class TipoTalonario(Base):
    """Tipos de talonarios disponibles."""
    __tablename__ = "tipo_talonarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(500))
    precio_base: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"TipoTalonario(id={self.id!r}, nombre={self.nombre!r})"


class Impresion(Base):
    """Tipos de impresión disponibles."""
    __tablename__ = "impresiones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(500))
    costo_adicional: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Impresion(id={self.id!r}, nombre={self.nombre!r})"


class TalonarioConfig(Base):
    """Configuración de talonarios relacionada a productos."""
    __tablename__ = "talonario_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    tipo_talonario_id: Mapped[int] = mapped_column(Integer, ForeignKey("tipo_talonarios.id"), nullable=False)
    impresion_id: Mapped[int] = mapped_column(Integer, ForeignKey("impresiones.id"), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    precio_total: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    detalles_json: Mapped[str | None] = mapped_column(String(4000))  # JSON con configuración adicional
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"TalonarioConfig(id={self.id!r}, product_id={self.product_id!r}, tipo={self.tipo_talonario_id!r})"
