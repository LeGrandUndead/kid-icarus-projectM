import sys, math
sys.path.insert(0,'.')
import idol
from PIL import Image, ImageDraw
from multiprocessing import Pool
ANIM=sys.argv[1] if sys.argv[1:2] and not sys.argv[1].isupper() else 'scene'
def one(a):
    key,k=a
    try: return idol.render(key,240,math.radians(20),math.radians(5),rim=(1,.75,.55),anim=ANIM,k=k,ss=1)
    except Exception as e: return None
if __name__=='__main__':
    for key in [a for a in sys.argv[1:] if a.isupper() or a[0].isupper()]:
        import numpy as np
        n=len(np.fromfile(f'{idol.S}/out{key}/{ANIM}.frames',dtype=np.float32))//(6*len(idol.load(key)[0]))
        with Pool(2) as p: ims=p.map(one,[(key,k) for k in range(min(40,n))])
        s=Image.new('RGB',(8*240,5*262),(36,28,34)); d=ImageDraw.Draw(s)
        for k,im in enumerate(ims):
            x,y=(k%8)*240,(k//8)*262
            if im: s.paste(im,(x,y),im)
            d.text((x+4,y+244),f'{key} #{k}',fill=(255,230,170))
        s.save(f'../sheet_{key}_{ANIM}.png'); print(key)
