p = r'c:\Users\Jesus\OneDrive\Documents\Sistema-Admin-2.0\src\admin_app\ui\corporeo_dialog.py'
start=2568
end=2588
with open(p,'r',encoding='utf-8') as f:
    lines = f.read().splitlines()
for i in range(start-1, end):
    ln = i+1
    line = lines[i]
    # count leading spaces
    leading = len(line) - len(line.lstrip(' '))
    print(f"{ln:4d} [{leading:2d}]: {line!r}")
