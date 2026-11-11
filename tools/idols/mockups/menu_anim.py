# The main menu in motion: each mode's idol plays its move; rays turn, motes
# drift, the vine's selection follows; modes cross-fade. Writes frames for ffmpeg.
exec(open('mk.py').read())
exec(open('vine.py').read())
import random, sys
R='/tmp/claude-0/-home-claude/0846ad66-37b8-5f7e-bbd2-eb4c158aa498/scratchpad/render/frames'
INK=(16,10,12)
atlas,_=art('040','MenTopBt_Lang0002')
A=np.asarray(atlas); lab,_=ndimage.label(A[:,:,3]>10); objs=ndimage.find_objects(lab); kA=atlas.width/256
def button(r,rot=0):
    x0,y0,x1,y1=[v*kA for v in r]; keep=np.zeros(lab.shape,bool)
    for i,o in enumerate(objs):
        cy=(o[0].start+o[0].stop)/2; cx=(o[1].start+o[1].stop)/2
        if x0<=cx<x1 and y0<=cy<y1: keep|=lab==i+1
    B=A.copy(); B[~keep,3]=0; p=Image.fromarray(B).crop((int(x0),int(y0),int(x1),int(y1)))
    return p.rotate(-90,expand=True) if rot else p
heads,_=art('040','MenTopUp_Lang0000')
MODES=[
 dict(name='Solo',color=(224,120,150),emb=('040','MenCmnBgUp0007Sg'),head=(0.0,0.185),cap='The story of Pit, our angelic hero.',chars=[('solo',0.70,0.93)]),
 dict(name='Together',color=(232,140,70),emb=('040','MenCmnBgUp0002Ml'),head=(0.19,0.386),cap='Battle it out wirelessly with others!',chars=[('tog_pit',0.55,0.93),('tog_dark',0.80,0.93)]),
 dict(name='Vault',color=(96,176,104),emb=('040','MenCmnBgUp0007Cl'),head=(0.588,0.785),cap="View content you've unlocked.",chars=[('vault',0.70,0.93)]),
 dict(name='Options',color=(160,112,206),emb=('040','MenCmnBgUp0007Op'),head=(0.79,0.985),cap='Adjust settings to your liking.',chars=[('options',0.70,0.93)]),
]
def background(m,i):
    c=m['color']; page=paper(seed=i+2)
    yy,xx=np.mgrid[0:H,0:W]; t=np.clip((xx/W-0.25)*1.2,0,1)*0.42
    wash=Image.new('RGBA',(W,H),c+(0,)); wash.putalpha(Image.fromarray((t*255).astype(np.uint8))); page.alpha_composite(wash)
    return page
def rays_layer():
    layer=Image.new('RGBA',(1500,1500)); rays(layer,750,750,(255,250,235),0.85,n=20,spread=0.62); return layer
def emblem(m):
    e,_=art(*m['emb']); return fit(mask(e,m['color'],0.55),h=1100)
def header(m):
    lay=Image.new('RGBA',(W,H))
    hm=mask(heads,INK); y0,y1=m['head']; hd=hm.crop((0,int(y0*hm.height),hm.width,int(y1*hm.height))); hd=fit(hd.crop(hd.getbbox()),h=96)
    put(lay,hd,W*0.415,110,anchor='c',sh=(6,0.25,4,6))
    fl,_=art('040','MenTopUp0000'); fl=fit(mask(fl,(255,255,255)),w=380)
    a=np.asarray(fl).copy(); g=np.linspace(0,1,a.shape[1])[None,:]
    a[:,:,0]=(220*(1-g)+60*g); a[:,:,1]=(60*(1-g)+200*g); a[:,:,2]=(220*(1-g)+230*g)
    put(lay,Image.fromarray(a.astype(np.uint8)),W*0.415,200,anchor='c')
    text(lay,(W*0.415,262),m['cap'],font(SANS,30,700),INK+(235,),anchor='mm')
    return lay
ITEMS=[((1,1,193,86),0,(18,22),-2,0),((1,91,184,180),0,(26,74),2,1),((0,182,118,255),0,(18,128),-1.5,2),((203,1,255,174),1,(26,176),1.5,3)]
BTN=[button(r,rot) for r,rot,_,_,_ in ITEMS]
UI_CACHE={}
def ui(sel,t):
    key=(sel,round(t*10))
    if key in UI_CACHE: return UI_CACHE[key]
    if len(UI_CACHE)>8: UI_CACHE.clear()
    UI_CACHE[key]=ui_(sel,t); return UI_CACHE[key]
def ui_(sel,t):
    lay=Image.new('RGBA',(W,H)); s=0.46; rects=[]; placed=[]
    for (r,rot,(x,y),ang,node),p in zip(ITEMS,BTN):
        dy=math.sin(t*1.3+node*2.1)*1.2; dx=math.sin(t*0.9+node*1.7)*0.7
        w,h=p.width/kA*s,p.height/kA*s; rects.append((x+dx,y+dy,x+dx+w,y+dy+h)); placed.append((p,x+dx,y+dy,w,h,ang,node))
    big=Image.new('L',(W*2,H*2),0); d=ImageDraw.Draw(big)
    for poly in vine(rects): d.polygon([(px*U*2,py*U*2) for px,py in poly],fill=255)
    mv=big.resize((W,H),Image.LANCZOS)
    sh=Image.new('RGBA',(W,H)); sh.putalpha(mv.filter(ImageFilter.GaussianBlur(5)).point(lambda v:v*0.3)); lay.alpha_composite(sh,(5,8))
    blk=Image.new('RGBA',(W,H),(10,6,8,255)); blk.putalpha(mv); lay.alpha_composite(blk)
    for p,x,y,w,h,ang,node in placed:
        on=node==sel; k=1.07 if on else 1
        put(lay,fit(p,w=w*U*k),x*U+w*U/2,y*U+h*U/2,anchor='c',sh=(6,0.5,6,9),gl=(11,12,(255,208,84),0.75+0.25*math.sin(t*4)) if on else None,rot=ang)
    return lay
def controls():
    # the menu controls: one compact panel, every hint clickable
    lay=Image.new('RGBA',(W,H)); d=ImageDraw.Draw(lay)
    fk=ImageFont.truetype('DejaVuSans-Bold.ttf',22); fw=font(SANS,26,700)
    items=[('▲ ▼','Choose'),('Enter','Select'),('Esc','Back')]
    widths=[max(d.textlength(k,font=fk)+20,36)+10+d.textlength(w_,font=fw) for k,w_ in items]
    total=sum(widths)+28*(len(items)-1)+44
    x0,y0=W-40-total,H-40-58
    d.rounded_rectangle((x0,y0,x0+total,y0+58),radius=29,fill=(20,14,16,200))
    x=x0+22
    for (k,w_),wd in zip(items,widths):
        kw=max(d.textlength(k,font=fk)+20,36)
        d.rounded_rectangle((x,y0+11,x+kw,y0+47),radius=8,outline=(240,232,214,255),width=2)
        d.text((x+kw/2,y0+29),k,font=fk,fill=(240,232,214,255),anchor='mm')
        d.text((x+kw+10,y0+30),w_,font=fw,fill=(240,232,214,255),anchor='lm')
        x+=wd+28
    return lay
def motes(page,m,t,seed):
    rng=random.Random(seed); lay=Image.new('RGBA',(W,H)); d=ImageDraw.Draw(lay)
    for k in range(46):
        x0=rng.uniform(0.38,1.0)*W; sp=rng.uniform(18,60); ph=rng.uniform(0,1); r=rng.uniform(2.5,7)
        y=H-((t*sp+ph*H*1.2)%(H*1.2))+40; x=x0+math.sin(t*0.8+k)*18
        a=int(150*min(1,(H-y)/300)*min(1,y/200)) if 0<y<H else 0
        if a<=0: continue
        col=tuple(int(c*0.6+255*0.4) for c in m['color'])
        d.ellipse((x-r*2.6,y-r*2.6,x+r*2.6,y+r*2.6),fill=col+(int(a*0.5),))
        d.ellipse((x-r*0.8,y-r*0.8,x+r*0.8,y+r*0.8),fill=(255,252,240,a))
    page.alpha_composite(lay.filter(ImageFilter.GaussianBlur(3.0)))
SHADOWS={}
def char_frame(key,k):
    fs=sorted(os.listdir(f'{R}/{key}')); return Image.open(f'{R}/{key}/{fs[k%len(fs)]}').convert('RGBA'), len(fs)
if __name__=='__main__':
    out='anim'; os.makedirs(out,exist_ok=True)
    RAYS=rays_layer(); CTRL=controls()
    only=int(sys.argv[1]) if len(sys.argv)>2 else None
    static=[(background(m,i),emblem(m),header(m)) if only is None or only==i else None for i,m in enumerate(MODES)]
    FPS=30; SEG=96; FADE=10
    def scene(i,f):
        m=MODES[i]; bg,em,hd=static[i]; t=f/FPS
        page=bg.copy()
        s=1+0.015*math.sin(t*0.7); e=em.resize((int(em.width*s),int(em.height*s)))
        put(page,e,W*0.74,H*0.5,anchor='c')
        r=RAYS.rotate(t*6,resample=Image.BILINEAR).crop((int(750-W*0.35),int(750-H*0.225),int(750-W*0.35)+W//2,int(750-H*0.225)+H//2)).resize((W,H),Image.BILINEAR)
        page.alpha_composite(r)
        motes(page,m,t,i)
        for key,cx,base in m['chars']:
            im,n=char_frame(key,f)
            # a soft shadow on the ground
            sk=(key,im.width)
            if sk not in SHADOWS:
                w_=int(im.width*0.4)+80; sh=Image.new('RGBA',(w_,128)); ImageDraw.Draw(sh).ellipse((40,40,w_-40,88),fill=(30,16,20,110))
                SHADOWS[sk]=sh.filter(ImageFilter.GaussianBlur(14))
            sh=SHADOWS[sk]; page.alpha_composite(sh,(int(cx*W-sh.width/2),int(base*H-64)))
            page.alpha_composite(im,(int(cx*W-im.width/2),int(base*H-im.height)))
        page.alpha_composite(hd)
        page.alpha_composite(ui(i,t))
        page.alpha_composite(CTRL)
        return page
    if len(sys.argv)>2:
        scene(int(sys.argv[1]),int(sys.argv[2])).convert('RGB').save('anim_test.png'); sys.exit()
    n=0
    for i in range(len(MODES)):
        for f in range(SEG):
            img=scene(i,f)
            if f<FADE and i>0:
                prev=scene(i-1,SEG+f); img=Image.blend(prev,img,f/FADE)
            img.convert('RGB').save(f'{out}/{n:04d}.png'); n+=1
    print(n,'frames')
