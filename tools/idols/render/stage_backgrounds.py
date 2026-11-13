# The main menu's stage backgrounds: each mode's game stage seen from inside
# (stage_view.py), 1280x720, written to $IDOLS_WORK/redraw/bg/<mode>.png,
# where the menu pack builder reads them (menu_pack/config.py,
# STAGE_RENDERS) and grades them in the mode's colours.
#   together: chapter 6 (g0601)   vault: chapter 20 (g2001)   options: chapter 11 (g1101)
#   (Solo's sky is built from chapter 1's textures by menu_pack/layers.py.)
#   python3 stage_backgrounds.py [together|vault|options ...]   (in this folder)
import os, sys
S = os.environ.get('IDOLS_WORK', 'work')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stage_view import view
OUT = f'{S}/redraw/bg'
SHOTS = {
    'together': dict(key='G06', eye=(-300, 300, 500), target=(-400, 500, -1500), fov_deg=55),
    'vault': dict(key='G20s', eye=(2200, 250, 600), target=(3100, 550, -3790), fov_deg=55,
                  skip=('hikari', 'hikari2', 'hane', 'hane2')),     # animated light beams
    'options': dict(key='G11s', eye=(-1500, -150, -200), target=(-3000, -450, -1500), fov_deg=60),
}
if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for name in sys.argv[1:] or SHOTS:
        view(W=1280, H=720, **SHOTS[name]).save(f'{OUT}/{name}.png'); print(name, flush=True)
