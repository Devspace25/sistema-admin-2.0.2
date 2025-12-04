from pathlib import Path
import json
import sys

# Asegurar import de src.* cuando se ejecuta desde scripts/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.admin_app.receipts import print_order_pdf

out = Path('data/receipts/__test_ticket.pdf')
out.parent.mkdir(parents=True, exist_ok=True)

payload = {
    "items": [
        {"descripcion": "Corpóreo de prueba áéíóú", "cantidad": 2, "subtotal_bs": 150.0},
        {"descripcion": "Instalación", "cantidad": 1, "subtotal_bs": 50.0}
    ],
    "totals": {"total_bs": 200.0, "total_usd": 20.0},
    "meta": {"tasa_bcv": 10.0, "cliente": {"name": "Cliente Demo", "document": "V-12345678"}}
}

path = print_order_pdf(order_id=123, sale_id=0, product_name='Servicio Demo', status='pendiente', details_json=json.dumps(payload), out_path=out)
print('PDF generado en:', path)
print('Existe?', Path(path).exists())
