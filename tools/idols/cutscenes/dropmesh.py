# Removes meshes (by name) from a converted model: geometry, materials and
# every animation export, so nothing else has to be re-exported.
import sys, os, json, glob, numpy as np
def drop(d, names):
    lines = [l.rstrip('\n') for l in open(f'{d}/meshes.txt') if l.strip()]
    v = np.fromfile(f'{d}/mesh.bin', np.float32).reshape(-1, 16)
    M = json.load(open(f'{d}/materials.json'))
    keep, at, kl, km = [], 0, [], []
    for l, m in zip(lines, M):
        n = int(l.split('\t')[1])
        if l.split('\t')[2] not in names:
            keep.append(np.arange(at, at + n)); kl.append(l); km.append(m)
        at += n
    k = np.concatenate(keep)
    for f in glob.glob(f'{d}/*.frames'):
        fr = np.fromfile(f, np.float32).reshape(-1, len(v), 6)
        fr[:, k].tofile(f)
    v[k].tofile(f'{d}/mesh.bin')
    open(f'{d}/meshes.txt', 'w').write('\n'.join(kl) + '\n')
    json.dump(km, open(f'{d}/materials.json', 'w'))
    print(d, len(v), '->', len(k), 'vertices')
if __name__ == '__main__':
    drop(sys.argv[1], set(sys.argv[2:]))
