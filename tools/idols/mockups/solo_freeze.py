# Frozen pose -> Pit turns to follow the pointer -> click -> the move resumes
# while he turns back to the camera -> a quick zoom-through into the Solo hall.
lib={'__name__':'lib'}; exec(open('menu_anim.py').read(),lib)
g=globals(); g.update({k:v for k,v in lib.items() if not k.startswith('__')})
m=MODES[0]; bg,em,hd=background(m,0),emblem(m),header(m); RAYS=rays_layer(); CTRL=controls()
hall=Image.open('/mnt/user-data/uploads/Kid icarus/build/menu-captures/20261109-222311/004-030-auto-upper.png').convert('RGBA')
hall=hall.resize((W,int(hall.height*W/hall.width)),Image.LANCZOS).crop((0,0,W,H))
K=0.76; FEET=1312
def small(im): return im.resize((int(im.width*K),int(im.height*K)),Image.LANCZOS)
FZ={}
def frozen(yaw):
    y=max(-50,min(20,round(yaw/2.5)*2.5))
    if y not in FZ: FZ[y]=small(Image.open(f'{R}/freeze/{y:+06.1f}.png').convert('RGBA'))
    return FZ[y]
RES={}
def resumed(k):
    if k not in RES: RES[k]=small(Image.open(f'{R}/resume/{k:03d}.png').convert('RGBA'))
    return RES[k]
def cursor(page,x,y,down):
    s=1.3*(0.9 if down else 1.0)
    pts=[(0,0),(0,34),(9,26),(15,40),(21,37),(15,24),(27,24)]
    d=ImageDraw.Draw(page); d.polygon([(x+px*s,y+py*s) for px,py in pts],fill=(255,255,255,255),outline=(0,0,0,255),width=3)
def ease(t): t=max(0,min(1,t)); return t*t*(3-2*t)
# the pointer's path: in from the right, past Pit, around, then onto Solo
PATH=[(0,(W*0.92,H*0.80)),(25,(W*0.88,H*0.40)),(50,(W*0.52,H*0.30)),(70,(W*0.58,H*0.72)),(95,(18*U+120,22*U+70))]
def pointer(f):
    for (f0,a),(f1,b) in zip(PATH,PATH[1:]):
        if f<=f1:
            k=ease((f-f0)/(f1-f0)); return (a[0]+(b[0]-a[0])*k,a[1]+(b[1]-a[1])*k)
    return PATH[-1][1]
PX=0.70*W
CLICK=105; ZOOM=CLICK+30; ZN=12; END=ZOOM+ZN+24
yaw=-12.0; SHADOW=None
out='freeze_frames'; os.makedirs(out,exist_ok=True)
for old in os.listdir(out): os.remove(f'{out}/{old}')
for f in range(END):
    t=f/30
    page=bg.copy()
    s=1+0.015*math.sin(t*0.7); e=em.resize((int(em.width*s),int(em.height*s))); put(page,e,W*0.74,H*0.5,anchor='c')
    r=RAYS.rotate(t*6,resample=Image.BILINEAR).crop((int(750-W*0.35),int(750-H*0.225),int(750-W*0.35)+W//2,int(750-H*0.225)+H//2)).resize((W,H),Image.BILINEAR)
    page.alpha_composite(r); motes(page,m,t,0)
    cx,cy=pointer(f)
    if f<CLICK:
        # turns toward the pointer, with a little lag
        want=-12+(cx-PX)/W*70
        yaw+=(max(-50,min(20,want))-yaw)*0.12
        im=frozen(yaw); bob=math.sin(t*2.2)*6
    else:
        im=resumed(min(99,18+(f-CLICK))); bob=0
    if SHADOW is None:
        w_=int(im.width*0.4)+80; sh=Image.new('RGBA',(w_,128)); ImageDraw.Draw(sh).ellipse((40,40,w_-40,88),fill=(30,16,20,110)); SHADOW=sh.filter(ImageFilter.GaussianBlur(14))
    page.alpha_composite(SHADOW,(int(PX-SHADOW.width/2),int(0.95*H-64)))
    page.alpha_composite(im,(int(PX-im.width/2),int(0.95*H-FEET*K+bob)))
    # after the click: the menu clears in a third of a second
    leave=ease((f-CLICK-2)/10) if f>=CLICK else 0
    hdl=hd.copy(); hdl.putalpha(hdl.split()[3].point(lambda a:int(a*(1-leave)))); page.alpha_composite(hdl,(0,int(-80*leave)))
    u=ui(0,t)
    if CLICK<=f<CLICK+4: u=u.resize((int(W*0.995),int(H*0.995)))
    if leave<1: page.alpha_composite(u,(int(-700*leave),0))
    c=CTRL.copy(); c.putalpha(c.split()[3].point(lambda a:int(a*(1-leave)))); page.alpha_composite(c)
    if f<CLICK+3: cursor(page,cx,cy,CLICK<=f)
    # zoom-through: the menu scene pushes in on Pit while the hall settles in
    if f>=ZOOM:
        k=ease((f-ZOOM)/ZN)
        z=1+0.35*k; zw,zh=int(W*z),int(H*z)
        big=page.resize((zw,zh),Image.BILINEAR); ox=int(PX*z-PX); oy=int(H*0.55*z-H*0.55)
        page=big.crop((ox,oy,ox+W,oy+H))
        hz=1.12-0.12*k; h2=hall.resize((int(W*hz),int(H*hz)),Image.BILINEAR)
        hx,hy=(h2.width-W)//2,(h2.height-H)//2; h2=h2.crop((hx,hy,hx+W,hy+H)); h2.putalpha(int(255*k))
        page.alpha_composite(h2)
    page.convert('RGB').save(f'{out}/{f:04d}.png')
print(END)
