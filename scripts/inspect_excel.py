
import openpyxl

file_path = r"g:\Documents\Dev\Sistema-Admin-2.0.2 - copia\Formato Recibo\formato_recibo.xlsx"

try:
    wb = openpyxl.load_workbook(file_path)
    ws = wb.active
    
    print(f"Sheet Name: {ws.title}")
    print("Non-empty cells:")
    
    for row in ws.iter_rows(max_row=20, max_col=10):
        for cell in row:
            if cell.value:
                print(f"{cell.coordinate}: {cell.value}")
                
except Exception as e:
    print(f"Error: {e}")
