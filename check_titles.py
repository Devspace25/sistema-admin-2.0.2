import openpyxl
from pathlib import Path

template_path = Path.cwd() / "Formato Recibo" / "FORMATO DE INGRESOS DIARIOS.xlsx"
wb = openpyxl.load_workbook(template_path)
ws = wb.active

print(f"Print title rows: {ws.print_title_rows}")
print(f"Print title cols: {ws.print_title_cols}")
