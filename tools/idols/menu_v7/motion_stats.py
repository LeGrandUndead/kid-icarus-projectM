# How much does each part of the screen move, frame to frame? (stiffness check)
#   python3 motion_stats.py <frames_dir>
import sys, numpy as np
from PIL import Image
d = sys.argv[1]
def load(i): return np.asarray(Image.open(f'{d}/{i:04d}.png').convert('L').resize((480, 270)), np.float32)
regions = {'paper+menu (left)': (0, 0, 200, 230), 'window (right)': (260, 20, 480, 220), 'heading': (10, 5, 170, 60), 'band': (0, 230, 480, 270)}
prev = load(0); rows = []
for i in range(1, 560):
    cur = load(i); diff = np.abs(cur - prev); prev = cur
    rows.append({k: diff[y0:y1, x0:x1].mean() for k, (x0, y0, x1, y1) in regions.items()})
segs = [('Solo hold', 62, 128), ('Together hold', 152, 228), ('Vault hold', 252, 318), ('Options hold', 342, 418)]
for name, a, b in segs:
    print(name, {k: round(float(np.mean([r[k] for r in rows[a:b]])), 2) for k in regions},
          'still frames in window:', sum(r['window (right)'] < 0.3 for r in rows[a:b]), '/', b - a)
