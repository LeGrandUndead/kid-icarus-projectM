# Pit for the in-game main menu (Solo): a seamless 6-second glide loop and a
# confirm move, rendered with the relighting buffers (idol.BUFS).
#  - loop (frames 0-359): his flap cycle (AirGrideFlap1, 90 frames) four
#    times; heading and pitch swing on curves with the same 360-frame period,
#    he banks into the turns (bank from the heading's rate of turn) and
#    glances back once (AirGrideLookB at 150, faded in and out inside the loop),
#    so frame 360 is frame 0 again;
#  - confirm (frames 1000-1047): from loop frame 0 he whips round toward the
#    camera and barrel-rolls past it (AirRollingGrideRA), as in sky.py's click.
#   python3 solo_loop.py [first last]  ->  frames/solo_loop_buf/NNNN_{base,nrm,post}.png
import sys, os, math
sys.path.insert(0, '.')
import numpy as np, idol, sky
from multiprocessing import Pool
SIZE = 1300; PERIOD = 360; LOOK = (150, 'AirGrideLookB', 1.0); CONFIRM = 1000
def yaw_pitch(f):
    a = 2 * math.pi * f / PERIOD
    return -24 + 22 * math.sin(a) + 6 * math.sin(2 * a + 1), 7 + 5 * math.sin(a + 2)
def loop_entry(f):
    yaw, pitch = yaw_pitch(f); y2, _ = yaw_pitch(f + 1)
    return dict(f=f, yaw=yaw, pitch=pitch, bank=max(-35, min(35, -(y2 - yaw) * 14 * 4)))
def loop_pose(f):
    loop = sky.clip(sky.LOOP); out = loop[f % len(loop)]
    s, a, sp = LOOK; c = sky.clip(a); t = (f - s) * sp
    if 0 <= t < len(c) - 1 + sky.FADE:
        w = min(1, (t + 1) / sky.FADE) * min(1, (len(c) - 1 + sky.FADE - t) / sky.FADE)
        out = out * (1 - w) + c[min(len(c) - 1, int(t))] * w
    out = out.copy(); n = out[:, 3:6]; out[:, 3:6] = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
    return out
def confirm_entry(g):
    """g frames after the click, starting from loop frame 0."""
    e = loop_entry(0); k = min(1.0, g / 14)
    k = k * k * (3 - 2 * k)
    e.update(f=CONFIRM + g, yaw=e['yaw'] + (-25 - e['yaw']) * k, pitch=e['pitch'] + (18 - e['pitch']) * k, bank=e['bank'] * (1 - k))
    return e
def confirm_pose(g):
    c = sky.clip('AirRollingGrideRA'); w = min(1, (g + 1) / 4)
    out = loop_pose(0) * (1 - w) + c[min(len(c) - 1, int(g * 1.25))] * w
    out = out.copy(); n = out[:, 3:6]; out[:, 3:6] = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
    return out
def one(e):
    pre = f'frames/solo_loop_buf/{e["f"]:04d}'
    if os.path.exists(pre + '_nrm.png'): return
    R = idol.rot(math.radians(e['yaw']), math.radians(e['pitch']), math.radians(e['bank'])); c = R @ sky.CENTRE
    idol.POST = dict(rim=(0.9, 0.95, 1.0), light=(-0.85, 0.45, 0.28), dark=0.6, rim_strength=0.8, shadow=(0.75, 0.82, 1.0))
    idol.BUFS = pre
    pose = loop_pose(e['f']) if e['f'] < CONFIRM else confirm_pose(e['f'] - CONFIRM)
    idol.render(sky.MODEL, SIZE, math.radians(e['yaw']), math.radians(e['pitch']), rim=(1.0, 0.55, 0.7), bank=math.radians(e['bank']),
                pose=pose, span_fix=(sky.SPAN, tuple(c)), ss=2).save(pre + '_post.png')
if __name__ == '__main__':
    os.makedirs('frames/solo_loop_buf', exist_ok=True)
    jobs = [loop_entry(f) for f in range(PERIOD)] + [confirm_entry(g) for g in range(48)]
    if sys.argv[2:]: jobs = [j for j in jobs if int(sys.argv[1]) <= j['f'] <= int(sys.argv[2])]
    with Pool(2) as p: p.map(one, jobs, chunksize=1)
    print('ok', len(jobs))
