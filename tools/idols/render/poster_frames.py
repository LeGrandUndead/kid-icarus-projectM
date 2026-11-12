# Together for the action poster (direction 1): the same timeline as
# cast.py (idle grapple, click at 150, the throw and kick), seen from a lower
# angle (yaw -30, pitch -12), bigger, with one fixed framing that holds the
# whole move.   python3 poster_frames.py [last_frame]  ->  frames/poster_tog/NNNN.png
import sys, os, math, json
sys.path.insert(0, '.')
import numpy as np, idol, cast
from multiprocessing import Pool
YAW, PITCH, SIZE, LAST = -30, -12, 1400, int(sys.argv[1]) if sys.argv[1:] else 216
T = json.load(open('frames/together.json'))['timeline'][:LAST]
R = idol.rot(math.radians(YAW), math.radians(PITCH))
def spec(e): return [(a, x, w, None if s is None else np.array(s)) for a, x, w, s in e['spec']]
pts = np.concatenate([cast.pose('T05', spec(e))[:, :3] @ R.T for e in T[::5]])
lo, hi = np.percentile(pts, 0.5, axis=0), np.percentile(pts, 99.5, axis=0)
FRAMING = (float(max(hi[0] - lo[0], hi[1] - lo[1]) * 1.06), tuple(((lo + hi) / 2).tolist()))
def one(e):
    out = f'frames/poster_tog_buf/{e["f"]:04d}_post.png'
    if os.path.exists(f'frames/poster_tog_buf/{e["f"]:04d}_nrm.png'): return
    idol.BUFS = f'frames/poster_tog_buf/{e["f"]:04d}'
    idol.POST = dict(rim=(1.0, 0.85, 0.65), light=(-0.85, 0.45, 0.28), dark=0.55, rim_strength=0.8, shadow=(0.75, 0.6, 1.0))
    idol.render('T05', SIZE, math.radians(YAW), math.radians(PITCH), pose=cast.pose('T05', spec(e)), span_fix=FRAMING, ss=2).save(out)
if __name__ == '__main__':
    os.makedirs('frames/poster_tog_buf', exist_ok=True)
    with Pool(2) as p: p.map(one, T, chunksize=1)
    print('ok', len(T))
