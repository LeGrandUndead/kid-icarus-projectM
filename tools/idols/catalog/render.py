import os; WORK=os.environ.get('IDOLS_WORK','work')  # the folder with the extracted models and renders
import sys, os, json, math, numpy as np
sys.path.insert(0,WORK+'/render')
import idol
from multiprocessing import Pool
entries=json.load(open('entries.json'))
def job(i):
    label,d,an,src,n=entries[i]
    os.makedirs(f'cells/{i:03d}',exist_ok=True)
    if os.path.exists(f'cells/{i:03d}/023.png') or os.path.exists(f'cells/{i:03d}/done'): return
    try:
        v,_,_=idol.load(d)
        F=np.fromfile(f'{idol.S}/out{d}/{an}.frames',dtype=np.float32).reshape(-1,len(v),6)
        R=idol.rot(math.radians(-20),0); P=F[:,:,0:3].reshape(-1,3)@R.T
        P=P[np.isfinite(P).all(1)]
        lo,hi=P.min(0),P.max(0); span=max(hi[0]-lo[0],hi[1]-lo[1])*1.06; c=((lo[0]+hi[0])/2,(lo[1]+hi[1])/2,0)
        idol.FRAMES[(d,an)]=F
        for k in range(len(F)):
            idol.render(d,240,math.radians(-20),0,rim=(1,0.8,0.5),anim=an,k=k,span_fix=(span,c),ss=1).save(f'cells/{i:03d}/{k:03d}.png')
    except Exception as e:
        open(f'cells/{i:03d}/error.txt','w').write(repr(e))
    open(f'cells/{i:03d}/done','w').close()
if __name__=='__main__':
    with Pool(2) as p: p.map(job,range(len(entries)),chunksize=1)
    print('rendered')
