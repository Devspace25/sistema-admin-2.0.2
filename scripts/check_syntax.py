import ast, sys
p = r'c:\Users\Jesus\OneDrive\Documents\Sistema-Admin-2.0\src\admin_app\ui\corporeo_dialog.py'
with open(p, 'r', encoding='utf-8') as f:
    s = f.read()
try:
    ast.parse(s)
    print('OK')
except SyntaxError as e:
    print('SyntaxError:', e.msg, 'line', e.lineno, 'offset', e.offset)
    lines = s.splitlines()
    start = max(0, e.lineno - 6)
    end = min(len(lines), e.lineno + 3)
    for i in range(start, end):
        ln = i + 1
        mark = '>>' if ln == e.lineno else '  '
        print(f"{mark} {ln:4d}: {lines[i]}")
    sys.exit(1)
