import openpyxl
from pathlib import Path

template_path = Path.cwd() / "Formato Recibo" / "FORMATO DE INGRESOS DIARIOS.xlsx"
wb = openpyxl.load_workbook(template_path)
ws = wb.active

width = 0
for col in range(1, 20):
    char = openpyxl.utils.get_column_letter(col)
    cd = ws.column_dimensions[char]
    w = cd.width
    print(f"Col {char} width: {w}")
    if w:
        width += w
    else:
        width += 8.43 # Default width

print(f"Total width units: {width}")
