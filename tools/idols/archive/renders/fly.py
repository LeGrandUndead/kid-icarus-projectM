# Pit gliding (his flight animation, ChrPit00AirGrideFlap1, looped), turning
# to head toward the pointer; on click he turns to the camera and flies at
# it. Writes a timeline (fly.json) and Pit's frames (frames/fly/NNNN.png),
# 60 frames a second (the animation's own rate: one keyframe a frame).
import sys, os, math, json
sys.path.insert(0,'.')
import numpy as np, idol
from multiprocessing import Pool
A='ChrPit00AirGrideFlap1'
W,H=1920,1080; FPS=60
B=1100                      # Pit's square on screen, in pixels, before the dive
PIT=(0.68*W,0.47*H)         # where he hovers
SOLO=(18*H/240+120,22*H/240+70)
def ease(t): t=max(0,min(1,t)); return t*t*(3-2*t)
PATH=[(0,(W*0.95,H*0.85)),(70,(W*0.86,H*0.22)),(140,(W*0.40,H*0.18)),(200,(W*0.50,H*0.80)),(260,SOLO)]
def pointer(f):
    for (f0,a),(f1,b) in zip(PATH,PATH[1:]):
        if f<=f1:
            k=ease((f-f0)/(f1-f0)); return (a[0]+(b[0]-a[0])*k,a[1]+(b[1]-a[1])*k)
    return PATH[-1][1]
CLICK=285; TURN=14; DIVE=36; END=CLICK+TURN+DIVE+40
def timeline():
    out=[]; yaw,pitch=55.0,10.0; vy=vp=0.0; anim=0.0
    for f in range(END):
        px,py=pointer(f)
        if f<CLICK:
            dx,dy=px-PIT[0],py-PIT[1]
            wy=max(-80,min(80,math.degrees(math.atan2(dx,700))*1.4))
            wp=max(-25,min(25,dy/H*60))
            speed=1.0
        else:
            wy,wp=0.0,8.0; speed=1.6
        # a soft spring, so he swings round rather than snapping
        k,d=(0.010,0.16) if f<CLICK else (0.05,0.35)
        vy+=(wy-yaw)*k-vy*d; yaw+=vy; vp+=(wp-pitch)*k-vp*d; pitch+=vp
        anim=(anim+speed)%90
        g=f-CLICK-TURN
        z=1.0 if g<0 else math.exp(ease(g/DIVE)**1.6*math.log(14))   # he comes at the camera
        bob=0 if f>=CLICK else math.sin(f/FPS*2*math.pi/1.5)*10
        cx=PIT[0]+(W/2-PIT[0])*ease(max(0,f-CLICK)/(TURN+DIVE*0.6)); cy=PIT[1]+bob+(H*0.5-PIT[1])*ease(max(0,f-CLICK)/(TURN+DIVE*0.6))
        out.append(dict(f=f,pointer=(px,py),yaw=yaw,pitch=pitch,k=anim,z=z,at=(cx,cy)))
    return out
# framing: turn about his centre, and a span that fits him at any angle
F=idol.FRAMES.get(('000',A))
def setup():
    v,_,_=idol.load('000')
    fr=np.fromfile(f'{idol.S}/out000/{A}.frames',dtype=np.float32).reshape(-1,len(v),6)
    P=fr[:,:,0:3].reshape(-1,3); P=P[np.isfinite(P).all(1)]
    centre=P.mean(0); radius=np.percentile(np.linalg.norm(P-centre,axis=1),99.8)
    return centre,radius*2.0
CENTRE,SPAN=setup()
def one(e):
    out=f'frames/fly/{e["f"]:04d}.png'
    if os.path.exists(out): return
    R=idol.rot(math.radians(e['yaw']),math.radians(e['pitch'])); c=R@CENTRE
    k=int(e['k'])
    px=B*e['z']; n=int(min(px,2200)); span=SPAN*n/px
    im=idol.render('000',n,math.radians(e['yaw']),math.radians(e['pitch']),rim=(1.0,0.55,0.7),anim=A,k=k,span_fix=(span,tuple(c)),ss=2 if n<=1200 else 1)
    im.save(out)
if __name__=='__main__':
    os.makedirs('frames/fly',exist_ok=True)
    T=timeline(); json.dump(dict(timeline=T,click=CLICK,turn=TURN,dive=DIVE,B=B),open('frames/fly.json','w'))
    if len(sys.argv)>1: T=[T[int(x)] for x in sys.argv[1:]]
    with Pool(2) as p: p.map(one,T,chunksize=1)
    print('ok',len(T))
