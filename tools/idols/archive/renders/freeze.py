# Pit frozen mid-leap (idol Action00, frame 18 of the step-2 export), turning
# to follow the pointer; then the move resumes from there.
import sys, os, math, json
sys.path.insert(0,'.')
import idol, chars
from multiprocessing import Pool
span,c,n,fill=chars.framing('000','DolPit00Action00',-12)
SQ=int(1300/fill); FREEZE=18
YAWS=[y/2 for y in range(-110,41,5)]   # -55 .. +20, 2.5 degree steps
def ease(t): return t*t*(3-2*t)
def resume_yaw(i, start): return start+(-12-start)*ease(min(1,i/15))
os.makedirs('frames/freeze',exist_ok=True); os.makedirs('frames/resume',exist_ok=True)
def one(job):
    kind,a,b=job
    if kind=='f':
        out=f'frames/freeze/{a:+06.1f}.png'
        if not os.path.exists(out): idol.render('000',SQ,math.radians(a),0,rim=(1.0,0.55,0.7),anim='DolPit00Action00',k=FREEZE,span_fix=(span,c)).save(out)
    else:
        out=f'frames/resume/{a:03d}.png'
        if not os.path.exists(out): idol.render('000',SQ,math.radians(b),0,rim=(1.0,0.55,0.7),anim='DolPit00Action00',k=a,span_fix=(span,c)).save(out)
if __name__=='__main__':
    start=float(sys.argv[1]) if len(sys.argv)>1 else -50
    jobs=[('f',y,0) for y in YAWS]+[('r',k,resume_yaw(k-FREEZE,start)) for k in range(FREEZE,100)]
    json.dump({'yaws':YAWS,'start':start},open('frames/freeze.json','w'))
    with Pool(2) as p: p.map(one,jobs)
    print('ok')
