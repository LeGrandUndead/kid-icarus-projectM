# Solo in the sky (60 fps): Pit glides with personality. His moves are the
# game's own: he banks into turns (AirGrideL/R), glances back at the
# pointer (AirGrideLookB), does a barrel roll when Solo is hovered
# (AirRollingGrideLA), and on click whips round and barrel-rolls past the
# camera (AirRollingGrideRA). Moves cross-fade over a few frames.
# Writes the timeline (frames/sky.json) and Pit's frames (frames/sky/NNNN.png).
import sys, os, math, json
sys.path.insert(0,'.')
import numpy as np, idol
from multiprocessing import Pool
P='ChrPit00'
MODEL='PitHF'    # the cutscene Pit (high detail head) on his gameplay flight moves
W,H=1920,1080; FPS=60
B=1000; PIT=(0.66*W,0.50*H)
SOLO=(18*H/240+120,22*H/240+70)
def ease(t): t=max(0,min(1,t)); return t*t*(3-2*t)
def ease_in(t): t=max(0,min(1,t)); return t*t*t
PATH=[(0,(W*0.97,H*0.86)),(60,(W*0.90,H*0.24)),(130,(W*0.47,H*0.30)),(160,(W*0.60,H*0.42)),(215,(W*0.42,H*0.70)),(285,SOLO)]
def pointer(f):
    for (f0,a),(f1,b) in zip(PATH,PATH[1:]):
        if f<=f1:
            k=ease((f-f0)/(f1-f0)); return (a[0]+(b[0]-a[0])*k,a[1]+(b[1]-a[1])*k)
    return PATH[-1][1]
CLICK=372; PASS=34; END=CLICK+PASS+36
# (start frame, move, speed): each one-shot fades back into the glide loop
ACTS=[(8,'AirGrideR',1.0),(78,'AirGrideL',1.0),(150,'AirGrideLookB',1.1),(288,'AirRollingGrideLA',1.0),(CLICK+3,'AirRollingGRIDE_PASS',1.25)]
LOOP='AirGrideFlap1'; FADE=10
N={}
def clip(a):
    if a not in N: N[a]=np.fromfile(f'{idol.S}/out{MODEL}/{P}{a}.frames',dtype=np.float32).reshape(-1,len(idol.load(MODEL)[0]),6)
    return N[a]
def pose(f):
    loop=clip(LOOP)
    base=loop[int(f)%len(loop)]
    out=base; 
    for s,a,sp in ACTS:
        a='AirRollingGrideRA' if a=='AirRollingGRIDE_PASS' else a
        c=clip(a); t=(f-s)*sp
        if t<0 or t>=len(c)-1+FADE: continue
        w=min(1,(t+1)/FADE)*min(1,(len(c)-1+FADE-t)/FADE)
        if a=='AirRollingGrideRA': w=min(1,(t+1)/4)    # the pass: straight in, held to the end
        k=min(len(c)-1,int(t)); out=out*(1-w)+c[k]*w
    out=out.copy(); n=out[:,3:6]; out[:,3:6]=n/np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-6)
    return out
def timeline():
    out=[]; yaw,pitch=50.0,8.0; vy=vp=0.0
    for f in range(END):
        px,py=pointer(f); g=f-CLICK
        if g<0:
            # he flies his own way, not after the pointer: slow swings of heading
            wy=-28+30*math.sin(2*math.pi*f/330)+8*math.sin(2*math.pi*f/127); wp=7+6*math.sin(2*math.pi*f/240)
            k,d=0.012,0.17
        else:
            wy,wp=-25.0,18.0; k,d=0.06,0.38        # whips round toward the camera, heading down-left past it
        vy+=(wy-yaw)*k-vy*d; yaw+=vy; vp+=(wp-pitch)*k-vp*d; pitch+=vp
        bank=max(-35,min(35,-vy*14)) if g<0 else 0.0   # leans into turns
        z=1.0; at=(PIT[0],PIT[1]+math.sin(f/FPS*2*math.pi/1.5)*9)
        if g>=6:
            t=(g-6)/PASS; z=math.exp(ease_in(t)*math.log(11))
            at=(PIT[0]+(-0.45*W)*ease_in(t)**0.8, PIT[1]+(0.62*H)*ease_in(t))   # past the lens, lower left
        out.append(dict(f=f,pointer=(px,py),yaw=yaw,pitch=pitch,bank=bank,z=z,at=at,hover=pointer(f)==SOLO))
    return out
def setup():
    v,_,_=idol.load(MODEL); Pp=clip(LOOP)[:,:,0:3].reshape(-1,3)
    c=Pp.mean(0); r=np.percentile(np.linalg.norm(Pp-c,axis=1),99.8)
    return c,r*2.0
CENTRE,SPAN=setup()
def one(e):
    out=f'frames/sky/{e["f"]:04d}.png'
    if os.path.exists(out): return
    R=idol.rot(math.radians(e['yaw']),math.radians(e['pitch']),math.radians(e['bank'])); c=R@CENTRE
    px=B*e['z']; n=int(min(px,2300)); span=SPAN*n/px
    idol.render(MODEL,n,math.radians(e['yaw']),math.radians(e['pitch']),rim=(1.0,0.55,0.7),bank=math.radians(e['bank']),
                pose=pose(e['f']),span_fix=(span,tuple(c)),ss=2 if n<=1200 else 1).save(out)
if __name__=='__main__':
    os.makedirs('frames/sky',exist_ok=True)
    T=timeline(); json.dump(dict(timeline=T,click=CLICK,passing=PASS,B=B),open('frames/sky.json','w'))
    if len(sys.argv)>1: T=[T[int(x)] for x in sys.argv[1:]]
    with Pool(2) as p: p.map(one,T,chunksize=1)
    print('ok',len(T))
