# How varied is the colour? OKLab per region: lightness spread, chroma, and the
# spread of hues (a flat image has one hue and one chroma everywhere).
#   python3 colour_stats.py img.png [x0 y0 x1 y1]
import sys, numpy as np
from PIL import Image
def oklab(rgb):
    a = rgb / 255; lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566], [0.0883024619, 0.2817188376, 0.6299787005]])
    M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099], [0.0259040371, 0.7827717662, -0.8086757660]])
    return np.cbrt(lin @ M1.T) @ M2.T
def stats(img, box):
    a = np.asarray(Image.open(img).convert('RGB').crop(box), np.float32).reshape(-1, 3); lab = oklab(a)
    L, A, B = lab[:, 0], lab[:, 1], lab[:, 2]; C = np.hypot(A, B); h = np.degrees(np.arctan2(B, A))
    sat = C > 0.03
    hs = h[sat]
    # circular spread of hue (0 = one hue)
    R = np.hypot(np.cos(np.radians(hs)).mean(), np.sin(np.radians(hs)).mean()) if len(hs) else 1
    return dict(L_p10_p90=(round(float(np.percentile(L, 10)), 2), round(float(np.percentile(L, 90)), 2)),
                chroma_med=round(float(np.median(C)), 3), chroma_p90=round(float(np.percentile(C, 90)), 3),
                hue_spread=round(float(np.degrees(np.sqrt(-2 * np.log(max(R, 1e-6))))), 1))
if __name__ == '__main__':
    box = tuple(map(int, sys.argv[2:6])) if len(sys.argv) > 5 else (1200, 60, 1900, 880)
    print(sys.argv[1].split('/')[-1], stats(sys.argv[1], box))
