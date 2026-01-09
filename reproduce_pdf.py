from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from pathlib import Path

def generate_test_pdf():
    out = Path("test_80mm.pdf")
    width = 80 * mm
    page_height = 297 * mm
    
    print(f"Width: {width}, Height: {page_height}")
    
    c = canvas.Canvas(str(out), pagesize=(width, page_height))
    c.setPageSize((width, page_height))
    
    c.drawString(10, page_height - 20, "TEST 80mm PDF")
    c.rect(0, 0, width, page_height)
    c.save()
    print(f"Generated {out.absolute()}")

if __name__ == "__main__":
    generate_test_pdf()
