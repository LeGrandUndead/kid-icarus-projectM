# New "promotional" animations for the main menu's characters (Palutena,
# Viridi), made bone by bone with rig.py from the strongest poses of their
# idol moves, timed like cutscene / key-art animation rather than game loops:
#
#   intro   (frames 0-39)    on selection: anticipation (the move's wind-up),
#                            a snap into the hero pose with ~10 % overshoot,
#                            joints breaking in succession (body, then arms 2 f
#                            later, head 3 f, hair and cloth 5 f, overshooting
#                            more), a settle;
#   hold    (frames 100-339) the hero pose held, never still: breath, a slow
#                            glance, wind through the hair and cloth (each
#                            strand lagging the one above it), a slow camera
#                            orbit from a low angle; every motion has a
#                            period dividing 240, so the hold loops seamlessly;
#   confirm (frames 400-439) a snap (6 f, overshoot) into a second, triumphant
#                            pose, then held with the same life.
# Renders the relighting buffers (idol.BUFS) into frames/promo_<key>_buf.
#   python3 promo.py P02|V12 [first last]
import sys, os, math
sys.path.insert(0, '.')
import numpy as np, idol, rig
from multiprocessing import Pool

TAU = 2 * math.pi
LOOP = 240
CHARS = {
    # Palutena: the staff thrust out, hair streaming (Action00 88); the
    # wind-up is the staff swung low (32); confirm: staff upright, chest out (122)
    'P02': dict(clip='DolPalu00Action00', wait='DolPalu00Wait', start=('wait', 0), wind=('act', 32), hero=('act', 88), confirm=('act', 122),
                yaw=-24, pitch=-7, orbit=5.0, size=1100,
                hair=['HairL01N', 'HairL02N', 'HairR01N', 'HairR02N', 'HairC01N', 'HairC02N'],
                cloth=['ClothF01N', 'ClothF02N', 'ClothB01N', 'ClothB02N', 'ClothL01N', 'ClothL02N', 'ClothR01N', 'ClothR02N', 'Rope01N', 'Rope02N'],
                chest='BustN', head='HeadN', arms=['LShoulderN', 'LArmN', 'LHandN', 'RShoulderN', 'RArmN', 'RHandN', 'StickN', 'ShieldN']),
    # Viridi: leaning in on tiptoe, staff forward, hair flying (Action00 126);
    # wind-up: the staff wound back (18); confirm: the staff thrust at you (36)
    'V12': dict(clip='DolNatur00Action00', wait='DolNatur00Wait', start=('wait', 0), wind=('act', 18), hero=('act', 126), confirm=('act', 36),
                yaw=-18, pitch=-3, orbit=6.0, size=1100,
                hair=['Hair01N', 'Hair02N', 'Hair03N', 'HairF01N', 'HairF02N', 'HairF03N', 'Sideburns'],
                cloth=['ClothBN', 'ClothFN', 'ClothLN', 'ClothRN'],
                chest='WaistN', head='HeadN', arms=['LShoulderN', 'LArmN', 'LHandN', 'LFingerN', 'LThumbN', 'RShoulderN', 'RArmN', 'RHandN', 'WandN']),
}

def ease_out_back(t, s=1.7):
    t = min(max(t, 0.0), 1.0) - 1; return t * t * ((s + 1) * t + s) + 1
def ease_in(t): t = min(max(t, 0.0), 1.0); return t ** 3
def smooth(t): t = min(max(t, 0.0), 1.0); return t * t * (3 - 2 * t)

class Promo:
    def __init__(self, key):
        self.key = key; self.c = CHARS[key]; self.r = rig.Rig(key)
        clips = dict(act=self.r.clip(self.c['clip']), wait=self.r.clip(self.c['wait']))
        self.pose = {k: clips[v[0]][v[1]] for k, v in self.c.items() if k in ('start', 'wind', 'hero', 'confirm')}
        ix = self.r.index; n = len(self.r.names)
        group = np.zeros(n, int)                   # 0 body, 1 arms, 2 head, 3 hair/cloth
        for b in self.c['arms']: group[ix[b]] = 1
        group[ix[self.c['head']]] = 2
        for b in self.c['hair'] + self.c['cloth']: group[ix[b]] = 3
        self.group = group
        self.delay = np.array([0, 2, 3, 5])[group]     # successive breaking of joints
        self.punch = np.array([1.7, 1.9, 1.7, 2.1])[group]  # overshoot amount per group

    def tween(self, a, b, f, dur, back=True):
        """Per bone from pose a to pose b, `f` frames in, over `dur`, each group delayed and overshooting."""
        t = [(ease_out_back((f - d) / dur, s) if back else smooth((f - d) / dur)) for d, s in zip(self.delay, self.punch)]
        return rig.blend(a, b, t)

    def life(self, loc, f, amount=1.0):
        """The moving hold: breath, glance, wind in hair and cloth. Periods divide LOOP."""
        r, c, ix = self.r, self.c, self.r.index
        loc = rig.turn(loc, ix[c['chest']], (1, 0, 0), amount * 1.3 * math.sin(TAU * f / 120))                 # breath (2 s)
        loc = rig.turn(loc, ix[c['head']], (0, 1, 0), amount * 2.5 * math.sin(TAU * f / 240 + 0.6))            # a slow glance
        loc = rig.turn(loc, ix[c['head']], (0, 0, 1), amount * 1.5 * math.sin(TAU * f / 120 + 1.9))
        for k, b in enumerate(c['hair']):                                                                      # wind: each strand lags the one above
            lag = 0.9 * (1 if b[-2:] in ('2N', '3N') else 0) + 0.5 * k
            loc = rig.turn(loc, ix[b], (1, 0, 0), amount * (6.0 * math.sin(TAU * f / 80 - lag) + 2.5 * math.sin(TAU * f / 48 - 1.3 * lag)))
        for k, b in enumerate(c['cloth']):
            loc = rig.turn(loc, ix[b], (1, 0, 0), amount * 3.5 * math.sin(TAU * f / 60 - 0.7 * k))
        return loc

    def at(self, i):
        """Local pose and camera for buffer frame i."""
        P = self.pose; c = self.c
        if i < 100:                                           # intro
            f = i
            if f < 10: loc = self.tween(P['start'], P['wind'], f, 10, back=False)            # anticipation, easing in
            else: loc = self.tween(P['wind'], P['hero'], f - 10, 12)                          # the snap, overshoot, settle
            loc = self.life(loc, 100, smooth((f - 16) / 24))                                  # life fades in, matching hold frame 0
            g = 0
        elif i < 400:                                         # hold
            g = i - 100; loc = self.life(P['hero'], 100 + g)
        else:                                                 # confirm
            f = i - 400; loc = self.tween(P['hero'], P['confirm'], f, 8)
            loc = self.life(loc, 100 + f, 1.0); g = 0
        yaw = c['yaw'] + c['orbit'] * math.sin(TAU * g / LOOP)
        pitch = c['pitch'] + 1.2 * math.sin(TAU * g / LOOP + 1.0)
        return loc, yaw, pitch

def framing(p):
    """One centre and span for every frame: the union of the key poses, with room."""
    pts = np.concatenate([p.r.skin(p.pose[k])[:, :3] for k in ('start', 'wind', 'hero', 'confirm')])
    lo, hi = np.percentile(pts, 0.5, 0), np.percentile(pts, 99.5, 0)
    return (lo + hi) / 2, float(max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) * 1.08)

P = None; CENTRE = SPAN = None
def one(i):
    global P, CENTRE, SPAN
    key = sys.argv[1]
    if P is None:
        P = Promo(key); CENTRE, SPAN = framing(P)
    pre = f'frames/promo_{key}_buf/{i:04d}'
    if os.path.exists(pre + '_nrm.png'): return
    loc, yaw, pitch = P.at(i)
    R = idol.rot(math.radians(yaw), math.radians(pitch)); c = R @ CENTRE
    idol.POST = dict(rim=(0.9, 0.95, 1.0), light=(-0.85, 0.45, 0.28), dark=0.6, rim_strength=0.8, shadow=(0.75, 0.82, 1.0))
    idol.BUFS = pre
    idol.render(key, P.c['size'], math.radians(yaw), math.radians(pitch), pose=P.r.skin(loc), span_fix=(SPAN, tuple(c)), ss=2).save(pre + '_post.png')

if __name__ == '__main__':
    key = sys.argv[1]; os.makedirs(f'frames/promo_{key}_buf', exist_ok=True)
    jobs = list(range(0, 40)) + list(range(100, 100 + LOOP)) + list(range(400, 440))
    if sys.argv[3:]: jobs = [j for j in jobs if int(sys.argv[2]) <= j <= int(sys.argv[3])]
    with Pool(2) as pool: pool.map(one, jobs, chunksize=1)
    print('ok', key, len(jobs))
