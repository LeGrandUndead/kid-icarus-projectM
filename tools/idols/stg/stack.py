# A game stage as one model, for the menus' backgrounds (render/stage_view.py).
# A stage (RomFS stage/<id>/stage) is split into sections: mdl00..mdlNN hold
# the static geometry, comtex.arc the shared textures, bindNN.arc each
# section's own. Each section is converted, then everything is stacked:
#   idols/out<KEY>: mesh.bin, meshes.txt, materials.json, luts.json
#   idols/tex<KEY>: every texture (.rgba + textures.txt)
#   python3 stack.py g0601 G06   (stage folder unpacked under x/stage/)
import sys, os, glob, json, shutil, subprocess
S = os.environ.get('IDOLS_WORK') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = f'{S}/spica/dump/bin/Release/net8.0/dump'

def stack(stage, key):
    src = f'{S}/x/stage/{stage}/stage'
    out, tex, tmp = f'{S}/idols/out{key}', f'{S}/idols/tex{key}', f'{S}/stg/{stage}'
    for d in (out, tex): shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    # 1. each section's geometry and materials
    mesh = open(f'{out}/mesh.bin', 'wb'); lines = []; mats = []; luts = {}
    for sec in sorted(glob.glob(f'{src}/mdl[0-9][0-9]')):
        name = os.path.basename(sec); d = f'{tmp}/{name}'
        subprocess.run([D, glob.glob(f'{sec}/mdl/*.bcres')[0], d], capture_output=True)
        if not os.path.exists(f'{d}/mesh.bin'): continue
        mesh.write(open(f'{d}/mesh.bin', 'rb').read())
        lines += [l for l in open(f'{d}/meshes.txt') if not l.startswith('#')]
        if os.path.exists(f'{d}/materials.json'): mats += json.load(open(f'{d}/materials.json'))
        if os.path.exists(f'{d}/luts.json'): luts.update(json.load(open(f'{d}/luts.json')))
    mesh.close()
    open(f'{out}/meshes.txt', 'w').writelines(lines)
    json.dump(mats, open(f'{out}/materials.json', 'w')); json.dump(luts, open(f'{out}/luts.json', 'w'))
    # 2. every texture: the shared ones and each section's
    names = {}
    for arc in sorted(glob.glob(f'{src}/comtex') + glob.glob(f'{src}/bind[0-9][0-9]')):
        d = f'{tmp}/tex_{os.path.basename(arc)}'
        subprocess.run([D, glob.glob(f'{arc}/*/*.bcres')[0], d, 'textures'], capture_output=True)
        if not os.path.exists(f'{d}/textures.txt'): continue
        for l in open(f'{d}/textures.txt'):
            n = l.split('\t')[0]
            if n not in names: names[n] = l; shutil.copy(f'{d}/{n}.rgba', f'{tex}/{n}.rgba')
    open(f'{tex}/textures.txt', 'w').writelines(names.values())
    print(key, len(lines), 'meshes', len(mats), 'materials', len(names), 'textures')

if __name__ == '__main__':
    stack(sys.argv[1], sys.argv[2])
