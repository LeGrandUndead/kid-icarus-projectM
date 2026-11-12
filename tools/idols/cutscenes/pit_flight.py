# The cutscene Pit (demo/098: body 21, high-detail head 22) on his gameplay
# flight moves (player/a0), for the Solo sky (render/sky.py, model PitHF).
# The moves are the gameplay skeleton's; 26/29 bones match the cutscene body.
# The head is put on the body's HeadN every frame (merge.py), the body's own
# low face is dropped.   python3 pit_flight.py  ->  idols/outPitHF
import sys, os, glob, subprocess, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import merge
S = os.environ.get('IDOLS_WORK') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = f'{S}/spica/dump/bin/Release/net8.0/dump'
A0 = glob.glob(f'{S}/x/player/a0/character/mdl/mdl/*.bcres')[0]     # Pit's air moves
MOVES = ['AirGrideFlap1', 'AirGrideL', 'AirGrideR', 'AirGrideLookB', 'AirRollingGrideLA', 'AirRollingGrideRA']
STEP = 1.0          # one game frame per menu frame (60 fps)

def export(part, out, anim):
    os.makedirs(out, exist_ok=True)
    r = subprocess.run([D, f'{S}/demo/098/mdl/{part}.bcres', out, anim, str(STEP), A0], capture_output=True, text=True)
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()

if __name__ == '__main__':
    body, head = f'{S}/idols/outPitHF_21', f'{S}/idols/outPitHF_22'
    for m in MOVES:
        a = 'ChrPit00' + m
        print(m, '| body:', export('21', body, a), '| head:', export('22', head, a))
        merge.merge(f'{S}/idols/outPitHF', [(body, a, {'Face'}), (head, a, set(), (body, a), 'HeadN')], a)
