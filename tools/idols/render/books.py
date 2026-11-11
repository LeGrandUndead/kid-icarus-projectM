# the save select's 3D books, rendered with the idol renderer
import os; WORK=os.environ.get('IDOLS_WORK','work')  # the folder with the extracted models and renders
import sys, math, numpy as np
sys.path.insert(0,WORK+'/render')
import idol
D=WORK+'/idols'
BOOKMESH={1:'BookMT2',2:'BookMT',3:'BookMT1'}
def loader(b):
    def load(_):
        out=f'{D}/outbook{b}'; tex=f'{D}/texbook1'
        v=np.fromfile(f'{out}/mesh.bin',dtype=np.float32).reshape(-1,16)
        groups=[]; at=0
        for line in open(f'{out}/meshes.txt'):
            if line.startswith('#'): continue
            p=line.rstrip('\n').split('\t'); n=int(p[1])
            groups.append(dict(t0=p[0],t1=p[5],t2=p[6],maps=p[7],name=p[2],layer=0 if p[2]==BOOKMESH[b] else 2,start=at,count=n,test=None,blend=False)); at+=n
        texs={}
        for line in open(f'{tex}/textures.txt'):
            nm,w,h=line.split('\t'); w,h=int(w),int(h)
            texs[nm]=np.fromfile(f'{tex}/{nm}.rgba',dtype=np.uint8).reshape(h,w,4).astype(np.float32)/255
        return v,groups,texs
    return load
def render(b,size,yaw,pitch,anim,k,rim=(1,0.85,0.5)):
    idol.load=loader(b)
    n=len(idol.load(0)[0])
    F=np.fromfile(f'{D}/outbook{b}/MenSelfileBt000{b-1}__{anim}.frames',dtype=np.float32).reshape(-1,n,6)
    idol.frame=lambda i,a,kk: F[kk]
    return idol.render('book',size,math.radians(yaw),math.radians(pitch),rim=rim,anim='x',k=k)
