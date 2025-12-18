
from __future__ import annotations
import json
from .models import CorporeoForm

def save_corporeo_form(session: Session, user_id: int | None, product_id: int | None, payload: dict, name: str | None = None, description: str | None = None) -> int:
    form = CorporeoForm(
        user_id=user_id,
        product_id=product_id,
        payload_json=payload,
        name=name,
        description=description
    )
    session.add(form)
    session.commit()
    session.refresh(form)
    return form.id

def load_corporeo_form(session: Session, form_id: int) -> dict | None:
    form = session.get(CorporeoForm, form_id)
    if form:
        return form.payload_json
    return None
#
## --- Referencias de Corporeo eliminadas ---

# --- CRUD Products (tests expectation) ---
from .models import Product, DailyReport
from sqlalchemy.orm import Session, joinedload

def add_product(session: Session, *, name: str, category: str | None = None, price: float = 0.0) -> Product:
    p = Product(name=name, category=category, price=price)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p

def list_products(session: Session) -> list[Product]:
    return session.query(Product).order_by(Product.id.asc()).all()

def get_product_by_id(session: Session, product_id: int) -> Product | None:
    return session.get(Product, product_id)

def update_product(session: Session, product_id: int, *, name: str | None = None, category: str | None = None, price: float | None = None) -> bool:
    p = session.get(Product, product_id)
    if not p:
        return False
    if name is not None:
        p.name = name
    if category is not None:
        p.category = category
    if price is not None:
        p.price = price
    session.commit()
    return True

def delete_product_by_id(session: Session, product_id: int) -> bool:
    p = session.get(Product, product_id)
    if not p:
        return False
    session.delete(p)
    session.commit()
    return True


from typing import Iterable, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
import hashlib, os, hmac

# --- Funciones internas de autenticación ---
def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    iters = 100_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    return f"pbkdf2_sha256${iters}${salt.hex()}${dk.hex()}"

def _verify_password(password: str, hashed: str) -> bool:
    try:
        algo, iter_s, salt_hex, dk_hex = hashed.split("$")
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iter_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(dk_hex)
        test = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
        return hmac.compare_digest(test, expected)
    except Exception:
        return False

from .models import (
    Base, Customer, Sale, SaleItem, SalePayment,
    Order, OrderSequence,
    User, Role, Permission, UserRole, RolePermission,
    Worker, WorkerGoal,
    SystemConfig,
    CorporeoConfig, CorporeoPayload,
    # EAV
    EavProductType, EavAttribute, EavTypeAttribute, EavAttributeOption, EavProduct, EavValue
)


# --- Auth API ---
def create_user(session: Session, *, username: str, password: str, full_name: str | None = None, 
                 default_role_id: int | None = None, is_active: bool = True) -> User:
    # Check if user exists (active or inactive)
    existing_user = session.query(User).filter(User.username == username).first()
    
    if existing_user:
        if existing_user.is_active:
            raise ValueError(f"El usuario '{username}' ya existe y está activo.")
        
        # Reactivate and update
        print(f"DEBUG: Reactivating user {username}")
        existing_user.is_active = is_active
        if full_name:
            existing_user.full_name = full_name
        existing_user.password_hash = _hash_password(password)
        if default_role_id is not None:
            existing_user.default_role_id = default_role_id
            
        session.commit()
        session.refresh(existing_user)
        return existing_user

    user = User(
        username=username, 
        full_name=full_name, 
        password_hash=_hash_password(password), 
        default_role_id=default_role_id,
        is_active=is_active
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate_user(session: Session, *, username: str, password: str) -> Optional[User]:
    user = session.query(User).filter(User.username == username, User.is_active == True).first()  # noqa: E712
    if not user:
        return None
    return user if _verify_password(password, user.password_hash) else None


def ensure_role(session: Session, *, name: str, description: str | None = None) -> Role:
    # Try to return existing role first
    r = session.query(Role).filter(Role.name == name).first()
    if r:
        return r
    # Not found -> attempt to create; handle unique constraint races
    r = Role(name=name, description=description)
    session.add(r)
    try:
        session.commit()
        session.refresh(r)
        return r
    except IntegrityError:
        session.rollback()
        # Another session may have inserted it concurrently; fetch existing
        return session.query(Role).filter(Role.name == name).first()


def ensure_permission(session: Session, *, code: str, description: str | None = None) -> Permission:
    # Return existing if present
    p = session.query(Permission).filter(Permission.code == code).first()
    if p:
        return p
    p = Permission(code=code, description=description)
    session.add(p)
    try:
        session.commit()
        session.refresh(p)
        return p
    except IntegrityError:
        session.rollback()
        return session.query(Permission).filter(Permission.code == code).first()


def update_permission(session: Session, *, permission_id: int, code: str | None = None, description: str | None = None) -> Permission | None:
    p = session.get(Permission, permission_id)
    if not p:
        return None
    if code is not None:
        p.code = code
    if description is not None:
        p.description = description
    session.commit()
    session.refresh(p)
    return p


def assign_role_to_user(session: Session, *, user_id: int, role_id: int) -> None:
    if not session.query(UserRole).filter(UserRole.user_id == user_id, UserRole.role_id == role_id).first():
        session.add(UserRole(user_id=user_id, role_id=role_id))
        session.commit()


def grant_permission_to_role(session: Session, *, role_id: int, permission_id: int) -> None:
    if not session.query(RolePermission).filter(RolePermission.role_id == role_id, RolePermission.permission_id == permission_id).first():
        session.add(RolePermission(role_id=role_id, permission_id=permission_id))
        session.commit()


def user_has_permission(session: Session, *, user_id: int, permission_code: str) -> bool:
    q = (
        session.query(RolePermission)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .filter(UserRole.user_id == user_id, Permission.code == permission_code)
    )
    return session.query(q.exists()).scalar() or False


def user_has_role(session: Session, *, user_id: int, role_name: str) -> bool:
    """Verifica si un usuario tiene un rol específico."""
    q = (
        session.query(UserRole)
        .join(Role, Role.id == UserRole.role_id)
        .filter(UserRole.user_id == user_id, Role.name == role_name)
    )
    return session.query(q.exists()).scalar() or False


# --- Auth CRUD extra ---
def list_users(session: Session) -> list[User]:
    return session.query(User).order_by(User.id.asc()).all()


def list_roles(session: Session) -> list[Role]:
    return session.query(Role).order_by(Role.id.asc()).all()


def list_permissions(session: Session) -> list[Permission]:
    return session.query(Permission).order_by(Permission.id.asc()).all()


def update_user(session: Session, *, user_id: int, full_name: str | None = None, 
                password: str | None = None, default_role_id: int | None = None, 
                is_active: bool | None = None) -> Optional[User]:
    u = session.get(User, user_id)
    if not u:
        return None
    if full_name is not None:
        u.full_name = full_name
    if is_active is not None:
        u.is_active = bool(is_active)
    if default_role_id is not None:
        u.default_role_id = default_role_id
    if password:
        u.password_hash = _hash_password(password)
    session.commit()
    session.refresh(u)
    return u


def delete_user(session: Session, *, user_id: int) -> bool:
    u = session.get(User, user_id)
    if not u:
        return False
    
    # Proteger al usuario admin de eliminación
    if u.username == "admin":
        raise ValueError("No se puede eliminar al usuario administrador del sistema")
    
    # Soft delete: marcar como inactivo para evitar errores de FK (ej. orders)
    print(f"DEBUG: Soft deleting user {user_id}")
    u.is_active = False
    
    # Desvincular de cualquier trabajador asignado
    worker = session.query(Worker).filter(Worker.user_id == user_id).first()
    if worker:
        print(f"DEBUG: Unlinking user {user_id} from worker {worker.id}")
        worker.user_id = None

    # No eliminamos roles ni el registro físico para mantener integridad referencial
    # session.query(UserRole).filter(UserRole.user_id == user_id).delete()
    # session.delete(u)
    
    session.commit()
    return True


def update_role(session: Session, *, role_id: int, name: str | None = None, description: str | None = None) -> Optional[Role]:
    r = session.get(Role, role_id)
    if not r:
        return None
    if name is not None:
        r.name = name
    if description is not None:
        r.description = description
    session.commit()
    return r


def get_user_role_ids(session: Session, *, user_id: int) -> list[int]:
    rows = session.query(UserRole).filter(UserRole.user_id == user_id).all()
    return [ur.role_id for ur in rows]


def set_user_roles(session: Session, *, user_id: int, role_ids: list[int]) -> None:
    current = set(get_user_role_ids(session, user_id=user_id))
    desired = set(role_ids)
    to_add = desired - current
    to_del = current - desired
    if to_del:
        session.query(UserRole).filter(UserRole.user_id == user_id, UserRole.role_id.in_(list(to_del))).delete(synchronize_session=False)
    for rid in to_add:
        session.add(UserRole(user_id=user_id, role_id=rid))
    session.commit()


def get_role_permission_ids(session: Session, *, role_id: int) -> list[int]:
    rows = session.query(RolePermission).filter(RolePermission.role_id == role_id).all()
    return [rp.permission_id for rp in rows]


def set_role_permissions(session: Session, *, role_id: int, permission_ids: list[int]) -> None:
    current = set(get_role_permission_ids(session, role_id=role_id))
    desired = set(permission_ids)
    to_add = desired - current
    to_del = current - desired
    if to_del:
        session.query(RolePermission).filter(RolePermission.role_id == role_id, RolePermission.permission_id.in_(list(to_del))).delete(synchronize_session=False)
    for pid in to_add:
        session.add(RolePermission(role_id=role_id, permission_id=pid))
    session.commit()


def init_db(engine, seed: bool = True) -> None:
    """Crea tablas y opcionalmente inserta datos de ejemplo."""
    Base.metadata.create_all(bind=engine)
    # Migración ligera: asegurar columnas nuevas en customers
    insp = inspect(engine)
    cols = {c['name'] for c in insp.get_columns('customers')} if insp.has_table('customers') else set()
    needed = {"first_name", "last_name", "document", "short_address", "phone"}
    missing = list(needed - cols)
    if missing:
        with engine.begin() as conn:
            # SQLite permite ADD COLUMN sin default complejo
            for col in missing:
                if col in {"first_name", "last_name"}:
                    conn.execute(text(f"ALTER TABLE customers ADD COLUMN {col} VARCHAR(120)"))
                elif col in {"document", "phone"}:
                    conn.execute(text(f"ALTER TABLE customers ADD COLUMN {col} VARCHAR(50)"))
                elif col == "short_address":
                    conn.execute(text("ALTER TABLE customers ADD COLUMN short_address VARCHAR(200)"))
    # Migración ligera: columna notes en sales
    if insp.has_table('sales'):
        sales_cols = {c['name'] for c in insp.get_columns('sales')}
        if 'notes' not in sales_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE sales ADD COLUMN notes VARCHAR(1000)"))
        # Add new columns for structured sales if missing
        add_cols = [
            ("cliente", "VARCHAR(200)"),
            ("cliente_id", "INTEGER"),
            ("descripcion", "VARCHAR(2000)"),
            ("cantidad", "FLOAT"),
            ("precio_unitario", "FLOAT"),
            ("total_bs", "FLOAT"),
            ("details_json", "VARCHAR(4000)"),
        ]
        for col_name, col_type in add_cols:
            if col_name not in sales_cols:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE sales ADD COLUMN {col_name} {col_type}"))

    # --- SEED/MIGRACIONES DE CORPOREO (ELIMINADO) ---
                
    # Migración: agregar default_role_id a users
    if insp.has_table('users'):
        users_cols = {c['name'] for c in insp.get_columns('users')}
        with engine.begin() as conn:
            if 'default_role_id' not in users_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN default_role_id INTEGER REFERENCES roles(id)"))
            if 'monthly_goal' not in users_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN monthly_goal FLOAT DEFAULT 0.0"))
                
    # Migración: agregar order_number a orders y crear tabla order_sequences
    if insp.has_table('orders'):
        orders_cols = {c['name'] for c in insp.get_columns('orders')}
        if 'order_number' not in orders_cols:
            with engine.begin() as conn:
                # Agregar columna order_number
                conn.execute(text("ALTER TABLE orders ADD COLUMN order_number VARCHAR(50)"))
                # Crear tabla order_sequences
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS order_sequences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        year INTEGER NOT NULL UNIQUE,
                        last_number INTEGER DEFAULT 0 NOT NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                # Actualizar órdenes existentes con números secuenciales
                conn.execute(text("""
                    UPDATE orders 
                    SET order_number = 'ORD-' || strftime('%Y', created_at) || '-' || printf('%03d', id)
                    WHERE order_number IS NULL
    
    # Migración: workers (asegurar full_name y user_id)
    if insp.has_table('workers'):
        w_cols = {c['name'] for c in insp.get_columns('workers')}
        with engine.begin() as conn:
            if 'full_name' not in w_cols:
                conn.execute(text("ALTER TABLE workers ADD COLUMN full_name VARCHAR(200)"))
                # Intentar poblar full_name desde first_name + last_name si existen
                if 'first_name' in w_cols and 'last_name' in w_cols:
                    conn.execute(text("UPDATE workers SET full_name = TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, ''))"))
                # Si no, usar name si existe
                elif 'name' in w_cols:
                    conn.execute(text("UPDATE workers SET full_name = name"))
                
            if 'user_id' not in w_cols:
                conn.execute(text("ALTER TABLE workers ADD COLUMN user_id INTEGER REFERENCES users(id)"))
                """))
    # Asegurar tabla orders
    if not insp.has_table('orders'):
        with engine.begin() as conn:
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_id INTEGER NOT NULL REFERENCES sales(id),
                    product_name VARCHAR(200) NOT NULL,
                    details_json VARCHAR(4000) NOT NULL,
                    status VARCHAR(50),
                    created_at DATETIME
                )
                """
            ))
    # Migración ligera: agregar columna order_number a corporeo_configs para enlazar por número legible
    if insp.has_table('corporeo_configs'):
        try:
            cols = {c['name'] for c in insp.get_columns('corporeo_configs')}
        except Exception:
            cols = set()
        if 'order_number' not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE corporeo_configs ADD COLUMN order_number VARCHAR(50)"))
    if not seed:
        return

    with Session(bind=engine) as session:
        # Seed auth mínimo: roles y permisos base
        admin_role = ensure_role(session, name="ADMIN", description="Administrador del sistema")
        administracion_role = ensure_role(session, name="ADMINISTRACION", description="Administración con acceso completo a ventas y reportes")
        vendedor_role = ensure_role(session, name="VENDEDOR", description="Vendedor con acceso a clientes, productos, pedidos y ventas")
        # Permisos base
        def ensure_perm(code: str, desc: str) -> Permission:
            p = session.query(Permission).filter(Permission.code == code).first()
            if not p:
                p = Permission(code=code, description=desc)
                session.add(p)
                session.commit()
            return p
        # Permisos específicos por módulo
        perms = [
            # Módulo Home
            ("view_home", "Ver página de inicio"),
            # Módulo Clientes
            ("view_customers", "Ver clientes"),
            ("edit_customers", "Editar clientes"),
            # Módulo Productos
            ("view_products", "Ver productos"),
            ("edit_products", "Editar productos"),
            # Módulo Ventas
            ("view_sales", "Ver ventas"),
            ("edit_sales", "Editar ventas"),
            # Módulo Pedidos
            ("view_orders", "Ver pedidos"),
            ("edit_orders", "Editar pedidos"),
            # Módulo Reportes
            ("view_reports", "Ver reportes"),
            # Módulo Reportes Diarios
            ("view_daily_reports", "Ver reportes diarios"),
            # Módulo Trabajadores
            ("view_workers", "Ver trabajadores"),
            ("edit_workers", "Editar trabajadores"),
            # Módulo Parámetros y Materiales
            ("view_parametros_materiales", "Ver parámetros y materiales"),
            ("edit_parametros_materiales", "Editar parámetros y materiales"),
            # Módulo Configuración
            ("view_config", "Ver configuración"),
            ("edit_config", "Editar configuración"),
        ]
        perm_objs = [ensure_perm(c, d) for c, d in perms]
        
        # Vincular TODOS los permisos al rol ADMIN
        if admin_role:
            for p in perm_objs:
                exists = session.query(RolePermission).filter(
                    RolePermission.role_id == admin_role.id, RolePermission.permission_id == p.id
                ).first()
                if not exists:
                    session.add(RolePermission(role_id=admin_role.id, permission_id=p.id))
        
        # Vincular permisos para el rol ADMINISTRACION (similar a ADMIN pero sin configuración)
        if administracion_role:
            # Solo asignar permisos por defecto si el rol no tiene ningún permiso asignado
            existing_perms_count = session.query(RolePermission).filter(RolePermission.role_id == administracion_role.id).count()
            
            if existing_perms_count == 0:
                administracion_perms = [
                    "view_home", "view_customers", "edit_customers",
                    "view_products", "edit_products", "view_sales", "edit_sales",
                    "view_orders", "edit_orders", "view_reports", "view_daily_reports",
                    "view_parametros_materiales", "edit_parametros_materiales"
                ]
                for perm_code in administracion_perms:
                    perm = session.query(Permission).filter(Permission.code == perm_code).first()
                    if perm:
                        session.add(RolePermission(role_id=administracion_role.id, permission_id=perm.id))
        
        # Vincular permisos específicos al rol VENDEDOR
        if vendedor_role:
            # Solo asignar permisos por defecto si el rol no tiene ningún permiso asignado (recién creado)
            # Esto permite que el usuario personalice el rol sin que se sobrescriba al reiniciar
            existing_perms_count = session.query(RolePermission).filter(RolePermission.role_id == vendedor_role.id).count()
            
            if existing_perms_count == 0:
                vendedor_perms = [
                    "view_home", "view_customers", "edit_customers",
                    "view_products", "edit_products", "view_sales", "edit_sales", 
                    "view_orders", "edit_orders"
                ]
                for perm_code in vendedor_perms:
                    perm = session.query(Permission).filter(Permission.code == perm_code).first()
                    if perm:
                        session.add(RolePermission(role_id=vendedor_role.id, permission_id=perm.id))
        
        session.commit()
        # Usuario admin/admin
        admin = session.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin", 
                full_name="Administrador", 
                password_hash=_hash_password("admin"), 
                is_active=True,
                default_role_id=admin_role.id if admin_role else None
            )
            session.add(admin)
            session.commit()
            session.refresh(admin)
        # Asignar rol ADMIN al usuario admin
        if admin_role and not session.query(UserRole).filter(UserRole.user_id == admin.id, UserRole.role_id == admin_role.id).first():
            session.add(UserRole(user_id=admin.id, role_id=admin_role.id))
            session.commit()
        if session.query(Customer).count() == 0:
            session.add_all(
                [
                    Customer(name="Alice", first_name="Alice", last_name="Smith", document="V-12345678", short_address="Av. 1", phone="0414-0000000", email="alice@example.com"),
                    Customer(name="Bob", first_name="Bob", last_name="Lee", document="J-12345678-9", short_address="Calle 2", phone="0412-1111111", email="bob@example.com"),
                    Customer(name="Carol", first_name="Carol", last_name="Chen", document="V-87654321", short_address="Av. 3", phone="0416-2222222", email="carol@example.com"),
                ]
            )
        if session.query(Sale).count() == 0:
            # Crear ventas de ejemplo usando la nueva función add_sale
            with session:
                add_sale(
                    session,
                    articulo="Letras Corpóreas Acrílico",
                    asesor="Juan Pérez",
                    venta_usd=150.0,
                    forma_pago="Efectivo $",
                    serial_billete="AB123456",
                    abono_usd=150.0,
                    ingresos_usd=150.0,  # Ingresos = Abono para efectivo $
                )
                add_sale(
                    session,
                    articulo="Logo LED",
                    asesor="Maria González",
                    venta_usd=280.0,
                    forma_pago="Pago Móvil",
                    banco="Banesco",
                    referencia="123456789",
                    monto_bs=14000.0,
                    abono_usd=100.0,
                    diseno_usd=30.0
                )
                add_sale(
                    session,
                    articulo="Rótulo Acrílico",
                    asesor="Carlos Ruiz",
                    venta_usd=200.0,
                    forma_pago="Efectivo $",
                    serial_billete="CD789012",
                    abono_usd=120.0,  # Solo abonó $120 de $200
                    ingresos_usd=120.0,  # Ingresos = Abono ($120)
                )
        session.commit()

        # Seed materiales base

        # Seed EAV mínimo: tipo y atributos para CORPÓREO
        def ensure_eav_type(key: str, name: str) -> EavProductType:
            t = session.query(EavProductType).filter(EavProductType.key == key).first()
            if not t:
                t = EavProductType(key=key, name=name)
                session.add(t)
                session.commit()
                session.refresh(t)
            return t

        def ensure_eav_attr(code: str, name: str, data_type: str, unit: str | None = None, sort: int = 0, type_id: int | None = None) -> EavAttribute:
            a = session.query(EavAttribute).filter(EavAttribute.code == code).first()
            if not a:
                a = EavAttribute(code=code, name=name, data_type=data_type, unit=unit or None, price_per_unit=0.0, price_affects=False, extra_percent=0.0, visible_expr=None)
                session.add(a)
                session.commit()
                session.refresh(a)
            # asegurar mapeo type-attr
            if type_id is not None:
                ta = (
                    session.query(EavTypeAttribute)
                    .filter(EavTypeAttribute.type_id == type_id, EavTypeAttribute.attribute_id == a.id)
                    .first()
                )
                if not ta:
                    ta = EavTypeAttribute(type_id=type_id, attribute_id=a.id, sort_order=sort)
                    session.add(ta)
                    session.commit()
            return a

        def ensure_option(attribute: EavAttribute, code: str, label: str, price_per_unit: float = 0.0) -> None:
            existing = (
                session.query(EavAttributeOption)
                .filter(EavAttributeOption.attribute_id == attribute.id, EavAttributeOption.code == code)
                .first()
            )
            if not existing:
                op = EavAttributeOption(attribute_id=attribute.id, code=code, label=label, price_per_unit=price_per_unit)
                session.add(op)
                session.commit()

        # EAV seed eliminado - ya no hay referencias a Corpóreo

        # Todas las opciones EAV eliminadas junto con el módulo Corpóreo
        # Seed de producto SELLO con categorías/modelos (si no existen)

        # Configuración por defecto del sistema
        from .models import SystemConfig as SysConfig
        if session.query(SysConfig).count() == 0:
            default_configs = [
                SysConfig(
                    config_key="monthly_sales_goal",
                    config_value="12000.0",
                    description="Meta mensual de ventas en USD"
                )
            ]
            session.add_all(default_configs)
            session.commit()

        # ...existing code...



# (CRUD de productos eliminado)


def list_customers(session: Session) -> list[Customer]:
    """Lista todos los clientes ordenados por ID."""
    try:
        return session.query(Customer).order_by(Customer.id.asc()).all()
    except Exception:
        session.rollback()
        raise


def add_customers(session: Session, customers: Iterable[Customer]) -> None:
    """Añade una lista de clientes a la base de datos."""
    try:
        customer_list = list(customers)  # Materializar la lista antes de añadir
        session.add_all(customer_list)
        session.commit()
    except Exception:
        session.rollback()
        raise


def get_customer_by_id(session: Session, customer_id: int) -> Customer | None:
    """Obtiene un cliente por su ID."""
    try:
        return session.get(Customer, customer_id)
    except Exception:
        session.rollback()
        raise


def delete_customer_by_id(session: Session, customer_id: int) -> bool:
    obj = session.get(Customer, customer_id)
    if not obj:
        return False
    session.delete(obj)
    session.commit()
    return True


def update_customer(session: Session, customer_id: int, *, name: str, email: str | None) -> bool:
    obj = session.get(Customer, customer_id)
    if not obj:
        return False
    obj.name = name
    obj.email = email
    session.commit()
    return True


def count_customers(session: Session) -> int:
    return session.query(Customer).count()


"""
APIs EAV y Productos: mantenemos un set mínimo para soportar el configurador Corpóreo.
"""

# --- EAV APIs ---

def eav_list_types(session: Session) -> list[EavProductType]:
    return session.query(EavProductType).order_by(EavProductType.name.asc()).all()


def eav_list_products(session: Session, *, type_id: int) -> list[EavProduct]:
    return session.query(EavProduct).filter(EavProduct.type_id == type_id).order_by(EavProduct.id.desc()).all()


def eav_create_product(session: Session, *, type_id: int, name: str) -> EavProduct:
    obj = EavProduct(type_id=type_id, name=name)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def eav_list_attributes_for_type(session: Session, type_id: int) -> list[tuple[EavAttribute, list[EavAttributeOption]]]:
    # Obtener atributos asociados al tipo y sus opciones
    tas = (
        session.query(EavTypeAttribute)
        .filter(EavTypeAttribute.type_id == type_id)
        .order_by(EavTypeAttribute.sort_order.asc(), EavTypeAttribute.id.asc())
        .all()
    )
    result: list[tuple[EavAttribute, list[EavAttributeOption]]] = []
    for ta in tas:
        atr = session.get(EavAttribute, ta.attribute_id)
        if not atr:
            continue
        opts = (
            session.query(EavAttributeOption)
            .filter(EavAttributeOption.attribute_id == atr.id)
            .order_by(EavAttributeOption.id.asc())
            .all()
        )
        result.append((atr, opts))
    return result


# --- EAV helpers mínimos para Corpóreo ---
def eav_get_attribute_by_code(session: Session, code: str) -> EavAttribute | None:
    return session.query(EavAttribute).filter(EavAttribute.code == code).first()


def eav_add_option(session: Session, *, attribute_code: str, code: str, label: str, price_per_unit: float | None = None) -> EavAttributeOption | None:
    atr = eav_get_attribute_by_code(session, attribute_code)
    if not atr:
        return None
    existing = (
        session.query(EavAttributeOption)
        .filter(EavAttributeOption.attribute_id == atr.id, EavAttributeOption.code == code)
        .first()
    )
    if existing:
        return existing
    op = EavAttributeOption(attribute_id=atr.id, code=code, label=label, price_per_unit=float(price_per_unit or 0.0))
    session.add(op)
    session.commit()
    session.refresh(op)
    return op


def eav_set_option_price(session: Session, *, option_id: int, price_per_unit: float) -> None:
    op = session.get(EavAttributeOption, option_id)
    if not op:
        return
    op.price_per_unit = float(price_per_unit or 0.0)
    session.commit()


def eav_save_values(session: Session, *, product_id: int, values: list[tuple[int, dict]]) -> None:
    """Guarda valores para un producto EAV. values: [(attribute_id, {value_*...}), ...]"""
    # Estrategia simple: borrar valores previos de esos atributos y volver a insertar
    attr_ids = [aid for aid, _ in values]
    if attr_ids:
        session.query(EavValue).filter(EavValue.product_id == product_id, EavValue.attribute_id.in_(attr_ids)).delete(synchronize_session=False)
    for aid, payload in values:
        v = EavValue(
            product_id=product_id,
            attribute_id=aid,
            value_text=payload.get('value_text'),
            value_number=payload.get('value_number'),
            option_id=payload.get('option_id'),
            value_bool=payload.get('value_bool'),
            subtotal_money=float(payload.get('subtotal_money', 0.0) or 0.0),
        )
        session.add(v)
    session.commit()


def eav_get_product_values(session: Session, *, product_id: int) -> dict:
    rows = (
        session.query(EavValue, EavAttribute)
        .join(EavAttribute, EavAttribute.id == EavValue.attribute_id)
        .filter(EavValue.product_id == product_id)
        .all()
    )
    out = {}
    for v, atr in rows:
        out[atr.code] = {
            'text': v.value_text,
            'number': v.value_number,
            'option_id': v.option_id,
            'bool': v.value_bool,
            'subtotal': v.subtotal_money,
        }
    return out


def ensure_corporeo_eav(session: Session) -> int:
    """Asegura el tipo y atributos/opciones mínimas para Corpóreo. Retorna type_id."""
    # Tipo
    t = session.query(EavProductType).filter(EavProductType.key == 'CORPOREO').first()
    if not t:
        t = EavProductType(key='CORPOREO', name='Corpóreo')
        session.add(t)
        session.commit()
        session.refresh(t)
    type_id = int(t.id)
    # Helper attr
    def ensure_attr(code: str, name: str, data_type: str, unit: str | None = None, sort: int = 0) -> EavAttribute:
        a = session.query(EavAttribute).filter(EavAttribute.code == code).first()
        if not a:
            a = EavAttribute(code=code, name=name, data_type=data_type, unit=unit, price_per_unit=0.0, price_affects=False, extra_percent=0.0, visible_expr=None)
            session.add(a)
            session.commit(); session.refresh(a)
        # relación type-attr
        ta = (
            session.query(EavTypeAttribute)
            .filter(EavTypeAttribute.type_id == type_id, EavTypeAttribute.attribute_id == a.id)
            .first()
        )
        if not ta:
            ta = EavTypeAttribute(type_id=type_id, attribute_id=a.id, sort_order=sort)
            session.add(ta); session.commit()
        return a
    def ensure_opts(atr: EavAttribute, items: list[tuple[str, str]]):
        for code, label in items:
            existing = (
                session.query(EavAttributeOption)
                .filter(EavAttributeOption.attribute_id == atr.id, EavAttributeOption.code == code)
                .first()
            )
            if not existing:
                session.add(EavAttributeOption(attribute_id=atr.id, code=code, label=label, price_per_unit=0.0))
        session.commit()
    # Atributos y opciones mínimas
    sort = 0
    ensure_attr('alto_mm', 'Alto (mm)', 'number', unit='mm', sort=sort); sort += 1
    ensure_attr('ancho_mm', 'Ancho (mm)', 'number', unit='mm', sort=sort); sort += 1
    ensure_attr('diametro_mm', 'Diámetro (mm)', 'number', unit='mm', sort=sort); sort += 1
    atr_corte = ensure_attr('corte_tipo', 'Tipo de Corte', 'option', sort=sort); sort += 1
    ensure_opts(atr_corte, [('recto', 'Recto'), ('silueta', 'Silueta'), ('redondo', 'Redondo')])
    atr_mat = ensure_attr('material', 'Material', 'option', sort=sort); sort += 1
    ensure_opts(atr_mat, [('acrilico', 'Acrílico'), ('mdf', 'MDF'), ('pvc', 'PVC Espumado')])
    atr_esp = ensure_attr('espesor_mm', 'Espesor', 'option', sort=sort); sort += 1
    ensure_opts(atr_esp, [('3', '3 mm'), ('5', '5 mm'), ('10', '10 mm'), ('15', '15 mm')])
    atr_base = ensure_attr('base_tipo', 'Tipo de Base', 'option', sort=sort); sort += 1
    ensure_opts(atr_base, [('sin', 'Sin base'), ('mdf', 'MDF'), ('acrilico', 'Acrílico'), ('pvc', 'PVC')])
    ensure_attr('base_color_code', 'Código Color', 'text', sort=sort); sort += 1
    ensure_attr('corporeo_modelos', 'Modelos Seleccionados', 'text', sort=sort); sort += 1
    atr_luz_t = ensure_attr('luces_tipo', 'Tipo de Luz', 'option', sort=sort); sort += 1
    ensure_opts(atr_luz_t, [('cinta', 'Cinta LED'), ('manguera', 'Neón manguera'), ('ceo', 'CEO')])
    atr_luz_c = ensure_attr('luces_color', 'Color de Luz', 'option', sort=sort); sort += 1
    ensure_opts(atr_luz_c, [('calido', 'Cálido'), ('frio', 'Frío'), ('rgb', 'RGB')])
    ensure_attr('luces_long_m', 'Longitud (m)', 'number', unit='m', sort=sort); sort += 1
    ensure_attr('luces_precio_unit', 'Precio unit luz', 'money', sort=sort); sort += 1
    atr_reg = ensure_attr('regulador_amp', 'Regulador (Amp)', 'option', sort=sort); sort += 1
    ensure_opts(atr_reg, [('3A', '3A'), ('5A', '5A'), ('7A', '7A')])
    ensure_attr('regulador_cant', 'Cant. Regulador', 'number', sort=sort); sort += 1
    atr_pos_luz = ensure_attr('posicion_luz', 'Posición de Luz', 'option', sort=sort); sort += 1
    ensure_opts(atr_pos_luz, [('frontal', 'Frontal'), ('posterior', 'Posterior'), ('borde', 'Borde')])
    atr_pos_borde = ensure_attr('posicion_borde', 'Borde', 'option', sort=sort); sort += 1
    ensure_opts(atr_pos_borde, [('plano', 'Plano'), ('biselado', 'Biselado')])
    ensure_attr('silueta_extra', 'Silueta $/m²', 'money', sort=sort); sort += 1
    ensure_attr('caja_de_luz', 'Caja de Luz', 'bool', sort=sort); sort += 1
    ensure_attr('caja_de_luz_pct', '% Caja de Luz', 'number', sort=sort); sort += 1
    return type_id




def set_product_bom(session: Session, product_id: int, items: list[tuple[int, float, float]]) -> None:
    pass

        # Funciones de BOM eliminadas


# Sales API
def list_sales(session: Session) -> list[Sale]:
    return session.query(Sale).order_by(Sale.id.desc()).all()


def generate_order_number(session: Session) -> str:
    """Genera un número de orden único con formato 000000 (6 dígitos)."""
    
    # Obtener todos los números de orden
    existing_orders = session.query(Sale.numero_orden).all()
    
    max_num = 0
    for (order_num,) in existing_orders:
        if not order_num:
            continue
        
        # Intentar extraer número de formatos conocidos
        try:
            # Formato nuevo: "000001"
            if order_num.isdigit():
                seq_num = int(order_num)
                max_num = max(max_num, seq_num)
            # Formato antiguo: "ORD-0001"
            elif order_num.startswith("ORD-") and len(order_num) >= 5:
                num_part = order_num[4:]
                if num_part.isdigit():
                    seq_num = int(num_part)
                    max_num = max(max_num, seq_num)
        except ValueError:
            continue
    
    next_num = max_num + 1
    return f"{next_num:06d}"


def get_bcv_rate() -> float:
    """Obtiene la tasa BCV actual. Por ahora devuelve una tasa fija, luego se puede integrar con API."""
    # TODO: Integrar con API del BCV o sistema de exchange existente
    try:
        from .exchange import get_bcv_rate as get_exchange_rate
        rate = get_exchange_rate()
        return rate if rate is not None else 50.0
    except (ImportError, AttributeError):
        # Tasa por defecto si no hay sistema de exchange
        return 50.0


def calculate_usd_from_bs(amount_bs: float, bcv_rate: float) -> float:
    """Calcula el equivalente en USD basado en el monto en Bs y la tasa BCV."""
    if bcv_rate > 0:
        return amount_bs / bcv_rate
    return 0.0


def calculate_remaining(total_usd: float, down_payment_usd: float) -> float:
    """Calcula el restante basado en el total y el abono."""
    return max(0.0, total_usd - (down_payment_usd or 0.0))


def add_sale(
    session: Session,
    *,
    articulo: str,
    asesor: str,
    venta_usd: float,
    forma_pago: str | None = None,
    serial_billete: str | None = None,
    banco: str | None = None,
    referencia: str | None = None,
    fecha_pago: datetime | None = None,
    monto_bs: float | None = None,
    monto_usd_calculado: float | None = None,
    abono_usd: float | None = None,
    iva: float | None = None,
    diseno_usd: float | None = None,
    ingresos_usd: float | None = None,
    notes: str | None = None,
    descripcion: str | None = None,
    cantidad: float | None = None,
    precio_unitario: float | None = None,
    total_bs: float | None = None,
    cliente_id: int | None = None,
    created_by: str | None = None,
    # Campos opcionales provenientes del formulario (si se pasan)
    incluye_diseno: bool | None = None,
    subtotal_usd: float | None = None,
    total_usd: float | None = None,
    notas: str | None = None,
    cliente: str | None = None,
    tasa_bcv_input: float | None = None,
    precio_unitario_input: float | None = None,
    corporeo_payload: dict | None = None,
    items: list[dict] | None = None,
    payments: list[dict] | None = None,
) -> Sale:
    """Crea una nueva venta con cálculos automáticos."""
    
    # Generar número de orden único con reintentos en caso de duplicación
    max_retries = 5
    numero_orden = None
    for attempt in range(max_retries):
        try:
            numero_orden = generate_order_number(session)
            # Verificar que no existe (extra precaución)
            existing = session.query(Sale).filter(Sale.numero_orden == numero_orden).first()
            if not existing:
                break
        except Exception:
            pass
        if attempt == max_retries - 1:
            # Fallback: usar timestamp para garantizar unicidad
            import time
            timestamp = int(time.time()) % 100000  # Últimos 5 dígitos del timestamp
            numero_orden = f"ORD-{timestamp:05d}"
    
    # Determinar tasa BCV a usar. Preferir valor explícito pasado por el caller
    tasa_bcv = None
    if tasa_bcv_input is not None:
        try:
            tasa_bcv = float(tasa_bcv_input)
        except Exception:
            tasa_bcv = None

    # Si no se proporcionó tasa y hay monto en Bs, resolver tasa según la fecha de pago (si existe)
    if tasa_bcv is None and monto_bs and monto_bs > 0:
        try:
            if fecha_pago is not None:
                from .exchange import get_rate_for_date
                rate_for_date = get_rate_for_date(fecha_pago)
                if rate_for_date and float(rate_for_date) > 0:
                    tasa_bcv = float(rate_for_date)
            # Fallback a tasa actual si no se pudo obtener por fecha
            if tasa_bcv is None:
                tasa_bcv = get_bcv_rate()
        except Exception:
            try:
                tasa_bcv = get_bcv_rate()
            except Exception:
                tasa_bcv = None

    # Calcular monto_usd_calculado si es necesario
    if monto_usd_calculado is None and monto_bs and monto_bs > 0 and tasa_bcv:
        monto_usd_calculado = calculate_usd_from_bs(monto_bs, tasa_bcv)
    
    # Calcular restante
    restante = calculate_remaining(venta_usd, abono_usd or 0.0)
    
    # Calcular ingresos automáticamente si no se especifica y la forma de pago es efectivo $ o Zelle
    if ingresos_usd is None and forma_pago in ["Efectivo $", "Zelle"] and abono_usd is not None:
        ingresos_usd = abono_usd
    
    obj = Sale(
        numero_orden=numero_orden,
        articulo=articulo,
        asesor=asesor,
        venta_usd=venta_usd,
        forma_pago=forma_pago,
        serial_billete=serial_billete,
        banco=banco,
        referencia=referencia,
        fecha_pago=fecha_pago,
        monto_bs=monto_bs,
    monto_usd_calculado=monto_usd_calculado,
    tasa_bcv=tasa_bcv,
        abono_usd=abono_usd,
        restante=restante,
        iva=iva,
        diseno_usd=diseno_usd,
        ingresos_usd=ingresos_usd,
        notes=notes,
        cliente=cliente,
        cliente_id=cliente_id,
        descripcion=saned_desc if ('saned_desc' in locals()) else (descripcion or None),
        cantidad=float(cantidad or 1.0),
        precio_unitario=float(precio_unitario or venta_usd),
        total_bs=float(total_bs or monto_bs or 0.0),
        details_json=None,
    )
    session.add(obj)

    # Intentar crear venta y pedido (si aplica) en la misma transacción
    try:
        # Flush para obtener obj.id sin hacer commit
        session.flush()
        session.refresh(obj)

        # Guardar items si existen
        if items:
            from .models import SaleItem
            for item in items:
                si = SaleItem(
                    sale_id=obj.id,
                    product_name=item.get('product_name', 'Unknown'),
                    quantity=float(item.get('quantity', 1.0)),
                    unit_price=float(item.get('unit_price', 0.0)),
                    total_price=float(item.get('total_price', 0.0)),
                    details_json=json.dumps(item.get('details', {})) if isinstance(item.get('details'), dict) else None
                )
                session.add(si)

        # Guardar pagos si existen
        if payments:
            from .models import SalePayment
            for pay in payments:
                # Parsear fecha
                p_date = datetime.utcnow()
                if pay.get('payment_date'):
                    try:
                        if isinstance(pay.get('payment_date'), str):
                            p_date = datetime.strptime(pay.get('payment_date'), "%Y-%m-%d")
                        elif isinstance(pay.get('payment_date'), datetime):
                            p_date = pay.get('payment_date')
                    except:
                        pass
                
                sp = SalePayment(
                    sale_id=obj.id,
                    payment_method=pay.get('payment_method', 'Unknown'),
                    amount_usd=float(pay.get('amount_usd', 0.0)),
                    amount_bs=float(pay.get('amount_bs', 0.0)),
                    exchange_rate=float(pay.get('exchange_rate', 0.0)),
                    reference=pay.get('reference'),
                    bank=pay.get('bank'),
                    payment_date=p_date
                )
                session.add(sp)

        # Determinar si crear pedido
        # Antes se filtraba por 'corp' o descripción. Ahora, por solicitud del usuario,
        # se asume que toda venta genera un pedido (para seguimiento de estado).
        create_order = True

        created_order_id = None
        if create_order:
            # Construir detalles estructurados para facilitar búsquedas
            # Sanear la descripción: eliminar segmentos de subtotal/total que el usuario haya pegado
            saned_desc = ''
            try:
                if descripcion:
                    import re
                    saned_desc = str(descripcion)
                    # Eliminar patrones como 'Subtotal: 82.00', 'Total: 82:00', 'Subtotal:82' (variantes)
                    saned_desc = re.sub(r"(?im)\bsubtotal\b\s*[:\-]?\s*[0-9.,]+", '', saned_desc)
                    saned_desc = re.sub(r"(?im)\btotal\b\s*[:\-]?\s*[0-9.,]+", '', saned_desc)
                    # Eliminar etiquetas aisladas 'Subtotal:' o 'Total:'
                    saned_desc = re.sub(r"(?im)\bsubtotal\b\s*[:\-]\s*", '', saned_desc)
                    saned_desc = re.sub(r"(?im)\btotal\b\s*[:\-]\s*", '', saned_desc)
                    # Limpiar espacios repetidos y separadores finales
                    saned_desc = re.sub(r"[\s\-]{2,}", ' ', saned_desc).strip()
            except Exception:
                saned_desc = descripcion or ''

            # If a structured payload for corporeo was provided, prefer it
            if corporeo_payload and isinstance(corporeo_payload, dict):
                details_struct = corporeo_payload.copy()
                # ensure meta exists
                if 'meta' not in details_struct or not isinstance(details_struct.get('meta'), dict):
                    details_struct['meta'] = details_struct.get('meta') or {}
            else:
                details_struct = {
                'descripcion_text': saned_desc or '',
                'items': [
                    {
                        'cantidad': float(cantidad or 1.0),
                        'precio_unitario': float(precio_unitario or obj.venta_usd),
                        'subtotal_usd': float(venta_usd or 0.0)
                    }
                ],
                'totals': {
                    'total_usd': float(obj.venta_usd or 0.0),
                    'total_bs': float(total_bs or obj.monto_bs or 0.0)
                },
                'meta': {
                    'product_name': obj.articulo or '',
                    'cliente_id': int(cliente_id) if cliente_id is not None else None,
                    # Campos adicionales del formulario (usar valores pasados o fallback)
                    'cliente': (str(cliente) if cliente is not None else None),
                    'incluye_diseno': bool(incluye_diseno) if incluye_diseno is not None else False,
                    'subtotal_usd': float(subtotal_usd) if subtotal_usd is not None else 0.0,
                    'total_usd': float(total_usd) if total_usd is not None else float(obj.venta_usd or 0.0),
                    'notas': (str(notas) if notas is not None else None),
                    'tasa_bcv': float(tasa_bcv_input) if tasa_bcv_input is not None else (float(tasa_bcv) if tasa_bcv is not None else None),
                    'precio_unitario': float(precio_unitario_input) if precio_unitario_input is not None else float(precio_unitario or obj.venta_usd),
                    'created_by': created_by or None,
                }
            }
            # Crear order dentro de la misma sesión antes del commit. Añadir order_number al payload
            # Usar el mismo número de orden de la venta
            order_number = obj.numero_orden
            try:
                details_struct.setdefault('meta', {})
                details_struct['meta']['order_number'] = order_number
            except Exception:
                pass

            order_obj = Order(
                sale_id=int(obj.id),
                order_number=order_number,
                product_name=(obj.articulo or ''),
                details_json=json.dumps(details_struct, ensure_ascii=False),
                status='NUEVO'
            )
            session.add(order_obj)
            # Flush para asignar ID a order_obj (si esto falla, la excepción propagará y haremos rollback)
            session.flush()
            created_order_id = int(order_obj.id)

        # Commit final de la transacción que incluye venta y pedido (si se creó)
        # Before commit, populate details_json field of sale (structured)
        try:
            details_for_sale = {
                'descripcion_text': (details_struct.get('descripcion_text') if isinstance(details_struct, dict) else ''),
                'totals': details_struct.get('totals') if isinstance(details_struct, dict) else {},
                'meta': details_struct.get('meta') if isinstance(details_struct, dict) else {},
                'items': details_struct.get('items') if isinstance(details_struct, dict) else [],
            }
            obj.details_json = json.dumps(details_for_sale, ensure_ascii=False)
        except Exception:
            pass
        session.commit()
        session.refresh(obj)
        if created_order_id:
            try:
                from .events import events
                events.order_created.emit(created_order_id)
            except Exception:
                pass
        # Adjuntar info del pedido creado (si aplica) al objeto devuelto
        if created_order_id:
            try:
                setattr(obj, 'created_order_id', created_order_id)
            except Exception:
                pass
        return obj
    except Exception as e:
        session.rollback()
        # Si hay error de constraint UNIQUE en numero_orden, intentar con nuevo número
        if "UNIQUE constraint failed: sales.numero_orden" in str(e):
            # Generar un número de orden alternativo con timestamp
            import time
            timestamp = int(time.time()) % 100000  # Últimos 5 dígitos del timestamp
            obj.numero_orden = f"ORD-{timestamp:05d}"
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return obj
        else:
            # Re-lanzar otros errores
            raise


def update_sale(session: Session, sale_id: int, **fields) -> bool:
    obj = session.get(Sale, sale_id)
    if not obj:
        return False
    
    # Manejo especial para relaciones (items y payments)
    if 'items' in fields:
        items_data = fields.pop('items')
        if isinstance(items_data, list):
            # Eliminar items existentes
            for item in obj.items:
                session.delete(item)
            obj.items = [] # Limpiar relación en memoria
            
            # Crear nuevos items
            for item_dict in items_data:
                new_item = SaleItem(
                    product_name=item_dict.get('product_name', 'Desconocido'),
                    quantity=float(item_dict.get('quantity', 1.0)),
                    unit_price=float(item_dict.get('unit_price', 0.0)),
                    total_price=float(item_dict.get('total_price', 0.0)),
                    details_json=json.dumps(item_dict.get('details', {}), ensure_ascii=False) if item_dict.get('details') else None
                )
                obj.items.append(new_item)

    if 'payments' in fields:
        payments_data = fields.pop('payments')
        if isinstance(payments_data, list):
            # Eliminar pagos existentes
            for pay in obj.payments:
                session.delete(pay)
            obj.payments = [] # Limpiar relación en memoria
            
            # Crear nuevos pagos
            for pay_dict in payments_data:
                # Convertir fecha si viene como string
                p_date = pay_dict.get('payment_date')
                if isinstance(p_date, str) and p_date:
                    try:
                        p_date = datetime.strptime(p_date, "%Y-%m-%d")
                    except:
                        p_date = datetime.utcnow()
                elif not p_date:
                    p_date = datetime.utcnow()

                new_pay = SalePayment(
                    payment_method=pay_dict.get('payment_method', 'Desconocido'),
                    amount_usd=float(pay_dict.get('amount_usd', 0.0)),
                    amount_bs=float(pay_dict.get('amount_bs', 0.0)),
                    exchange_rate=float(pay_dict.get('exchange_rate', 0.0)),
                    reference=pay_dict.get('reference'),
                    bank=pay_dict.get('bank'),
                    payment_date=p_date
                )
                obj.payments.append(new_pay)

    # Actualizar campos simples
    for k, v in fields.items():
        if hasattr(obj, k):
            setattr(obj, k, v)
    
    # Recalcular campos automáticos si es necesario
    if 'monto_bs' in fields and fields['monto_bs'] and 'monto_usd_calculado' not in fields:
        tasa_bcv = get_bcv_rate()
        if tasa_bcv:
            obj.monto_usd_calculado = calculate_usd_from_bs(fields['monto_bs'], tasa_bcv)
    
    if 'venta_usd' in fields or 'abono_usd' in fields:
        obj.restante = calculate_remaining(obj.venta_usd or 0.0, obj.abono_usd or 0.0)
    
    # Calcular ingresos automáticamente si no se especifica y la forma de pago es efectivo $ o Zelle
    if 'forma_pago' in fields or 'abono_usd' in fields:
        if obj.forma_pago in ["Efectivo $", "Zelle"] and obj.abono_usd is not None:
            if 'ingresos_usd' not in fields:  # Solo si no se especifica manualmente
                obj.ingresos_usd = obj.abono_usd
    
    # If caller provided a details_json or any of the structured fields, update details_json
    if 'details_json' in fields and fields.get('details_json') is not None:
        try:
            obj.details_json = fields.get('details_json')
        except Exception:
            pass
    else:
        # Try to recompute a minimal details_json from available fields
        try:
            meta = {
                'cliente': getattr(obj, 'cliente', None),
                'cliente_id': getattr(obj, 'cliente_id', None),
                'tasa_bcv': getattr(obj, 'tasa_bcv', None),
            }
            items = [{'cantidad': getattr(obj, 'cantidad', 1.0), 'precio_unitario': getattr(obj, 'precio_unitario', getattr(obj, 'venta_usd', 0.0))}]
            totals = {'total_usd': getattr(obj, 'venta_usd', 0.0), 'total_bs': getattr(obj, 'total_bs', getattr(obj, 'monto_bs', 0.0))}
            obj.details_json = json.dumps({'meta': meta, 'items': items, 'totals': totals}, ensure_ascii=False)
        except Exception:
            pass
    session.commit()
    return True


def delete_sale_by_id(session: Session, sale_id: int) -> bool:
    obj = session.get(Sale, sale_id)
    if not obj:
        return False
    
    # Delete associated orders first to maintain consistency
    orders = session.query(Order).filter(Order.sale_id == sale_id).all()
    for order in orders:
        # Also clean up Corporeo payloads/configs linked to this order
        session.query(CorporeoPayload).filter(CorporeoPayload.order_id == order.id).delete()
        session.query(CorporeoConfig).filter(CorporeoConfig.order_id == order.id).delete()
        session.delete(order)
    
    # Clean up any Corporeo payloads/configs linked directly to the sale (if any remain)
    session.query(CorporeoPayload).filter(CorporeoPayload.sale_id == sale_id).delete()
    session.query(CorporeoConfig).filter(CorporeoConfig.sale_id == sale_id).delete()
        
    session.delete(obj)
    session.commit()
    return True


def get_sale_by_id(session: Session, sale_id: int) -> Sale | None:
    return session.get(Sale, sale_id)


# --- Order numbering ---

def get_next_order_number(session: Session) -> str:
    """Genera el siguiente número de orden secuencial por año (ej: ORD-2025-1)."""
    from datetime import datetime
    current_year = datetime.now().year
    # Buscar o crear la secuencia para el año actual
    sequence = session.query(OrderSequence).filter(OrderSequence.year == current_year).first()
    if not sequence:
        sequence = OrderSequence(year=current_year, last_number=0)
        session.add(sequence)
        session.flush()  # Para obtener el ID y persistir en la sesión

    # Incrementar el número y flush (NO commit aquí, dejar commit al scope externo)
    sequence.last_number += 1
    session.flush()

    # Generar código de orden
    return f"ORD-{current_year}-{sequence.last_number:03d}"


def get_sale_display_number(sale_id: int, payment_date: Optional[datetime] = None) -> str:
    if payment_date:
        date_part = payment_date.strftime('%Y%m%d')
        return f"V-{date_part}-{sale_id:03d}"
    else:
        from datetime import datetime
        current_date = datetime.now().strftime('%Y%m%d')
        return f"V-{current_date}-{sale_id:03d}"


# --- Orders ---

def add_order(session: Session, *, sale_id: int, product_name: str, details_json: str, status: str | None = "NUEVO", order_number: str | None = None) -> Order:
    """Crear un pedido relacionado con una venta.

    Si se pasa `order_number`, se usa ese número en lugar de generar uno nuevo. Esto permite
    enlazar el pedido con la venta usando el mismo número de orden.
    """
    if order_number is None:
        order_number = get_next_order_number(session)
    obj = Order(
        sale_id=sale_id,
        order_number=order_number,
        product_name=product_name,
        details_json=details_json,
        status=status,
    )
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def add_corporeo_config(session: Session, *, sale_id: int | None = None, order_id: int | None = None, product_id: int | None = None, payload: dict | None = None, computed: dict | None = None) -> 'CorporeoConfig':
    """Crea o actualiza una entrada en `corporeo_configs` vinculada a una venta/pedido."""
    # lazy import to avoid circular
    from .models import CorporeoConfig
    pj = None
    try:
        import json
        pj = json.dumps(payload or {}, ensure_ascii=False)
    except Exception:
        pj = str(payload or {})
    cfg = CorporeoConfig(
        sale_id=int(sale_id) if sale_id is not None else None,
        order_id=int(order_id) if order_id is not None else None,
        order_number=(computed.get('order_number') if isinstance(computed, dict) else None) if computed else None,
        product_id=int(product_id) if product_id is not None else None,
        cliente_id=(computed.get('cliente_id') if isinstance(computed, dict) else None) if computed else None,
        soporte_model_id=(computed.get('soporte_model_id') if isinstance(computed, dict) else None) if computed else None,
        soporte_qty=(computed.get('soporte_qty') if isinstance(computed, dict) else None) if computed else None,
        luz_pv_id=(computed.get('luz_pv_id') if isinstance(computed, dict) else None) if computed else None,
        luz_price=(computed.get('luz_price') if isinstance(computed, dict) else None) if computed else None,
        posicion_luz=(computed.get('posicion_luz') if isinstance(computed, dict) else None) if computed else None,
        precio_total_usd=(computed.get('precio_total_usd') if isinstance(computed, dict) else None) if computed else None,
        precio_total_bs=(computed.get('precio_total_bs') if isinstance(computed, dict) else None) if computed else None,
        payload_json=pj,
    )
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


def get_corporeo_by_order(session: Session, order_id: int) -> 'CorporeoConfig | None':
    from .models import CorporeoConfig
    try:
        # Accept either numeric order_id or order_number (string)
        if isinstance(order_id, (str,)) and not str(order_id).isdigit():
            return session.query(CorporeoConfig).filter(CorporeoConfig.order_number == str(order_id)).order_by(CorporeoConfig.id.desc()).first()
        return session.query(CorporeoConfig).filter(CorporeoConfig.order_id == int(order_id)).order_by(CorporeoConfig.id.desc()).first()
    except Exception:
        return None


def get_corporeo_by_sale(session: Session, sale_id: int) -> 'CorporeoConfig | None':
    from .models import CorporeoConfig
    try:
        return session.query(CorporeoConfig).filter(CorporeoConfig.sale_id == int(sale_id)).order_by(CorporeoConfig.id.desc()).first()
    except Exception:
        return None


def update_corporeo_config(session: Session, config_id: int, *, payload: dict | None = None, computed: dict | None = None) -> bool:
    from .models import CorporeoConfig
    cfg = session.get(CorporeoConfig, int(config_id))
    if not cfg:
        return False
    try:
        import json
        if payload is not None:
            cfg.payload_json = json.dumps(payload, ensure_ascii=False)
        if computed and isinstance(computed, dict):
            for k, v in computed.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False


def reserve_draft_order(session: Session, *, sale_id: int | None = None, product_name: str = '') -> Order:
    """Create a draft order placeholder (details_json='{}') and return it.

    If sale_id is None the order will be created with sale_id=0 as a placeholder
    and can be updated later (caller is responsible to reassign or update). This
    function commits and returns the created Order.
    """
    # use get_next_order_number for a unique order_number even for drafts
    order_number = get_next_order_number(session)
    sid = int(sale_id) if sale_id is not None else 0
    obj = Order(
        sale_id=sid,
        order_number=order_number,
        product_name=(product_name or '')[:200],
        details_json='{}',
        status='BORRADOR'
    )
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj

def list_orders(session: Session, filter_user: Optional[str] = None) -> list[Order]:
    from .models import Sale
    query = session.query(Order).options(joinedload(Order.sale), joinedload(Order.designer))
    
    if filter_user:
        query = query.join(Order.sale).filter(Sale.asesor == filter_user)
        
    return query.order_by(Order.id.desc()).all()

def get_order_by_id(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)

def get_order_full(session: Session, order_id: int) -> Order | None:
    """Retorna el pedido con sus relaciones cargadas (sale, designer)."""
    return session.query(Order).options(joinedload(Order.sale), joinedload(Order.designer)).filter(Order.id == order_id).first()



def get_order_for_sale(session: Session, sale_id: int) -> Order | None:
    """Retorna el primer pedido asociado a una venta (o None)."""
    try:
        return session.query(Order).filter(Order.sale_id == int(sale_id)).order_by(Order.id.desc()).first()
    except Exception:
        return None

def update_order(session: Session, order_id: int, **fields) -> bool:
    obj = session.get(Order, order_id)
    if not obj:
        return False
    for k, v in fields.items():
        if hasattr(obj, k):
            setattr(obj, k, v)
    session.commit()
    return True


def add_corporeo_payload(session: Session, *, sale_id: int | None = None, order_id: int | None = None, order_number: str | None = None, product_id: int | None = None, payload: dict | None = None, computed: dict | None = None) -> 'CorporeoPayload':
    """Crear o actualizar un registro en `corporeo_payloads`.

    Si existe un registro previo para la misma venta se crea uno nuevo (registro histórico). Devuelve la instancia.
    """
    from .models import CorporeoPayload
    import json

    p = CorporeoPayload(
        order_id=order_id,
        order_number=order_number,
        sale_id=sale_id,
        product_id=product_id,
        payload_json=(json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else None),
        # Populate some quick access columns from payload if available
        nombre=(payload.get('nombre') if isinstance(payload, dict) else None),
        descripcion_user=(payload.get('descripcion_user') if isinstance(payload, dict) else None),
        subtotal=(float(payload.get('subtotal')) if isinstance(payload, dict) and payload.get('subtotal') is not None else None),
        total=(float(payload.get('total')) if isinstance(payload, dict) and payload.get('total') is not None else None),
    )
    # try to extract common nested values
    try:
        if isinstance(payload, dict):
            med = payload.get('medidas') or {}
            p.alto_cm = float(med.get('alto_cm') or 0.0) if med else None
            p.ancho_cm = float(med.get('ancho_cm') or 0.0) if med else None
            p.diam_mm = float(med.get('diam_mm') or 0.0) if med else None
            p.area_m2 = float(med.get('area_m2') or 0.0) if med else None
            mat = payload.get('material') or {}
            p.material_label = mat.get('label') if isinstance(mat, dict) else None
            p.material_id = mat.get('id') if isinstance(mat, dict) else None
            esp = payload.get('espesor') or {}
            p.espesor_label = esp.get('label') if isinstance(esp, dict) else None
            p.espesor_id = esp.get('id') if isinstance(esp, dict) else None
            p.espesor_price = float(esp.get('price') or 0.0) if isinstance(esp, dict) and esp.get('price') is not None else None
            sup = payload.get('soporte') or {}
            p.soporte_model = sup.get('model') if isinstance(sup, dict) else None
            p.soporte_size = sup.get('size') if isinstance(sup, dict) else None
            try:
                p.soporte_qty = int(sup.get('qty')) if isinstance(sup, dict) and sup.get('qty') is not None else None
            except Exception:
                p.soporte_qty = None
            try:
                p.soporte_price = float(sup.get('price')) if isinstance(sup, dict) and sup.get('price') is not None else None
            except Exception:
                p.soporte_price = None
            luces = payload.get('luces') or {}
            if isinstance(luces, dict):
                sel = luces.get('selected') or []
                if isinstance(sel, list) and sel:
                    first = sel[0] or {}
                    p.luz_pv_id = first.get('pv_id')
                    try:
                        p.luz_price = float(first.get('price')) if first.get('price') is not None else None
                    except Exception:
                        p.luz_price = None
                p.luz_color = luces.get('color')
                p.posicion_luz = luces.get('posicion')
            # tipos corporeo as json
            try:
                import json as _json
                tipos = payload.get('tipos_corporeo')
                p.tipos_corporeo_json = _json.dumps(tipos, ensure_ascii=False) if tipos is not None else None
            except Exception:
                p.tipos_corporeo_json = None
    except Exception:
        pass

    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def get_corporeo_payload_by_sale(session: Session, sale_id: int) -> 'CorporeoPayload | None':
    """Devuelve el último `CorporeoPayload` asociado a una venta (sale_id) o None."""
    from .models import CorporeoPayload
    try:
        return session.query(CorporeoPayload).filter(CorporeoPayload.sale_id == int(sale_id)).order_by(CorporeoPayload.id.desc()).first()
    except Exception:
        return None


def update_corporeo_payload(session: Session, payload_id: int, *, payload: dict | None = None, **kwargs) -> bool:
    from .models import CorporeoPayload
    p = session.get(CorporeoPayload, int(payload_id))
    if not p:
        return False
    import json
    if payload is not None:
        p.payload_json = json.dumps(payload, ensure_ascii=False)
    for k, v in kwargs.items():
        if hasattr(p, k):
            try:
                setattr(p, k, v)
            except Exception:
                pass
    session.commit()
    return True

def delete_order_by_id(session: Session, order_id: int) -> bool:
    obj = session.get(Order, order_id)
    if not obj:
        return False
    session.delete(obj)
    session.commit()
    return True


# --- Daily Reports CRUD ---

from typing import Optional
from datetime import date as _date

def check_daily_report_status(session: Session, target_date: Optional[datetime | _date] = None) -> dict:
    """Verifica el estado del reporte diario para una fecha específica."""
    from datetime import date, datetime as dt
    
    # Normalizar a date (día)
    day = dt.now().date() if target_date is None else (target_date.date() if isinstance(target_date, dt) else target_date)
    
    # Buscar reporte existente para esa fecha
    existing_report = session.query(DailyReport).filter(
    DailyReport.report_date >= dt.combine(day, dt.min.time()),
    DailyReport.report_date < dt.combine(day, dt.max.time())
    ).first()
    
    # Contar ventas del día
    sales_count = session.query(Sale).filter(
    Sale.fecha >= dt.combine(day, dt.min.time()),
    Sale.fecha < dt.combine(day, dt.max.time())
    ).count()
    
    return {
    'date': day,
        'has_report': existing_report is not None,
        'report': existing_report,
        'sales_count': sales_count,
        'needs_report': sales_count > 0 and existing_report is None,
        'status': existing_report.report_status if existing_report else 'FALTANTE'
    }


def get_daily_sales_data(session: Session, target_date: Optional[datetime | _date] = None, user_filter: Optional[str] = None) -> dict:
    """Obtiene datos de ventas para un día específico."""
    from .models import Sale, SalePayment
    
    day = dt.now().date() if target_date is None else (target_date.date() if isinstance(target_date, dt) else target_date)
    
    # Obtener ventas del día con filtro opcional por usuario
    query = session.query(Sale).filter(
    Sale.fecha >= dt.combine(day, dt.min.time()),
    Sale.fecha < dt.combine(day, dt.max.time())
    )
    
    # Aplicar filtro por asesor/usuario si se especifica
    if user_filter:
        query = query.filter(Sale.asesor == user_filter)
    
    daily_sales = query.all()

    # Obtener pagos de cuentas por cobrar del día
    payments_query = session.query(SalePayment).filter(
        SalePayment.payment_date >= dt.combine(day, dt.min.time()),
        SalePayment.payment_date < dt.combine(day, dt.max.time())
    )
    daily_payments = payments_query.all()
    
    # Calcular totales de todos los campos
    total_sales = len(daily_sales) # Solo contamos ventas nuevas como "ventas"
    total_amount_usd = sum((sale.venta_usd or 0.0) for sale in daily_sales)
    total_amount_bs = sum((sale.monto_bs or 0.0) for sale in daily_sales)
    total_monto_usd_calculado = sum((sale.monto_usd_calculado or 0.0) for sale in daily_sales)
    total_abono_usd = sum((sale.abono_usd or 0.0) for sale in daily_sales)
    total_restante = sum((sale.restante or 0.0) for sale in daily_sales)
    total_iva = sum((sale.iva or 0.0) for sale in daily_sales)
    total_diseno_usd = sum((sale.diseno_usd or 0.0) for sale in daily_sales)
    total_ingresos_usd = sum((sale.ingresos_usd or 0.0) for sale in daily_sales)

    # Sumar pagos a los totales relevantes
    for payment in daily_payments:
        total_abono_usd += payment.amount_usd
        total_ingresos_usd += payment.amount_usd
        total_amount_bs += payment.amount_bs
        # No sumamos a total_amount_usd porque no es nueva venta
    
    # Agrupar por forma de pago con detalles completos
    payment_methods = {}
    asesores_summary = {}
    
    # Procesar ventas
    for sale in daily_sales:
        # Resumen por forma de pago
        method = sale.forma_pago or "Sin especificar"
        if method not in payment_methods:
            payment_methods[method] = {
                'count': 0, 
                'venta_usd': 0.0,
                'monto_bs': 0.0,
                'abono_usd': 0.0,
                'ingresos_usd': 0.0
            }
        payment_methods[method]['count'] += 1
        payment_methods[method]['venta_usd'] += (sale.venta_usd or 0.0)
        payment_methods[method]['monto_bs'] += (sale.monto_bs or 0.0)
        payment_methods[method]['abono_usd'] += (sale.abono_usd or 0.0)
        payment_methods[method]['ingresos_usd'] += (sale.ingresos_usd or 0.0)
        
        # Resumen por asesor
        asesor = sale.asesor or "Sin especificar"
        if asesor not in asesores_summary:
            asesores_summary[asesor] = {
                'count': 0,
                'venta_usd': 0.0,
                'monto_bs': 0.0,
                'abono_usd': 0.0,
                'ingresos_usd': 0.0
            }
        asesores_summary[asesor]['count'] += 1
        asesores_summary[asesor]['venta_usd'] += (sale.venta_usd or 0.0)
        asesores_summary[asesor]['monto_bs'] += (sale.monto_bs or 0.0)
        asesores_summary[asesor]['abono_usd'] += (sale.abono_usd or 0.0)
        asesores_summary[asesor]['ingresos_usd'] += (sale.ingresos_usd or 0.0)

    # Procesar pagos
    for payment in daily_payments:
        method = payment.payment_method or "Sin especificar"
        if method not in payment_methods:
            payment_methods[method] = {
                'count': 0, 'venta_usd': 0.0, 'monto_bs': 0.0, 
                'abono_usd': 0.0, 'ingresos_usd': 0.0
            }
        payment_methods[method]['count'] += 1
        payment_methods[method]['abono_usd'] += payment.amount_usd
        payment_methods[method]['ingresos_usd'] += payment.amount_usd
        payment_methods[method]['monto_bs'] += payment.amount_bs
        
        # Asesor de la venta original
        sale = payment.sale
        asesor = sale.asesor if sale else "Sin especificar"
        if asesor not in asesores_summary:
             asesores_summary[asesor] = {
                'count': 0, 'venta_usd': 0.0, 'monto_bs': 0.0,
                'abono_usd': 0.0, 'ingresos_usd': 0.0
            }
        asesores_summary[asesor]['abono_usd'] += payment.amount_usd
        asesores_summary[asesor]['ingresos_usd'] += payment.amount_usd
        asesores_summary[asesor]['monto_bs'] += payment.amount_bs
    
    # Serializar los datos de ventas para el reporte
    sales_data = []
    for sale in daily_sales:
        # Resolver nombre del cliente
        client_name = sale.cliente or ""
        if not client_name and sale.cliente_id:
            # Intentar buscar cliente por ID si no tiene nombre directo
            # Nota: Esto asume que Customer está importado o disponible en la sesión
            try:
                from .models import Customer
                cust = session.get(Customer, sale.cliente_id)
                if cust:
                    client_name = cust.name
            except Exception:
                pass

        sales_data.append({
            'id': sale.id,
            'numero_orden': sale.numero_orden,
            'fecha': sale.fecha.isoformat(),
            'articulo': sale.articulo,
            'asesor': sale.asesor,
            'cliente': client_name,
            'venta_usd': sale.venta_usd,
            'forma_pago': sale.forma_pago,
            'serial_billete': sale.serial_billete,
            'banco': sale.banco,
            'referencia': sale.referencia,
            'fecha_pago': sale.fecha_pago.isoformat() if sale.fecha_pago else None,
            'monto_bs': sale.monto_bs,
            'monto_usd_calculado': sale.monto_usd_calculado,
            'tasa_bcv': sale.tasa_bcv,
            'abono_usd': sale.abono_usd,
            'restante': sale.restante,
            'iva': sale.iva,
            'diseno_usd': sale.diseno_usd,
            'ingresos_usd': sale.ingresos_usd,
            'notes': sale.notes,
            'created_at': sale.created_at.isoformat()
        })

    # Agregar pagos a sales_data
    for payment in daily_payments:
        sale = payment.sale
        client_name = sale.cliente or ""
        if not client_name and sale and sale.cliente_id:
            try:
                from .models import Customer
                cust = session.get(Customer, sale.cliente_id)
                if cust:
                    client_name = cust.name
            except Exception:
                pass
        
        sales_data.append({
            'id': f"PAY-{payment.id}",
            'numero_orden': sale.numero_orden if sale else "N/A",
            'fecha': payment.payment_date.isoformat(),
            'articulo': "PAGO RESTANTE",
            'asesor': sale.asesor if sale else "N/A",
            'cliente': client_name,
            'venta_usd': 0.0,
            'forma_pago': payment.payment_method,
            'serial_billete': None,
            'banco': payment.bank,
            'referencia': payment.reference,
            'fecha_pago': payment.payment_date.isoformat(),
            'monto_bs': payment.amount_bs,
            'monto_usd_calculado': 0.0,
            'tasa_bcv': payment.exchange_rate,
            'abono_usd': payment.amount_usd,
            'restante': sale.restante if sale else 0.0,
            'iva': 0.0,
            'diseno_usd': 0.0,
            'ingresos_usd': payment.amount_usd,
            'notes': f"Pago de deuda",
            'created_at': payment.payment_date.isoformat()
        })
    
    return {
    'date': day,
        'sales': daily_sales,
        'sales_data': sales_data,  # Datos serializados para el reporte
        'total_sales': total_sales,
        'total_amount_usd': total_amount_usd,
        'total_amount_bs': total_amount_bs,
        'total_monto_usd_calculado': total_monto_usd_calculado,
        'total_abono_usd': total_abono_usd,
        'total_restante': total_restante,
        'total_iva': total_iva,
        'total_diseno_usd': total_diseno_usd,
        'total_ingresos_usd': total_ingresos_usd,
        'payment_methods': payment_methods,
        'asesores_summary': asesores_summary
    }


def create_daily_report(session: Session, user_id: int, target_date: Optional[datetime | _date] = None, notes: Optional[str] = None, user_filter: Optional[str] = None) -> DailyReport:
    """Crea un reporte diario de ventas."""
    from datetime import date, datetime as dt
    import json
    
    day = dt.now().date() if target_date is None else (target_date.date() if isinstance(target_date, dt) else target_date)
    
    # Verificar que no exista ya un reporte para esa fecha
    existing = session.query(DailyReport).filter(
    DailyReport.report_date >= dt.combine(day, dt.min.time()),
    DailyReport.report_date < dt.combine(day, dt.max.time())
    ).first()
    
    if existing:
        raise ValueError(f"Ya existe un reporte para la fecha {target_date}")
    
    # Obtener datos del día con filtro opcional por usuario
    data = get_daily_sales_data(session, day, user_filter)
    
    # Crear el reporte con todos los datos completos
    report = DailyReport(
    report_date=dt.combine(day, dt.min.time()),
        generated_by=user_id,
        total_sales=data['total_sales'],
        total_amount_usd=data['total_amount_usd'],
        total_amount_bs=data['total_amount_bs'],
        total_ingresos_usd=data['total_ingresos_usd'],
        report_status='GENERADO',
        report_data_json=json.dumps({
            # Datos detallados de todas las ventas del día
            'sales_data': data['sales_data'],
            
            # Totales completos
            'totals': {
                'total_sales': data['total_sales'],
                'total_amount_usd': data['total_amount_usd'],
                'total_amount_bs': data['total_amount_bs'],
                'total_monto_usd_calculado': data['total_monto_usd_calculado'],
                'total_abono_usd': data['total_abono_usd'],
                'total_restante': data['total_restante'],
                'total_iva': data['total_iva'],
                'total_diseno_usd': data['total_diseno_usd'],
                'total_ingresos_usd': data['total_ingresos_usd']
            },
            
            # Resúmenes agrupados
            'payment_methods': data['payment_methods'],
            'asesores_summary': data['asesores_summary'],
            
            # Metadatos del reporte
            'generation_timestamp': dt.now().isoformat(),
            'report_date': day.isoformat()
        }, ensure_ascii=False),
        notes=notes
    )
    
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


def get_pending_reports(session: Session, days_back: int = 7) -> list[dict]:
    """Obtiene las fechas que necesitan reporte en los últimos N días."""
    from datetime import date, datetime as dt, timedelta
    
    pending_dates = []
    current_date = dt.now().date()
    
    for i in range(days_back):
        check_date = current_date - timedelta(days=i)
        status = check_daily_report_status(session, check_date)
        if status['needs_report']:
            pending_dates.append(status)
    
    return pending_dates


def list_daily_reports(session: Session, limit: int = 30) -> list[DailyReport]:
    """Lista los reportes diarios más recientes."""
    return session.query(DailyReport).order_by(
        DailyReport.report_date.desc()
    ).limit(limit).all()


# --- Funciones de Configuración del Sistema ---

def get_system_config(session: Session, key: str, default_value: Optional[str] = None) -> Optional[str]:
    """Obtener un valor de configuración del sistema."""
    config = session.query(SystemConfig).filter(SystemConfig.config_key == key).first()
    return config.config_value if config else default_value


def set_system_config(session: Session, key: str, value: str, description: Optional[str] = None) -> SystemConfig:
    """Establecer un valor de configuración del sistema."""
    config = session.query(SystemConfig).filter(SystemConfig.config_key == key).first()
    if config:
        config.config_value = value
        if description:
            config.description = description
    else:
        config = SystemConfig(
            config_key=key,
            config_value=value,
            description=description
        )
        session.add(config)
    session.commit()
    session.refresh(config)
    return config


def get_monthly_sales_goal(session: Session) -> float:
    """Obtener la meta mensual de ventas."""
    goal_str = get_system_config(session, "monthly_sales_goal", "12000.0")
    try:
        return float(goal_str) if goal_str is not None else 12000.0
    except (ValueError, TypeError):
        return 12000.0


def set_monthly_sales_goal(session: Session, goal: float) -> None:
    """Establecer la meta mensual de ventas."""
    set_system_config(
        session,
        "monthly_sales_goal",
        str(goal),
        "Meta mensual de ventas en USD"
    )

def set_user_monthly_goal(session: Session, username: str, goal: float) -> None:
    """Establecer la meta mensual para un usuario específico."""
    from .models import User
    user = session.query(User).filter(User.username == username).first()
    if user:
        user.monthly_goal = goal
        session.commit()


# --- Funciones de Estadísticas de Ventas ---

def get_sales_by_user(session: Session, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, filter_user: Optional[str] = None) -> list[dict]:
    """Obtener ventas agrupadas por usuario/asesor (incluyendo usuarios sin ventas)."""
    from .models import Sale, User
    from datetime import datetime, date
    import calendar
    from sqlalchemy import func
    
    # Si no se especifica rango, usar mes actual
    if not start_date or not end_date:
        today = date.today()
        start_date = datetime(today.year, today.month, 1)
        # Último día del mes
        last_day = calendar.monthrange(today.year, today.month)[1]
        end_date = datetime(today.year, today.month, last_day, 23, 59, 59)
    
    # 1. Subquery: Ventas agrupadas por asesor en el rango
    sales_sub = session.query(
        Sale.asesor,
        func.sum(Sale.venta_usd).label('total_sales'),
        func.count(Sale.id).label('sales_count')
    ).filter(
        Sale.fecha >= start_date,
        Sale.fecha <= end_date
    ).group_by(Sale.asesor).subquery()

    # 2. Query principal: Usuarios activos + sus ventas (Left Join)
    query = session.query(
        User.username,
        User.monthly_goal,
        func.coalesce(sales_sub.c.total_sales, 0.0).label('total_sales'),
        func.coalesce(sales_sub.c.sales_count, 0).label('sales_count')
    ).outerjoin(
        sales_sub, User.username == sales_sub.c.asesor
    ).filter(
        User.is_active == True
    )

    if filter_user:
        query = query.filter(User.username == filter_user)

    results = query.all()
    
    return [
        {
            'asesor': row.username,
            'total_sales': float(row.total_sales),
            'sales_count': int(row.sales_count),
            'monthly_goal': float(row.monthly_goal or 0.0)
        }
        for row in results
    ]


def get_daily_sales_chart_data(session: Session, days_back: int = 7, filter_user: Optional[str] = None) -> dict:
    """Obtener datos de ventas por día para gráficos."""
    from .models import Sale
    from datetime import datetime, date, timedelta
    
    today = date.today()
    start_date = datetime.combine(today - timedelta(days=days_back - 1), datetime.min.time())
    end_date = datetime.combine(today, datetime.max.time())
    
    # Obtener ventas en el rango
    query = session.query(Sale).filter(
        Sale.fecha >= start_date,
        Sale.fecha <= end_date
    )
    
    if filter_user:
        query = query.filter(Sale.asesor == filter_user)
        
    sales = query.all()
    
    # Inicializar diccionario con todos los días en el rango
    daily_data = {}
    for i in range(days_back):
        day = today - timedelta(days=days_back - 1 - i)
        day_key = day.strftime("%Y-%m-%d")
        daily_data[day_key] = {
            'date': day,
            'total_sales': 0.0,
            'sales_count': 0
        }

    # Agrupar ventas
    for sale in sales:
        day_key = sale.fecha.strftime("%Y-%m-%d")
        if day_key in daily_data:
            daily_data[day_key]['total_sales'] += (sale.venta_usd or 0.0)
            daily_data[day_key]['sales_count'] += 1
            
    # Convertir a lista ordenada
    result_list = sorted(daily_data.values(), key=lambda x: x['date'])
    
    return {
        'daily_data': result_list
    }


def get_weekly_sales_data(session: Session, weeks_back: int = 4, filter_user: Optional[str] = None) -> dict:
    """Obtener datos de ventas por semana para gráficos."""
    from .models import Sale
    from datetime import datetime, date, timedelta
    import calendar
    
    today = date.today()
    start_date = datetime.combine(today - timedelta(weeks=weeks_back), datetime.min.time())
    end_date = datetime.combine(today, datetime.max.time())
    
    # Obtener ventas en el rango
    query = session.query(Sale).filter(
        Sale.fecha >= start_date,
        Sale.fecha <= end_date
    )
    
    if filter_user:
        query = query.filter(Sale.asesor == filter_user)
        
    sales = query.all()
    
    # Agrupar por semana
    weekly_data = {}
    for sale in sales:
        week_start = sale.fecha.date() - timedelta(days=sale.fecha.weekday())
        week_key = week_start.strftime("%Y-%m-%d")
        
        if week_key not in weekly_data:
            weekly_data[week_key] = {
                'week_start': week_start,
                'total_sales': 0.0,
                'sales_count': 0
            }
        
        weekly_data[week_key]['total_sales'] += sale.venta_usd
        weekly_data[week_key]['sales_count'] += 1
    
    return {
        'weekly_data': list(weekly_data.values()),
        'start_date': start_date.date(),
        'end_date': end_date.date()
    }


def get_dashboard_kpis(session: Session, filter_user: Optional[str] = None) -> dict:
    """Obtener KPIs para el dashboard principal."""
    from .models import Sale, Customer
    from datetime import datetime, date
    import calendar
    
    today = date.today()
    month_start = datetime(today.year, today.month, 1)
    
    # Total clientes
    total_customers = session.query(Customer).count()
    
    # Ventas del mes
    from sqlalchemy import func
    q_monthly = session.query(func.sum(Sale.venta_usd)).filter(
        Sale.fecha >= month_start
    )
    
    # Total pedidos del mes
    q_orders = session.query(Sale).filter(
        Sale.fecha >= month_start
    )
    
    # Ventas de hoy
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    q_today = session.query(func.sum(Sale.venta_usd)).filter(
        Sale.fecha >= today_start,
        Sale.fecha <= today_end
    )

    if filter_user:
        q_monthly = q_monthly.filter(Sale.asesor == filter_user)
        q_orders = q_orders.filter(Sale.asesor == filter_user)
        q_today = q_today.filter(Sale.asesor == filter_user)
    
    monthly_sales = q_monthly.scalar() or 0
    monthly_orders = q_orders.count()
    today_sales = q_today.scalar() or 0
    
    return {
        'total_customers': total_customers,
        'monthly_sales': float(monthly_sales),
        'monthly_orders': monthly_orders,
        'today_sales': float(today_sales)
    }


# --- Funciones avanzadas de gestión de usuarios ---

def update_user(session: Session, *, user_id: int, username: str | None = None, full_name: str | None = None, 
                password: str | None = None, is_active: bool | None = None) -> User | None:
    """Actualizar información de un usuario."""
    user = session.get(User, user_id)
    if not user:
        return None
    
    if username is not None:
        user.username = username
    if full_name is not None:
        user.full_name = full_name
    if password is not None:
        user.password_hash = _hash_password(password)
    if is_active is not None:
        user.is_active = is_active
        
    session.commit()
    session.refresh(user)
    return user


def get_user_roles(session: Session, user_id: int) -> list[Role]:
    """Obtener roles asignados a un usuario."""
    return (
        session.query(Role)
        .join(UserRole)
        .filter(UserRole.user_id == user_id)
        .all()
    )


def get_role_permissions(session: Session, role_id: int) -> list[Permission]:
    """Obtener permisos asignados a un rol."""
    return (
        session.query(Permission)
        .join(RolePermission)
        .filter(RolePermission.role_id == role_id)
        .all()
    )


def get_user_permissions(session: Session, user_id: int) -> list[str]:
    """Obtener todos los códigos de permisos asignados a un usuario a través de sus roles."""
    permissions = (
        session.query(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id)
        .distinct()
        .all()
    )
    return [p[0] for p in permissions]


def assign_user_roles(session: Session, user_id: int, role_ids: list[int]) -> None:
    """Asignar roles a un usuario (reemplaza roles existentes)."""
    # Eliminar roles actuales
    session.query(UserRole).filter(UserRole.user_id == user_id).delete()
    
    # Agregar nuevos roles
    for role_id in role_ids:
        session.add(UserRole(user_id=user_id, role_id=role_id))
    
    session.commit()


def assign_role_permissions(session: Session, role_id: int, permission_ids: list[int]) -> None:
    """Asignar permisos a un rol (reemplaza permisos existentes)."""
    # Eliminar permisos actuales
    session.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
    
    # Agregar nuevos permisos
    for permission_id in permission_ids:
        session.add(RolePermission(role_id=role_id, permission_id=permission_id))
    
    session.commit()


def list_roles(session: Session) -> list[Role]:
    """Listar todos los roles."""
    return session.query(Role).order_by(Role.name).all()


def list_permissions(session: Session) -> list[Permission]:
    """Listar todos los permisos."""
    return session.query(Permission).order_by(Permission.code).all()


def get_users_with_roles(session: Session, active_only: bool = True) -> list[dict]:
    """Obtener usuarios con sus roles como texto."""
    users_data = []
    # Mostrar usuarios ordenados por nombre de usuario
    query = session.query(User)
    if active_only:
        query = query.filter(User.is_active == True)
    users = query.order_by(User.username).all()
    
    for user in users:
        roles = get_user_roles(session, user.id)
        role_names = [role.name for role in roles]
        
        users_data.append({
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name or '',
            'roles': ', '.join(role_names) if role_names else 'Sin rol',
            'is_active': user.is_active,
            'status_text': 'Activo' if user.is_active else 'Inactivo'
        })
    
    return users_data


def get_roles_with_stats(session: Session) -> list[dict]:
    """Obtener roles con estadísticas."""
    roles_data = []
    roles = session.query(Role).all()
    
    for role in roles:
        # Contar usuarios con este rol
        user_count = (
            session.query(UserRole)
            .filter(UserRole.role_id == role.id)
            .count()
        )
        
        # Contar permisos de este rol
        perm_count = (
            session.query(RolePermission)
            .filter(RolePermission.role_id == role.id)
            .count()
        )
        
        roles_data.append({
            'id': role.id,
            'name': role.name,
            'description': role.description or '',
            'user_count': user_count,
            'permission_count': perm_count
        })
    
    return roles_data


def get_permissions_with_stats(session: Session) -> list[dict]:
    """Obtener permisos con estadísticas."""
    permissions_data = []
    permissions = session.query(Permission).all()
    
    for perm in permissions:
        # Contar roles que tienen este permiso
        role_count = (
            session.query(RolePermission)
            .filter(RolePermission.permission_id == perm.id)
            .count()
        )
        
        # Obtener nombres de roles
        roles = (
            session.query(Role)
            .join(RolePermission)
            .filter(RolePermission.permission_id == perm.id)
            .all()
        )
        role_names = [role.name for role in roles]
        
        permissions_data.append({
            'id': perm.id,
            'code': perm.code,
            'description': perm.description or '',
            'role_count': role_count,
            'roles': ', '.join(role_names) if role_names else 'Ninguno'
        })
    
    return permissions_data


# --- Módulo de Parámetros y Materiales ---

def list_configurable_products(session: Session) -> list:
    """Listar todos los productos configurables activos."""
    from .models import ConfigurableProduct, User
    
    products = (
        session.query(ConfigurableProduct, User.username)
        .join(User, ConfigurableProduct.created_by == User.id)
        .filter(ConfigurableProduct.is_active == True)
        .order_by(ConfigurableProduct.name)
        .all()
    )
    
    result = []
    for product, creator_username in products:
        result.append({
            'id': product.id,
            'name': product.name,
            'description': product.description or '',
            'created_by': creator_username,
            'created_at': product.created_at,
            'updated_at': product.updated_at
        })
    
    return result


def create_configurable_product(session: Session, name: str, description: str | None = None, created_by: int = 1) -> int:
    """Crear un nuevo producto configurable."""
    from .models import ConfigurableProduct
    
    # Verificar si ya existe un producto con el mismo nombre
    existing = session.query(ConfigurableProduct).filter(ConfigurableProduct.name == name.strip()).first()
    if existing:
        raise ValueError(f"Ya existe un producto con el nombre '{name.strip()}'")
    
    product = ConfigurableProduct(
        name=name.strip(),
        description=description.strip() if description else None,
        created_by=created_by
    )
    
    session.add(product)
    session.flush()  # Para obtener el ID
    return product.id


def update_configurable_product(session: Session, product_id: int, name: str, description: str | None = None):
    """Actualizar un producto configurable."""
    from .models import ConfigurableProduct
    
    product = session.query(ConfigurableProduct).filter(ConfigurableProduct.id == product_id).first()
    if not product:
        raise ValueError(f"Producto con ID {product_id} no encontrado")
    
    # Verificar si el nombre cambió y si ya existe otro producto con ese nombre
    if product.name != name.strip():
        existing = session.query(ConfigurableProduct).filter(
            ConfigurableProduct.name == name.strip(),
            ConfigurableProduct.id != product_id
        ).first()
        if existing:
            raise ValueError(f"Ya existe un producto con el nombre '{name.strip()}'")
    
    product.name = name.strip()
    product.description = description.strip() if description else None


def delete_configurable_product(session: Session, product_id: int):
    """Eliminar (desactivar) un producto configurable."""
    from .models import ConfigurableProduct
    
    product = session.query(ConfigurableProduct).filter(ConfigurableProduct.id == product_id).first()
    if not product:
        raise ValueError(f"Producto con ID {product_id} no encontrado")
    
    product.is_active = False


def get_product_parameter_tables(session: Session, product_id: int, include_inactive: bool = False) -> list:
    """Obtener las tablas de parámetros de un producto."""
    from .models import ProductParameterTable
    from .models import ProductParameterValue
    
    # Asegurar que product_id es un entero válido
    if isinstance(product_id, dict) and 'id' in product_id:
        product_id = product_id['id']
    
    q = (
        session.query(ProductParameterTable)
        .filter(ProductParameterTable.product_id == product_id)
    )
    if not include_inactive:
        q = q.filter(ProductParameterTable.is_active == True)
    tables = q.order_by(ProductParameterTable.display_name).all()
    
    result = []
    for table in tables:
        import json
        schema = json.loads(table.schema_json) if table.schema_json else {}
        # Contar registros activos en la tabla
        record_count = (
            session.query(ProductParameterValue)
            .filter(ProductParameterValue.parameter_table_id == table.id)
            .filter(ProductParameterValue.is_active == True)
            .count()
        )
        
        # Información de la tabla padre si existe
        parent_table_name = None
        if table.parent_table_id:
            parent_table = session.get(ProductParameterTable, table.parent_table_id)
            if parent_table:
                parent_table_name = parent_table.display_name
        
        result.append({
            'id': table.id,
            'table_name': table.table_name,
            'display_name': table.display_name,
            'description': table.description or '',
            'schema': schema,
            'has_auto_id': table.has_auto_id,
            'parent_table_id': table.parent_table_id,
            'parent_table_name': parent_table_name,
            'relationship_column': table.relationship_column,
            'created_at': table.created_at,
            'record_count': int(record_count),
            'is_active': bool(table.is_active),
        })
    
    return result


def delete_product_parameter_table(session: Session, table_id: int, *, cascade_values: bool = True, force: bool = False) -> dict:
    """Eliminar (desactivar) una tabla de parámetros.

    Reglas:
    - Si la tabla tiene tablas hijas activas y no se usa force, se lanza ValueError.
    - Se desactivan los valores (filas) asociados si cascade_values=True.
    - La tabla se marca como inactiva (soft-delete).

    Retorna un dict con métricas del borrado: {'values_deactivated': n, 'children_count': m}
    """
    from .models import ProductParameterTable, ProductParameterValue

    table = session.get(ProductParameterTable, table_id)
    if not table:
        raise ValueError(f"Tabla con ID {table_id} no encontrada")

    # Verificar si ya está inactiva
    if table.is_active is False:
        return {'values_deactivated': 0, 'children_count': 0}

    # Verificar tablas hijas activas y, si force, eliminarlas recursivamente primero
    children = (
        session.query(ProductParameterTable)
        .filter(ProductParameterTable.parent_table_id == table_id)
        .filter(ProductParameterTable.is_active == True)
        .all()
    )
    children_count = len(children)
    if children_count > 0 and not force:
        raise ValueError(
            f"No se puede eliminar la tabla '{table.display_name}' porque tiene {children_count} tabla(s) hija(s) activas. "
            "Elimine o desasigne primero las relaciones de las tablas hijas."
        )
    # Cascada forzada: desactivar primero las hijas (profundidad primero)
    total_values_deactivated = 0
    total_children_processed = 0
    if force and children_count:
        for child in children:
            stats_child = delete_product_parameter_table(session, child.id, cascade_values=cascade_values, force=True)
            total_values_deactivated += stats_child.get('values_deactivated', 0)
            total_children_processed += 1 + stats_child.get('children_count', 0)

    # Desactivar filas/valores asociados
    values_deactivated = 0
    if cascade_values:
        values_deactivated = (
            session.query(ProductParameterValue)
            .filter(ProductParameterValue.parameter_table_id == table_id)
            .filter(ProductParameterValue.is_active == True)
            .update({ProductParameterValue.is_active: False}, synchronize_session=False)
        )

    # Desactivar la tabla
    table.is_active = False
    session.flush()

    return {
        'values_deactivated': int((values_deactivated or 0) + total_values_deactivated),
        'children_count': int(children_count + total_children_processed)
    }


def get_child_parameter_tables(session: Session, parent_table_id: int, *, active_only: bool = True) -> list:
    """Devuelve las tablas hijas directas de una tabla de parámetros."""
    from .models import ProductParameterTable
    q = session.query(ProductParameterTable).filter(ProductParameterTable.parent_table_id == parent_table_id)
    if active_only:
        q = q.filter(ProductParameterTable.is_active == True)
    rows = q.order_by(ProductParameterTable.display_name).all()
    return [
        {
            'id': t.id,
            'display_name': t.display_name,
            'is_active': t.is_active,
            'parent_table_id': t.parent_table_id,
        }
        for t in rows
    ]


def restore_product_parameter_table(session: Session, table_id: int, *, with_children: bool = False) -> dict:
    """Restaura (reactiva) una tabla de parámetros. Si with_children=True, reactiva recursivamente las hijas.

    Restricción: no permite restaurar una hija si su padre está inactivo (a menos que with_children=True y se restaure en cadena).
    """
    from .models import ProductParameterTable
    table = session.get(ProductParameterTable, table_id)
    if not table:
        raise ValueError(f"Tabla con ID {table_id} no encontrada")

    # Si tiene padre y el padre está inactivo, impedir restaurar solo hija
    if table.parent_table_id:
        parent = session.get(ProductParameterTable, table.parent_table_id)
        if parent and not parent.is_active and not with_children:
            raise ValueError("No se puede restaurar una tabla hija mientras su tabla padre está inactiva. Restaure el padre primero o use 'con hijos'.")

    restored_children = 0
    # Restaurar padre si with_children y padre inactivo
    if table.parent_table_id and with_children:
        parent = session.get(ProductParameterTable, table.parent_table_id)
        if parent and not parent.is_active:
            restore_product_parameter_table(session, parent.id, with_children=True)

    # Restaurar hijos si se indica
    if with_children:
        children = get_child_parameter_tables(session, table_id, active_only=False)
        for child in children:
            if not child['is_active']:
                restore_product_parameter_table(session, child['id'], with_children=True)
                restored_children += 1

    table.is_active = True
    session.flush()
    return {'restored_children': restored_children}


def check_parameter_table_references(session: Session, table_id: int) -> dict:
    """Verifica referencias potenciales a la tabla en órdenes/ventas.

    Implementación heurística: busca el ID o el nombre de la tabla dentro de Order.details_json.
    """
    from .models import ProductParameterTable, Order, Sale
    t = session.get(ProductParameterTable, table_id)
    if not t:
        return {'orders': 0, 'sales': 0}
    # Heurística: patrones posibles dentro del JSON
    like_id = f'%"parameter_table_id"%{table_id}%'
    like_table = f'%"{t.table_name}"%'
    like_display = f'%"{t.display_name}"%'
    orders_count = (
        session.query(Order)
        .filter((Order.details_json.like(like_id)) | (Order.details_json.like(like_table)) | (Order.details_json.like(like_display)))
        .count()
    )
    # No tenemos un vínculo directo con ventas; retornar 0 por compatibilidad
    return {'orders': int(orders_count), 'sales': 0}


def create_product_parameter_table(session: Session, product_id: int, display_name: str, 
                                 description: str | None = None, columns: list | None = None,
                                 has_auto_id: bool = True, parent_table_id: int | None = None,
                                 relationship_column: str | None = None) -> int:
    """Crear una nueva tabla de parámetros para un producto."""
    from .models import ProductParameterTable
    import json
    import re
    
    # Generar nombre de tabla único
    base_name = re.sub(r'[^a-zA-Z0-9_]', '_', display_name.lower())
    table_name = f"params_{product_id}_{base_name}_{int(__import__('time').time())}"
    
    # Schema por defecto si no se proporciona
    if not columns:
        columns = [
            {'name': 'nombre', 'type': 'TEXT', 'required': True, 'description': 'Nombre del parámetro'},
            {'name': 'valor', 'type': 'TEXT', 'required': True, 'description': 'Valor del parámetro'}
        ]

    # Normalizar bandera de auto ID: si el esquema ya trae una PK/auto id, no volver a añadir
    def _has_builtin_id(cols: list) -> bool:
        for c in cols:
            name = str(c.get('name', '')).strip().lower()
            # Considerar 'id' presente aunque no esté marcado como PK/Auto para evitar duplicados
            if name == 'id':
                return True
            if c.get('primary_key') and name:  # Cualquier PK existente
                return True
        return False

    if has_auto_id and not _has_builtin_id(columns):
        id_column = {
            'name': 'id',
            'type': 'INTEGER',
            'required': True,
            'primary_key': True,
            'auto_increment': True,
            'description': 'Identificador único automático'
        }
        columns = [id_column] + columns
    
    # Si hay una relación con otra tabla, añadir columna de FK
    if parent_table_id and relationship_column:
        # Verificar que la tabla padre existe
        parent_table = session.get(ProductParameterTable, parent_table_id)
        if not parent_table:
            raise ValueError(f"Tabla padre con ID {parent_table_id} no encontrada")
        
        fk_column = {
            'name': relationship_column,
            'type': 'INTEGER',
            'required': False,
            'foreign_key': parent_table_id,
            'description': f'Relación con tabla {parent_table.display_name}'
        }
        columns.append(fk_column)
    
    parameter_table = ProductParameterTable(
        product_id=product_id,
        table_name=table_name,
        display_name=display_name.strip(),
        description=description.strip() if description else None,
        schema_json=json.dumps(columns),
        has_auto_id=has_auto_id,
        parent_table_id=parent_table_id,
        relationship_column=relationship_column
    )
    
    session.add(parameter_table)
    session.flush()
    return parameter_table.id


def update_product_parameter_table(session: Session, table_id: int, display_name: str, 
                                 description: str | None = None, columns: list | None = None,
                                 has_auto_id: bool = True, parent_table_id: int | None = None,
                                 relationship_column: str | None = None) -> bool:
    """Actualizar una tabla de parámetros existente."""
    from .models import ProductParameterTable
    import json
    
    # Obtener la tabla existente
    parameter_table = session.get(ProductParameterTable, table_id)
    if not parameter_table:
        raise ValueError(f"Tabla con ID {table_id} no encontrada")
    
    # Schema por defecto si no se proporciona
    if not columns:
        columns = [
            {'name': 'nombre', 'type': 'TEXT', 'required': True, 'description': 'Nombre del parámetro'},
            {'name': 'valor', 'type': 'TEXT', 'required': True, 'description': 'Valor del parámetro'}
        ]

    # Normalizar bandera de auto ID: si el esquema ya trae una PK/auto id, no volver a añadir
    def _has_builtin_id(cols: list) -> bool:
        for c in cols:
            name = str(c.get('name', '')).strip().lower()
            if name == 'id':
                return True
            if c.get('primary_key') and name:
                return True
        return False

    if has_auto_id and not _has_builtin_id(columns):
        id_column = {
            'name': 'id',
            'type': 'INTEGER',
            'required': True,
            'primary_key': True,
            'auto_increment': True,
            'description': 'Identificador único automático'
        }
        columns = [id_column] + columns
    
    # Si hay una relación con otra tabla, añadir columna de FK
    if parent_table_id and relationship_column:
        # Verificar que la tabla padre existe
        parent_table = session.get(ProductParameterTable, parent_table_id)
        if not parent_table:
            raise ValueError(f"Tabla padre con ID {parent_table_id} no encontrada")
        
        fk_column = {
            'name': relationship_column,
            'type': 'INTEGER',
            'required': False,
            'foreign_key': parent_table_id,
            'description': f'Relación con tabla {parent_table.display_name}'
        }
        columns.append(fk_column)
    
    # Actualizar los campos de la tabla
    parameter_table.display_name = display_name.strip()
    parameter_table.description = description.strip() if description else None
    parameter_table.schema_json = json.dumps(columns)
    parameter_table.has_auto_id = has_auto_id
    parameter_table.parent_table_id = parent_table_id
    parameter_table.relationship_column = relationship_column
    
    session.flush()
    return True


def get_available_parent_tables(session: Session, product_id: int, exclude_table_id: int | None = None) -> list:
    """Obtener tablas disponibles para usar como tablas padre en relaciones."""
    from .models import ProductParameterTable
    
    query = (
        session.query(ProductParameterTable)
        .filter(ProductParameterTable.product_id == product_id)
        .filter(ProductParameterTable.is_active == True)
        .filter(ProductParameterTable.has_auto_id == True)  # Solo tablas con ID automático pueden ser padres
    )
    
    if exclude_table_id:
        query = query.filter(ProductParameterTable.id != exclude_table_id)
    
    tables = query.order_by(ProductParameterTable.display_name).all()
    
    return [
        {
            'id': table.id,
            'display_name': table.display_name,
            'table_name': table.table_name,
            'description': table.description or ''
        }
        for table in tables
    ]


def get_parameter_table_data(session: Session, table_id: int) -> list:
    """Obtener los datos de una tabla de parámetros."""
    from .models import ProductParameterValue
    import json
    
    values = (
        session.query(ProductParameterValue)
        .filter(ProductParameterValue.parameter_table_id == table_id)
        .filter(ProductParameterValue.is_active == True)
        .order_by(ProductParameterValue.id)
        .all()
    )
    
    result = []
    for value in values:
        row_data = json.loads(value.row_data_json) if value.row_data_json else {}
        result.append({
            'id': value.id,
            'data': row_data,
            'created_at': value.created_at,
            'updated_at': value.updated_at
        })
    
    return result


def get_parent_table_options(session: Session, parent_table_id: int) -> list:
    """Obtener opciones de una tabla padre para usar en ComboBox."""
    from .models import ProductParameterTable
    import json
    
    # Verificar que la tabla padre existe
    parent_table = session.get(ProductParameterTable, parent_table_id)
    if not parent_table:
        return []
    
    # Obtener el esquema para determinar qué columnas mostrar
    schema = json.loads(parent_table.schema_json) if parent_table.schema_json else []
    
    # Encontrar la primera columna de texto para mostrar (excluyendo ID)
    display_column = None
    for col in schema:
        if col.get('name') != 'id' and col.get('type') in ['TEXT', 'VARCHAR']:
            display_column = col.get('name')
            break
    
    # Si no hay columna de texto, usar la primera columna no-ID
    if not display_column:
        for col in schema:
            if col.get('name') != 'id':
                display_column = col.get('name')
                break
    
    # Obtener los datos
    values = get_parameter_table_data(session, parent_table_id)
    
    options = []
    for value in values:
        row_data = value.get('data', {})
        # El ID de la fila viene del registro, no dentro de data
        record_id = value.get('id')
        
        # Determinar el texto a mostrar
        if display_column and display_column in row_data:
            display_text = str(row_data[display_column])
        else:
            # Fallback: mostrar el primer valor no-ID
            non_id_values = {k: v for k, v in row_data.items() if k != 'id'}
            if non_id_values:
                display_text = str(next(iter(non_id_values.values())))
            else:
                display_text = f"Registro {record_id}"
        
        if record_id is not None:
            options.append({
                'id': record_id,
                'text': display_text,
                'full_data': row_data
            })
    
    return options


def validate_foreign_key_value(session: Session, parent_table_id: int, fk_value: int) -> bool:
    """Validar que el valor de clave foránea existe en la tabla padre."""
    if fk_value is None:
        return True  # NULL es válido para FK opcionales
    
    try:
        parent_options = get_parent_table_options(session, parent_table_id)
        valid_ids = [option['id'] for option in parent_options]
        return fk_value in valid_ids
    except Exception:
        return False


def get_related_data(session: Session, child_table_id: int, parent_table_id: int, relationship_column: str) -> list:
    """Obtener datos relacionados combinando tabla padre e hija (simulando JOIN)."""
    import json
    
    # Obtener datos de ambas tablas
    parent_data = get_parameter_table_data(session, parent_table_id)
    child_data = get_parameter_table_data(session, child_table_id)
    
    # Crear índice de datos padre por ID
    parent_index = {}
    for parent_row in parent_data:
        parent_row_data = parent_row.get('data', {})
        parent_id = parent_row_data.get('id')
        if parent_id is not None:
            parent_index[parent_id] = parent_row_data
    
    # Combinar datos
    combined_results = []
    for child_row in child_data:
        child_row_data = child_row.get('data', {})
        parent_id = child_row_data.get(relationship_column)
        
        combined_row = {
            'child_id': child_row_data.get('id'),
            'child_data': child_row_data,
            'parent_data': parent_index.get(parent_id, {}) if parent_id else {},
            'relationship_value': parent_id
        }
        
        combined_results.append(combined_row)
    
    return combined_results


def get_filtered_data_by_parent(session: Session, child_table_id: int, parent_table_id: int, 
                               relationship_column: str, parent_filter_id: int) -> list:
    """Obtener solo los datos hijos que pertenecen a un padre específico."""
    child_data = get_parameter_table_data(session, child_table_id)
    
    filtered_results = []
    for child_row in child_data:
        child_row_data = child_row.get('data', {})
        if child_row_data.get(relationship_column) == parent_filter_id:
            filtered_results.append(child_row)
    
    return filtered_results


def add_parameter_table_row(session: Session, table_id: int, row_data: dict) -> int:
    """Agregar una fila de datos a una tabla de parámetros."""
    from .models import ProductParameterValue
    import json
    
    parameter_value = ProductParameterValue(
        parameter_table_id=table_id,
        row_data_json=json.dumps(row_data)
    )
    
    session.add(parameter_value)
    session.flush()
    return parameter_value.id


def update_parameter_table_row(session: Session, row_id: int, row_data: dict):
    """Actualizar una fila de datos en una tabla de parámetros."""
    from .models import ProductParameterValue
    import json
    
    value = session.query(ProductParameterValue).filter(ProductParameterValue.id == row_id).first()
    if not value:
        raise ValueError(f"Fila con ID {row_id} no encontrada")
    
    value.row_data_json = json.dumps(row_data)


def delete_parameter_table_row(session: Session, row_id: int):
    """Eliminar (desactivar) una fila de datos de una tabla de parámetros."""
    from .models import ProductParameterValue
    
    value = session.query(ProductParameterValue).filter(ProductParameterValue.id == row_id).first()
    if not value:
        raise ValueError(f"Fila con ID {row_id} no encontrada")
    
    value.is_active = False

# --- Workers Management ---

def list_workers(session: Session, active_only: bool = True, search_query: str | None = None) -> list[Worker]:
    query = session.query(Worker)
    if active_only:
        query = query.filter(Worker.is_active == True)
    
    if search_query:
        search = f"%{search_query}%"
        query = query.filter(
            (Worker.full_name.ilike(search)) |
            (Worker.cedula.ilike(search)) |
            (Worker.job_title.ilike(search))
        )
        
    return query.order_by(Worker.full_name).all()

def get_worker(session: Session, worker_id: int) -> Worker | None:
    return session.get(Worker, worker_id)

def create_worker(session: Session, full_name: str, user_id: int | None = None, 
                  cedula: str | None = None, phone: str | None = None, email: str | None = None,
                  address: str | None = None, job_title: str | None = None, 
                  start_date: datetime | None = None, salary: float | None = None) -> Worker:
    
    # Split full_name into first and last name for legacy support
    parts = full_name.strip().split(' ', 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""
    
    worker = Worker(
        full_name=full_name, 
        first_name=first_name,
        last_name=last_name,
        user_id=user_id,
        cedula=cedula,
        phone=phone,
        email=email,
        address=address,
        job_title=job_title,
        start_date=start_date,
        salary=salary
    )
    session.add(worker)
    session.commit()
    session.refresh(worker)
    return worker

def delete_worker(session: Session, worker_id: int) -> bool:
    """Elimina un trabajador y sus metas asociadas."""
    worker = session.get(Worker, worker_id)
    if not worker:
        return False
        
    # Eliminar metas asociadas
    session.query(WorkerGoal).filter(WorkerGoal.worker_id == worker_id).delete()
    
    # Eliminar trabajador
    session.delete(worker)
    session.commit()
    return True

def update_worker(session: Session, worker_id: int, full_name: str | None = None, user_id: int | None = None, is_active: bool | None = None,
                  cedula: str | None = None, phone: str | None = None, email: str | None = None,
                  address: str | None = None, job_title: str | None = None, 
                  start_date: datetime | None = None, salary: float | None = None) -> Worker | None:
    worker = session.get(Worker, worker_id)
    if not worker:
        return None
    
    if full_name is not None:
        worker.full_name = full_name
        # Update legacy fields
        parts = full_name.strip().split(' ', 1)
        worker.first_name = parts[0]
        worker.last_name = parts[1] if len(parts) > 1 else ""
        
    if user_id is not None:
        worker.user_id = user_id
    if is_active is not None:
        worker.is_active = is_active
    
    # Extended fields
    if cedula is not None:
        worker.cedula = cedula
    if phone is not None:
        worker.phone = phone
    if email is not None:
        worker.email = email
    if address is not None:
        worker.address = address
    if job_title is not None:
        worker.job_title = job_title
    if start_date is not None:
        worker.start_date = start_date
    if salary is not None:
        worker.salary = salary
        
    session.commit()
    session.refresh(worker)
    return worker

def get_worker_goal(session: Session, worker_id: int, year: int, month: int) -> WorkerGoal | None:
    return session.query(WorkerGoal).filter(
        WorkerGoal.worker_id == worker_id,
        WorkerGoal.year == year,
        WorkerGoal.month == month
    ).first()

def set_worker_goal(session: Session, worker_id: int, year: int, month: int, target_amount: float) -> WorkerGoal:
    goal = get_worker_goal(session, worker_id, year, month)
    if goal:
        goal.target_amount = target_amount
    else:
        goal = WorkerGoal(worker_id=worker_id, year=year, month=month, target_amount=target_amount)
        session.add(goal)
    
    session.commit()
    session.refresh(goal)
    return goal

def get_worker_goals_by_year(session: Session, worker_id: int, year: int) -> list[WorkerGoal]:
    return session.query(WorkerGoal).filter(
        WorkerGoal.worker_id == worker_id,
        WorkerGoal.year == year
    ).order_by(WorkerGoal.month).all()

# --- Cuentas por Cobrar ---

def get_pending_sales(session: Session) -> list[Sale]:
    """Obtener ventas con saldo pendiente (restante > 0)."""
    from .models import Sale
    return session.query(Sale).filter(Sale.restante > 0.01).order_by(Sale.fecha.desc()).all()

def register_payment(session: Session, sale_id: int, amount_usd: float, payment_method: str, 
                    amount_bs: float = 0.0, exchange_rate: float = 0.0, 
                    reference: str = None, bank: str = None) -> SalePayment:
    """Registrar un pago para una venta existente."""
    from .models import Sale, SalePayment
    
    sale = session.get(Sale, sale_id)
    if not sale:
        raise ValueError(f"Venta {sale_id} no encontrada")
        
    # Crear pago
    payment = SalePayment(
        sale_id=sale_id,
        payment_method=payment_method,
        amount_usd=amount_usd,
        amount_bs=amount_bs,
        exchange_rate=exchange_rate,
        reference=reference,
        bank=bank
    )
    session.add(payment)
    
    # Actualizar venta
    sale.abono_usd = (sale.abono_usd or 0.0) + amount_usd
    sale.restante = max(0.0, (sale.restante or 0.0) - amount_usd)
    
    # Actualizar ingresos si aplica (si es efectivo o pago inmediato)
    # Asumimos que todo pago registrado aquí es un ingreso real
    sale.ingresos_usd = (sale.ingresos_usd or 0.0) + amount_usd
    
    session.commit()
    session.refresh(payment)
    return payment

def get_payments_history(session: Session, limit: int = 100) -> list[SalePayment]:
    """Obtener historial de pagos recientes."""
    from .models import SalePayment, Sale
    return session.query(SalePayment).join(Sale).order_by(SalePayment.payment_date.desc()).limit(limit).all()
