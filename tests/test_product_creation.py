
import pytest
from sqlalchemy.exc import IntegrityError
from src.admin_app.repository import create_configurable_product, update_configurable_product
from src.admin_app.models import ConfigurableProduct

def test_create_duplicate_product(session_factory):
    """Verificar que no se pueden crear productos con nombre duplicado."""
    with session_factory() as session:
        # Crear primer producto
        create_configurable_product(session, "Producto Test")
        session.commit()
        
        # Intentar crear segundo producto con mismo nombre
        with pytest.raises(ValueError) as excinfo:
            create_configurable_product(session, "Producto Test")
        
        assert "Ya existe un producto con el nombre" in str(excinfo.value)

def test_update_duplicate_product(session_factory):
    """Verificar que no se puede renombrar un producto a un nombre existente."""
    with session_factory() as session:
        # Crear dos productos
        id1 = create_configurable_product(session, "Producto A")
        id2 = create_configurable_product(session, "Producto B")
        session.commit()
        
        # Intentar renombrar B a A
        with pytest.raises(ValueError) as excinfo:
            update_configurable_product(session, id2, "Producto A")
            
        assert "Ya existe un producto con el nombre" in str(excinfo.value)

def test_update_product_success(session_factory):
    """Verificar que se puede actualizar nombre y descripción correctamente."""
    with session_factory() as session:
        # Crear producto
        pid = create_configurable_product(session, "Producto Original", "Desc Original")
        session.commit()
        
        # Actualizar
        update_configurable_product(session, pid, "Producto Editado", "Desc Editada")
        session.commit()
        
        # Verificar cambios
        prod = session.get(ConfigurableProduct, pid)
        assert prod.name == "Producto Editado"
        assert prod.description == "Desc Editada"

def test_delete_product(session_factory):
    """Verificar que se puede eliminar (desactivar) un producto."""
    from src.admin_app.repository import delete_configurable_product
    
    with session_factory() as session:
        # Crear producto
        pid = create_configurable_product(session, "Producto a Eliminar")
        session.commit()
        
        # Eliminar
        delete_configurable_product(session, pid)
        session.commit()
        
        # Verificar que is_active es False
        prod = session.get(ConfigurableProduct, pid)
        assert prod.is_active is False

