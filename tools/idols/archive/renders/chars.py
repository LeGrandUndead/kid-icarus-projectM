# Renders every frame of each mode's character animation, at a fixed
# framing per animation (so the feet stay put), into frames/<key>/NNN.png
import sys, os, math, numpy as np
sys.path.insert(0,'.')
import idol
from multiprocessing import Pool
JOBS=[  # key, idol, animation, yaw (degrees), rim colour, size
 ('solo','000','DolPit00Action00',-12,(1.0,0.55,0.7),1300),
 ('tog_pit','000','DolPit00Action00',35,(1.0,0.7,0.4),1050),
 ('tog_dark','009','DolBpit00Action00',-35,(0.75,0.4,1.0),1050),
 ('vault','002','DolPalu00Action00',-10,(0.55,1.0,0.6),1250),
 ('options','012','DolNatur00Action00',-10,(0.8,0.6,1.0),1250),
]
def framing(d,anim,yaw):
    v,_,_=idol.load(d); F=np.fromfile(f'{idol.S}/out{d}/{anim}.frames',dtype=np.float32).reshape(-1,len(v),6)
    R=idol.rot(math.radians(yaw),0); P=F[:,:,0:3].reshape(-1,3)@R.T
    lo,hi=P.min(0),P.max(0); span=max(hi[0]-lo[0],hi[1]-lo[1])*1.04
    return span,((lo[0]+hi[0])/2,(lo[1]+hi[1])/2,0),len(F),(hi[1]-lo[1])/span
def one(args):
    key,d,anim,yaw,rim,size,span,c,k=args
    out=f'frames/{key}/{k:03d}.png'
    if os.path.exists(out): return
    im=idol.render(d,size,math.radians(yaw),0,rim=rim,anim=anim,k=k,span_fix=(span,c))
    im.save(out)
if __name__=='__main__':
    tasks=[]
    for key,d,anim,yaw,rim,size in JOBS:
        os.makedirs(f'frames/{key}',exist_ok=True)
        span,c,n,fill=framing(d,anim,yaw)
        # `size` is now the character's height on screen
        sq=int(size/fill)
        tasks+= [(key,d,anim,yaw,rim,sq,span,c,k) for k in range(n)]
    print(len(tasks),'frames')
    with Pool(2) as p: p.map(one,tasks,chunksize=4)
