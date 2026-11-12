# The menus' backgrounds: each mode's game stage seen from inside
# (stage_view.py), 1280x720, written to bg/<mode>.png. The Dream layout then
# blurs and washes them (still_v7.dream_bg).
#   together: chapter 6 (g0601)   vault: chapter 20 (g2001)   options: chapter 11 (g1101)
import os, sys
S = os.environ.get('IDOLS_WORK', 'work')
sys.path.insert(0, S + '/render'); sys.path.insert(0, '.')
from stage_view import view
SHOTS = {
    'together': dict(key='G06', eye=(-300, 300, 500), target=(-400, 500, -1500), fov_deg=55),
    'vault': dict(key='G20s', eye=(2200, 250, 600), target=(3100, 550, -3790), fov_deg=55,
                  skip=('hikari', 'hikari2', 'hane', 'hane2')),     # animated light beams
    'options': dict(key='G11s', eye=(-1500, -150, -200), target=(-3000, -450, -1500), fov_deg=60),
}
if __name__ == '__main__':
    os.makedirs('bg', exist_ok=True)
    for name in sys.argv[1:] or SHOTS:
        view(W=1280, H=720, **SHOTS[name]).save(f'bg/{name}.png'); print(name, flush=True)
