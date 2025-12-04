from PIL import Image
from pathlib import Path

# Convert assets/img/logo.png -> assets/img/logo.ico with multiple sizes
png_path = Path('assets/img/logo.png')
ico_path = Path('assets/img/logo.ico')

if not png_path.exists():
    raise SystemExit(f"No se encontró {png_path}")

img = Image.open(png_path).convert('RGBA')
# Create RGBA white background to avoid transparency issues on some shells
bg = Image.new('RGBA', img.size, (255, 255, 255, 0))
bg.paste(img, (0, 0), img)

sizes = [(16,16), (24,24), (32,32), (48,48), (64,64), (128,128), (256,256)]
resized = [bg.resize(s, Image.Resampling.LANCZOS) for s in sizes]

resized[0].save(ico_path, sizes=sizes, format='ICO')
print(f"Generado {ico_path}")
