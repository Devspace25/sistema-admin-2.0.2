import openpyxl
from pathlib import Path

template_path = Path.cwd() / "Formato Recibo" / "FORMATO DE INGRESOS DIARIOS.xlsx"
wb = openpyxl.load_workbook(template_path)
ws = wb.active

print(f"Row breaks: {len(ws.row_breaks)}")
for rb in ws.row_breaks:
    print(f"Break at row: {rb}")

print(f"Col breaks: {len(ws.col_breaks)}")
for cb in ws.col_breaks:
    print(f"Break at col: {cb}")
