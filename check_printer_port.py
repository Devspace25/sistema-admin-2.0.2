import win32print

def get_printer_port(printer_name):
    printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
    for p in printers:
        name = p[2]
        if name == printer_name:
            # Level 2 gives more details including port
            try:
                handle = win32print.OpenPrinter(name)
                info = win32print.GetPrinter(handle, 2)
                win32print.ClosePrinter(handle)
                print(f"Printer: {name}, Port: {info['pPortName']}")
            except Exception as e:
                print(f"Error getting info for {name}: {e}")

if __name__ == "__main__":
    get_printer_port("Microsoft Print to PDF")
