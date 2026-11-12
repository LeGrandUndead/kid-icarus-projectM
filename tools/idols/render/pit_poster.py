# Pit gliding for the Solo poster (menu v8): the Solo sky's own timeline
# (sky.py: his flight moves, heading swings, banking), rendered bigger and
# sharper (1300 px, 2x supersampling), one fixed framing.
#   python3 pit_poster.py [count]  ->  frames/poster_solo/NNNN.png
import sys, os, math
sys.path.insert(0, '.')
import idol, sky
from multiprocessing import Pool
SIZE = 1300
COUNT = int(sys.argv[1]) if sys.argv[1:] else 110
def one(e):
    out = f'frames/poster_solo_buf/{e["f"]:04d}_post.png'
    if os.path.exists(f'frames/poster_solo_buf/{e["f"]:04d}_nrm.png'): return
    idol.BUFS = f'frames/poster_solo_buf/{e["f"]:04d}'
    R = idol.rot(math.radians(e['yaw']), math.radians(e['pitch']), math.radians(e['bank'])); c = R @ sky.CENTRE
    idol.POST = dict(rim=(0.9, 0.95, 1.0), light=(-0.85, 0.45, 0.28), dark=0.6, rim_strength=0.8, shadow=(0.75, 0.82, 1.0))
    idol.render(sky.MODEL, SIZE, math.radians(e['yaw']), math.radians(e['pitch']), rim=(1.0, 0.55, 0.7), bank=math.radians(e['bank']),
                pose=sky.pose(e['f']), span_fix=(sky.SPAN, tuple(c)), ss=2).save(out)
if __name__ == '__main__':
    os.makedirs('frames/poster_solo_buf', exist_ok=True)
    T = sky.timeline()[:COUNT]
    with Pool(2) as p: p.map(one, T, chunksize=1)
    print('ok', len(T))
