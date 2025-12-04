import ast
from pathlib import Path
p = Path(r'c:\Users\Jesus\OneDrive\Documents\Sistema-Admin-2.0\src\admin_app\ui\corporeo_dialog.py')
s = p.read_text(encoding='utf-8')
lines = s.splitlines()
lo = 1
hi = len(lines)
bad = None
# binary search for first failing prefix
while lo <= hi:
    mid = (lo + hi) // 2
    chunk = '\n'.join(lines[:mid])
    try:
        ast.parse(chunk)
        lo = mid + 1
    except SyntaxError as e:
        bad = (mid, e)
        hi = mid - 1
if bad:
    mid, e = bad
    print('First failing parse at prefix ending on line', mid)
    print('SyntaxError:', e.msg, 'line', e.lineno, 'offset', e.offset)
    start = max(0, e.lineno - 6)
    end = min(len(lines), e.lineno + 3)
    for i in range(start, end):
        ln = i+1
        mark = '>>' if ln == e.lineno else '  '
        print(f"{mark} {ln:4d}: {lines[i]}")
else:
    print('No syntax error found by binary search')
