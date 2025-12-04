import sqlite3, os, sys, json
p = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'app.db')
print('Using DB:', p)
if not os.path.exists(p):
    print('DB not found:', p)
    sys.exit(1)
con = sqlite3.connect(p)
cur = con.cursor()

print('\n=== SALES (last 20) ===')
try:
    for row in cur.execute('SELECT id, numero_orden, articulo, venta_usd, created_at FROM sales ORDER BY id DESC LIMIT 20'):
        print(row)
except Exception as e:
    print('Error reading sales:', e)

print('\n=== ORDERS (last 20) ===')
try:
    for row in cur.execute('SELECT id, order_number, sale_id, product_name, status, created_at, details_json FROM orders ORDER BY id DESC LIMIT 20'):
        print(row)
except Exception as e:
    print('Error reading orders:', e)

con.close()
print('\nDone')
