# Together / Vault / Options: the cutscene characters (heads on bodies),
# an idle (slow-motion or the character's own idle), then on click the
# move plays. 60 fps. Writes frames/<mode>/NNNN.png and frames/<mode>.json.
import sys, os, math, json
sys.path.insert(0,'.')
import numpy as np, idol
from multiprocessing import Pool
B=1150; CLICK=150
MODES={
 # key, yaw, pitch, rim colour, idle spec, action spec, end
 'together':dict(room=1.45,key='T05',yaw=25,pitch=5,rim=(1.0,0.78,0.35),idle=('clip',5,0.08),act=('clip',17,1.15),end=CLICK+110,wipe=CLICK+62),
 'vault':dict(key='P20',yaw=20,pitch=3,rim=(0.55,0.95,1.0),idle=('idle',0,1.0),act=('clip',20,1.25),end=CLICK+120,wipe=CLICK+78),
 'options':dict(key='V11',yaw=300,pitch=-20,rim=(0.6,1.0,0.5),idle=('clip',30,0.25),act=('clip',67,1.3),end=CLICK+110,wipe=CLICK+66),
}
F={}
def clip(key,a):
    if (key,a) not in F:
        v=len(idol.load(key)[0]); F[key,a]=np.fromfile(f'{idol.S}/out{key}/{a}.frames',dtype=np.float32).reshape(-1,v,6)
    return F[key,a]
def at(key,a,x,shift=None):
    c=clip(key,a); x=min(max(x,0),len(c)-1.001); i=int(x); w=x-i
    p=c[i]*(1-w)+c[min(i+1,len(c)-1)]*w
    if shift is not None: p=p.copy(); p[:,:3]+=shift
    return p
def plan(m):
    M=MODES[m]; key=M['key']; out=[]
    shift=None
    if M['idle'][0]!=M['act'][0]:      # a different take: put the move where the idle ends
        a=clip(key,M['idle'][0])[min(len(clip(key,M['idle'][0]))-1,int(M['idle'][1]+CLICK*M['idle'][2]))]
        b=clip(key,M['act'][0])[M['act'][1]]
        shift=a[:,:3].mean(0)-b[:,:3].mean(0)
    for f in range(M['end']):
        if f<CLICK: spec=[(M['idle'][0],M['idle'][1]+f*M['idle'][2],1.0,None)]
        else:
            g=f-CLICK; ramp=min(1,g/12)                       # speeds up into the move
            x=M['act'][1]+sum(M['idle'][2]+(M['act'][2]-M['idle'][2])*min(1,h/12) for h in range(g))
            spec=[(M['act'][0],x,1.0,shift)]
            if M['idle'][0]!=M['act'][0] and g<8:
                spec=[(M['idle'][0],M['idle'][1]+CLICK*M['idle'][2],1-g/8,None),(M['act'][0],M['act'][1]+g*0.5,g/8,shift)]
        out.append(dict(f=f,spec=spec))
    return out
def pose(key,spec):
    p=None
    for a,x,w,sh in spec:
        q=at(key,a,x,None if sh is None else np.array(sh))*w
        p=q if p is None else p+q
    n=p[:,3:6]; p[:,3:6]=n/np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-6); return p
def framing(m,T):
    M=MODES[m]; R=idol.rot(math.radians(M['yaw']),math.radians(M['pitch']))
    pts=[]
    for e in T[:CLICK+40:10]:
        P=pose(M['key'],e['spec'])[:,:3]@R.T; pts.append(P[np.isfinite(P).all(1)])
    P=np.concatenate(pts); lo,hi=np.percentile(P,0.5,axis=0),np.percentile(P,99.5,axis=0)
    return float(max(hi[0]-lo[0],hi[1]-lo[1])*M.get('room',1.18)), ((lo+hi)/2).tolist()
def one(job):
    m,e,fr=job; M=MODES[m]
    out=f'frames/{m}/{e["f"]:04d}.png'
    if os.path.exists(out): return
    spec=[(a,x,w,None if s is None else np.array(s)) for a,x,w,s in e['spec']]
    idol.render(M['key'],B,math.radians(M['yaw']),math.radians(M['pitch']),rim=M['rim'],pose=pose(M['key'],spec),span_fix=(fr[0],tuple(fr[1])),ss=2).save(out)
if __name__=='__main__':
    jobs=[]
    for m in sys.argv[1:]:
        os.makedirs(f'frames/{m}',exist_ok=True)
        T=plan(m)
        for e in T: e['spec']=[(a,x,w,None if s is None else [float(v) for v in s]) for a,x,w,s in e['spec']]
        fr=framing(m,[dict(f=e['f'],spec=[(a,x,w,None if s is None else np.array(s)) for a,x,w,s in e['spec']]) for e in T])
        json.dump(dict(timeline=T,click=CLICK,wipe=MODES[m]['wipe'],end=MODES[m]['end'],framing=fr),open(f'frames/{m}.json','w'))
        jobs+=[(m,e,fr) for e in T]
    with Pool(2) as p: p.map(one,jobs,chunksize=1)
    print('ok',len(jobs))
