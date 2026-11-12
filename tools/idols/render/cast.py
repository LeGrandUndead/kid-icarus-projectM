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
 'together':dict(key='T05',yaw=-45,pitch=5,rim=(1.0,0.85,0.65),idle=('clash',4,8/150),act=('clash',12,1.0),end=CLICK+110,wipe=CLICK+64,close=True),
 'vault':dict(key='P20',yaw=20,pitch=3,rim=(0.8,1.0,0.95),idle=('idle',0,1.0),act=('clip',20,1.25),end=CLICK+120,wipe=CLICK+78),
 # Options: Viridi's idol (full body), her Wait, then her Action00
 'options':dict(key='V12',yaw=-20,pitch=3,rim=(1.0,0.82,0.92),idle=('DolNatur00Wait',0,1.0),act=('DolNatur00Action00',0,1.0),end=CLICK+110,wipe=CLICK+66),
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
def robust(P):
    c0=np.median(P,0); d=np.linalg.norm(P-c0,axis=1); return P[d<np.percentile(d,97)*1.2]
def close_framing(m,T):
    # close: the heads and arms during the clash; after the click the camera
    # pulls back to twice that, following the two of them
    M=MODES[m]; R=idol.rot(math.radians(M['yaw']),math.radians(M['pitch']))
    sp=lambda e:[(a,x,w,None if s is None else np.array(s)) for a,x,w,s in e['spec']]
    P=robust(pose(M['key'],sp(T[75]))[:,:3]@R.T); lo,hi=P.min(0),P.max(0); h=hi[1]-lo[1]
    top=P[P[:,1]>hi[1]-0.42*h]; tl,th=top.min(0),top.max(0)
    span=float(max(th[0]-tl[0],th[1]-tl[1])*1.02)
    close=[float((tl[0]+th[0])/2),float((tl[1]+th[1])/2-0.03*h),0.0]
    centres={}
    for e in T[CLICK:]:
        Q=robust(pose(M['key'],sp(e))[:,:3]@R.T); centres[e['f']]=[float(v) for v in np.median(Q,0)]
    return dict(span=span,close=close,centres=centres)
def frame_at(m,f,fr):
    M=MODES[m]
    if not M.get('close'): return fr
    k=min(1,max(0,(f-CLICK-6)/50)); k=k*k*(3-2*k)
    c=fr['centres'].get(str(f),fr['centres'].get(f,fr['close']))
    # the camera eases from the clash toward the middle of the fight, a little behind it
    cen=[fr['close'][i]+(c[i]-fr['close'][i])*k*0.85 for i in range(3)]
    return (fr['span']*(1+1.1*k),cen)
def one(job):
    m,e,fr=job; M=MODES[m]
    out=f'frames/{m}/{e["f"]:04d}.png'
    if os.path.exists(out): return
    spec=[(a,x,w,None if s is None else np.array(s)) for a,x,w,s in e['spec']]
    fr=frame_at(m,e['f'],fr)
    # cutscene-style shading: side key, shadows tinted with the mode's colour, rim
    idol.POST=dict(rim=M['rim'],light=(-0.85,0.45,0.28),dark=0.55,rim_strength=0.8,
                   shadow={'together':(0.75,0.6,1.0),'vault':(0.7,0.85,1.0),'options':(0.95,0.7,0.95)}[m])
    idol.render(M['key'],B,math.radians(M['yaw']),math.radians(M['pitch']),rim=M['rim'],pose=pose(M['key'],spec),span_fix=(fr[0],tuple(fr[1])),ss=2).save(out)
if __name__=='__main__':
    jobs=[]
    for m in sys.argv[1:]:
        os.makedirs(f'frames/{m}',exist_ok=True)
        T=plan(m)
        for e in T: e['spec']=[(a,x,w,None if s is None else [float(v) for v in s]) for a,x,w,s in e['spec']]
        fr=close_framing(m,T) if MODES[m].get('close') else framing(m,[dict(f=e['f'],spec=[(a,x,w,None if s is None else np.array(s)) for a,x,w,s in e['spec']]) for e in T])
        json.dump(dict(timeline=T,click=CLICK,wipe=MODES[m]['wipe'],end=MODES[m]['end'],framing=fr),open(f'frames/{m}.json','w'))
        jobs+=[(m,e,fr) for e in T]
    with Pool(2) as p: p.map(one,jobs,chunksize=1)
    print('ok',len(jobs))
