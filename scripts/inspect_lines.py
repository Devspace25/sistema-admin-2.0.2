from pathlib import Path
p = Path('src/admin_app/ui/corporeo_dialog.py')
s = p.read_text(encoding='utf-8')
lines = s.splitlines()
for i in range(2558, 2592):
    if i < 1 or i > len(lines):
        continue
    ln = lines[i-1]
    print(f"{i:4d}: {repr(ln)}")
