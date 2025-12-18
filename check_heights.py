import openpyxl
from pathlib import Path

template_path = Path.cwd() / "Formato Recibo" / "FORMATO DE INGRESOS DIARIOS.xlsx"
wb = openpyxl.load_workbook(template_path)
ws = wb.active

for row in range(1, ws.max_row + 1):
    rd = ws.row_dimensions[row]
    print(f"Row {row} height: {rd.height}")
