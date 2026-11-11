# Puts several converted models into one (a cutscene body and its head),
# dropping meshes by material name; their animation frames are joined too.
import sys, os, numpy as np
def bones(d, anim):
    names=open(f'{d}/bones.txt').read().split()
    return names, np.fromfile(f'{d}/{anim}.bones',dtype=np.float32).reshape(-1,len(names),4,4)
def attach(fr, body, head, bone):
    # head vertices (row vectors, System.Numerics order): onto the body's bone,
    # matching the head model's own bone of the same name
    bn,bm=body; hn,hm=head; n=min(len(fr),len(bm),len(hm))
    out=fr[:n].copy()
    for k in range(n):
        M=np.linalg.inv(hm[k,hn.index(bone)])@bm[k,bn.index(bone)]
        p=np.c_[fr[k,:,0:3],np.ones(len(fr[k]))]@M; out[k,:,0:3]=p[:,:3]
        nn=fr[k,:,3:6]@M[:3,:3]; out[k,:,3:6]=nn/np.maximum(np.linalg.norm(nn,axis=1,keepdims=True),1e-6)
    return out
def merge(out, parts, anim_out):
    os.makedirs(out, exist_ok=True)
    verts=[]; lines=[]; texl=[]; frames=[]
    for part in parts:
        d, anim, drop = part[:3]
        v=np.fromfile(f'{d}/mesh.bin',dtype=np.float32).reshape(-1,16)
        fr=np.fromfile(f'{d}/{anim}.frames',dtype=np.float32).reshape(-1,len(v),6)
        if len(part)>3: fr=attach(fr, bones(*part[3]), bones(d, anim), part[4])
        at=0; keep=[]
        for line in open(f'{d}/meshes.txt'):
            if line.startswith('#'): continue
            p=line.rstrip('\n').split('\t'); n=int(p[1])
            if p[2] not in drop: keep.append(np.arange(at,at+n)); lines.append(line.rstrip('\n'))
            at+=n
        k=np.concatenate(keep); verts.append(v[k]); frames.append(fr[:,k])
        for t in open(f'{d}/textures.txt'):
            name=t.split('\t')[0]
            if any(x.split('\t')[0]==name for x in texl): continue
            if not os.path.lexists(f'{out}/{name}.rgba'): os.symlink(os.path.abspath(f'{d}/{name}.rgba'),f'{out}/{name}.rgba')
            texl.append(t.rstrip('\n'))
    np.concatenate(verts).tofile(f'{out}/mesh.bin')
    open(f'{out}/meshes.txt','w').write('\n'.join(lines)+'\n')
    open(f'{out}/textures.txt','w').write('\n'.join(texl)+'\n')
    n=min(f.shape[0] for f in frames)
    np.concatenate([f[:n] for f in frames],axis=1).tofile(f'{out}/{anim_out}.frames')
    tex=os.path.join(os.path.dirname(out),'tex'+os.path.basename(out)[3:])
    if not os.path.lexists(tex): os.symlink(os.path.basename(out),tex)
    print(out, sum(len(x) for x in verts), 'vertices', n, 'frames')
if __name__=='__main__':
    merge('outPitH',[('outPit','c21_040_pith00',{'Face'}),('outPitS','c21_040_pith',set(),('outPit','c21_040_pith00'),'HeadN')],'c21_040')
    merge('outDPitH',[('outDPit','c21_040_bpith04',{'Face'}),('outDPitS','c21_040_bpith',set(),('outDPit','c21_040_bpith04'),'HeadN')],'c21_040')
    merge('outViriH',[('outViri','c11_030_natur',{'Effect'})],'c11_030')
