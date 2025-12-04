import ast
from pathlib import Path
import sys
p = Path('src/admin_app/ui/corporeo_dialog.py')
if not p.exists():
    print('file not found', p)
    sys.exit(2)
s = p.read_text(encoding='utf-8')
try:
    ast.parse(s)
    print('OK: parsed without SyntaxError')
except SyntaxError as e:
    print('SyntaxError:', getattr(e,'msg',None), 'line', getattr(e,'lineno',None), 'offset', getattr(e,'offset',None))
    lines = s.splitlines()
    start = max(0, (e.lineno or 1) - 6)
    end = min(len(lines), (e.lineno or 1) + 3)
    for i in range(start, end):
        ln = i + 1
        mark = '>>' if ln == e.lineno else '  '
        print(f"{mark} {ln:4d}: {lines[i]}")
    sys.exit(1)
except Exception as ex:
    print('Unexpected parsing error:', ex)
    sys.exit(3)
