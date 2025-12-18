import win32print

def list_printers():
    printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
    for p in printers:
        print(f"Printer: {p[2]}")

if __name__ == "__main__":
    list_printers()
