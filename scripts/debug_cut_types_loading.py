"""Script para diagnosticar la carga de tipos de corte en el diálogo Corpóreo."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.admin_app.db import make_engine
from src.admin_app.models import ProductParameterValue, ProductParameterTable
from src.admin_app import repository as _repo
from sqlalchemy.orm import Session
import json

engine = make_engine()

# Simular lo que hace _load_cut_types_from_product
pid = 7  # ID del producto Corpóreo

print(f"=== Diagnóstico de carga de tipos de corte para producto {pid} ===\n")

with Session(engine) as s:
    tables = _repo.get_product_parameter_tables(s, pid, include_inactive=False)
    print(f"Total tablas encontradas: {len(tables)}\n")
    
    # Buscar tablas relacionadas con corte (misma lógica que el diálogo)
    corte_tables = []
    exact_match = None
    
    for t in tables:
        tn = (t.get('table_name') or '').lower()
        dn = (t.get('display_name') or '').lower()
        
        print(f"Evaluando tabla ID {t.get('id')}: '{t.get('display_name')}'")
        print(f"  table_name: {tn}")
        print(f"  display_name: {dn}")
        
        # Prioridad 1: display_name exactamente "cortes"
        if dn == 'cortes':
            print(f"  ✓ EXACT MATCH!")
            exact_match = t
            break
        
        # Prioridad 2: table_name contiene "_cortes_"
        if '_cortes_' in tn:
            print(f"  ✓ Contiene '_cortes_' en table_name (prioridad 2)")
            corte_tables.insert(0, t)
        # Prioridad 3: display_name contiene "tipo" y "corte"
        elif 'tipo' in dn and 'corte' in dn:
            print(f"  ✓ Contiene 'tipo' y 'corte' en display_name (prioridad 3)")
            corte_tables.append(t)
        # Prioridad 4: cualquier tabla que contenga "corte"
        elif 'corte' in dn:
            print(f"  ✓ Contiene 'corte' en display_name (prioridad 4)")
            corte_tables.append(t)
        else:
            print(f"  ✗ No coincide")
        
        print()
    
    if exact_match:
        corte_tables = [exact_match]
        print(f"\n=== EXACT MATCH encontrado, usando solo esta tabla ===")
    
    print(f"\n=== Tablas seleccionadas: {len(corte_tables)} ===")
    for t in corte_tables:
        print(f"  - {t.get('display_name')} (ID: {t.get('id')})")
    
    if corte_tables:
        table = corte_tables[0]
        print(f"\n=== Cargando registros de: {table.get('display_name')} (ID: {table.get('id')}) ===\n")
        
        rows = (
            s.query(ProductParameterValue)
            .filter(ProductParameterValue.parameter_table_id == table['id'])
            .filter(ProductParameterValue.is_active == True)
            .all()
        )
        
        print(f"Registros activos encontrados: {len(rows)}\n")
        
        for r in rows:
            data = json.loads(r.row_data_json or '{}')
            print(f"ID {r.id}:")
            print(f"  Data: {json.dumps(data, ensure_ascii=False, indent=2)}")
            
            # Simular extracción de label
            label = None
            for k in ('tipo de corte', 'tipo_de_corte', 'Tipo de Corte', 'Tipo', 'tipo', 'nombre', 'Nombre', 'name', 'label', 'descripcion', 'display'):
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    label = v.strip()
                    print(f"  → Label extraído (clave '{k}'): '{label}'")
                    break
            
            # Si no encontró label, buscar relaciones
            if not label:
                print(f"  → No se encontró label directo, buscando relaciones...")
                for k, v in data.items():
                    if (k.startswith('id_') or k.endswith('_id')) and isinstance(v, (int, str)):
                        try:
                            related_id = int(v)
                            print(f"    Siguiendo relación: {k} = {related_id}")
                            related_row = s.query(ProductParameterValue).filter(ProductParameterValue.id == related_id).first()
                            if related_row:
                                related_data = json.loads(related_row.row_data_json or '{}')
                                print(f"      Registro relacionado: {json.dumps(related_data, ensure_ascii=False)}")
                                for kk in ('tipo de corte', 'tipo_de_corte', 'Tipo de Corte', 'Tipo', 'tipo', 'nombre', 'name', 'label'):
                                    vv = related_data.get(kk)
                                    if isinstance(vv, str) and vv.strip():
                                        label = vv.strip()
                                        print(f"      → Label extraído del relacionado (clave '{kk}'): '{label}'")
                                        break
                                if label:
                                    break
                        except Exception as e:
                            print(f"      Error al seguir relación: {e}")
            
            if not label:
                label = str(r.id)
                print(f"  → Usando ID como fallback: '{label}'")
            
            print(f"  ✓ LABEL FINAL: '{label}'\n")
    else:
        print("\n⚠️ NO SE ENCONTRARON TABLAS DE CORTE")
