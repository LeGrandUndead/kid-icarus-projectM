# A small keyframe toolkit for the mock-ups, after the motion notes
# (claude/MOTION_DESIGN_NOTES.md). Everything is in frames at 60 fps.
#
#   x = track(f, [(0, -400), (24, 0, 'out_back'), (150, 0), (162, -900, 'in')])
#       a value keyed at frames; each key says how we arrive at it
#   s = stagger(f, start=10, i=2, step=3)      the frame as seen by sibling i
#   dx, dy = shake(f, start=190, frames=22, amp=16, axis='x')
#   sx, sy = squash(f, start=150)              a press: squash then overshoot back
import math, random

# --- curves: t in 0..1 -> progress (may pass 1 for overshoot) -------------------
def linear(t): return t
def out(t): return 1 - (1 - t) ** 4                     # quart out: entering
def out_expo(t): return 1 if t >= 1 else 1 - 2 ** (-10 * t)
def in_(t): return t ** 3                                # cubic in: leaving
def in_out(t): return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
def out_back(t, s=1.7):                                  # overshoot ~10% then settle
    t -= 1; return t * t * ((s + 1) * t + s) + 1
def spring(t, freq=2.5, decay=9.0, dur=1.0):
    """A decaying spring: over `dur` seconds of t, about `freq` wobbles."""
    x = t * dur; return 1 - math.exp(-decay * x) * math.cos(2 * math.pi * freq * x)
CURVES = {'linear': linear, 'out': out, 'out_expo': out_expo, 'in': in_, 'in_out': in_out,
          'out_back': out_back, 'spring': spring}

def clamp01(t): return 0.0 if t < 0 else 1.0 if t > 1 else t

def track(f, keys):
    """Value at frame f. keys: [(frame, value[, curve])], frames rising; the
    curve of a key shapes the way from the previous key to it (default 'out').
    Values can be numbers or tuples."""
    if f <= keys[0][0]: return keys[0][1]
    for a, b in zip(keys, keys[1:]):
        if f <= b[0]:
            t = clamp01((f - a[0]) / max(1e-9, b[0] - a[0]))
            k = CURVES[b[2] if len(b) > 2 else 'out'](t)
            if isinstance(a[1], tuple): return tuple(x + (y - x) * k for x, y in zip(a[1], b[1]))
            return a[1] + (b[1] - a[1]) * k
    return keys[-1][1]

def stagger(f, start, i, step=3):
    """Frame f as seen by the i-th sibling of a group starting at `start`."""
    return f - start - i * step

def shake(f, start, frames, amp, axis='x', seed=0):
    """A decaying shake: strongest at `start`, gone after `frames`. 'x' for a
    hit on the ground, 'y' in the air, 'xy' for both (Sakurai)."""
    t = f - start
    if t < 0 or t >= frames: return 0.0, 0.0
    a = amp * (1 - t / frames) ** 2; s = -1 if t % 2 else 1          # alternate sides each frame
    r = random.Random(seed * 1000 + t).uniform(0.6, 1.0)
    dx = a * s * r if 'x' in axis else 0.0; dy = a * s * r * (0.6 if axis == 'xy' else 1) if 'y' in axis else 0.0
    return dx, dy

def squash(f, start, depth=0.08, frames=4, settle=14):
    """A press: squash (wider, shorter) for `frames`, then spring back with a
    small overshoot. Returns (scale x, scale y)."""
    t = f - start
    if t < 0: return 1.0, 1.0
    if t < frames:
        k = out(t / frames); return 1 + depth * 0.6 * k, 1 - depth * k
    k = clamp01((t - frames) / settle); s = 1 - depth * (1 - spring(k, freq=2, decay=6, dur=0.8))
    return 2 - s if s < 1 else s, s

def hold_then(f, start, hold):
    """Animation time with a hold: frames after `start` freeze for `hold` frames."""
    if f < start: return f
    if f < start + hold: return start
    return f - hold
