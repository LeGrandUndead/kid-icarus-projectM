# Re-export only the materials of a model's parts (after a converter change),
# without touching the animation exports.
import subprocess, json, os, shutil, sys
S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = f'{S}/spica/dump/bin/Release/net8.0/dump'
for key, demo, part in [('T05','024','24'),('T05','024','21'),('T05','024','25'),('T05','024','22'),
                        ('V11','051','23'),('P20','091','22')]:
    tmp = f'{S}/matfix/{key}-{part}'
    os.makedirs(tmp, exist_ok=True)
    subprocess.run([D, f'{S}/demo/{demo}/mdl/{part}.bcres', tmp], capture_output=True)
    m = json.load(open(f'{tmp}/materials.json'))
    shutil.copy(f'{tmp}/materials.json', f'{S}/idols/out{key}_{part}/materials.json')
    print(key, part, len(m), sorted({tuple(w) for x in m for w in x['wrap']}))
