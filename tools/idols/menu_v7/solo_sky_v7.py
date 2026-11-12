# Solo v7: chapter 1's sky in the Dream layout (heading, black ground band,
# caption, controls), the v7 vine focus, star flares on Pit's wings, the
# cutscene grade. Rebuilt 2026-11-12 from solo_sky.py after the lost v5.
#   python3 solo_sky_v7.py  ->  sky_frames_v7/     STILL=N: only frame N, to check/v7_solo.png
# Solo in chapter 1's sky, 60 fps. The sky is the game's own (stage a0101:
# sky gradient, distant mountains, sun, cloud textures). Clouds are 3D
# sprites streaming past opposite to Pit's heading, so the world moves the
# way he flies. Click: Pit whips round and rolls past the lens; the Solo
# hall shows through the trail he cuts, anime speed lines around him.
import os; WORK=os.environ.get('IDOLS_WORK','work')  # the folder with the extracted models and renders
lib={'__name__':'lib'}; exec(open('menu_anim.py').read(),lib)
g=globals(); g.update({k:v for k,v in lib.items() if not k.startswith('__')})
exec(open('ui_v4.py').read()); exec(open('ui_v7.py').read())
exec(open('still_v7.py').read().split('SHOTS = {')[0].split('from PIL import ImageChops, ImageEnhance')[1])   # heading_only, grade
import json, random
import numpy as np
from PIL import ImageChops
FPS=60
TX=WORK+'/stages/tex'
def tex(n):
    import glob; return Image.open(sorted(glob.glob(f'{TX}/*/{n}.png'))[0]).convert('RGBA')
J=json.load(open(f'{R}/sky.json')); T=J['timeline']; CLICK=J['click']
m=MODES[0]
hd=Image.new('RGBA',(W,H))
for lay in (heading_only(m), ground_band(), caption_band(m), controls_v4()): hd.alpha_composite(lay)
STILL=int(os.environ.get('STILL','-1'))   # >=0: only that frame, saved to check/
def ui60(sel,t):
    key=(sel,round(t*60))
    if key not in UI_CACHE:
        if len(UI_CACHE)>8: UI_CACHE.clear()
        UI_CACHE[key]=buttons_v7(sel,t)
    return UI_CACHE[key]
# --- the sky ---------------------------------------------------------------
HOR=int(H*0.80)
g=tex('a01m03_bg00').convert('RGB').crop((96,0,160,118))          # sky rows: deep blue down to the white haze
sky=g.resize((W,HOR),Image.BICUBIC).filter(ImageFilter.GaussianBlur(4))
# below the horizon a sea of cloud (the stage's cloud-wall texture), in strips
# that get bigger toward the viewer
wall=tex('a01m01c01_kumokabe').convert('RGB')
STRIPS=[]; y=0; k=0
while y<H-HOR:
    sc=1.2+k*0.55; th=int(14*sc); tw=int(128*sc*2)
    strip=wall.resize((tw,int(128*sc)),Image.BICUBIC).crop((0,(k*29)%int(128*sc-th),tw,(k*29)%int(128*sc-th)+th))
    row=Image.new('RGB',(W+2*tw,th))
    for x in range(0,W+2*tw,tw): row.paste(strip,(x,0))
    STRIPS.append((row.filter(ImageFilter.GaussianBlur(1.2)),y,tw,sc)); y+=th; k+=1
def floor(scroll):
    fl=Image.new('RGB',(W,H-HOR))
    for row,y,tw,sc in STRIPS:
        o=int(scroll*sc*6)%tw; fl.paste(row.crop((tw-o,0,tw-o+W,row.height)),(0,y))
    return fl
SK=Image.new('RGB',(W,H)); SK.paste(sky,(0,0)); SK.paste(floor(0),(0,HOR))
BAND=None
band=Image.new('L',(1,H)); band.putdata([int(255*math.exp(-((y-HOR)/38)**2)) for y in range(H)]); band=band.resize((W,H))
HAZE=Image.new('RGB',(W,H),(226,236,244)); BAND=band
SK=Image.composite(HAZE,SK,band)
sun=tex('a01m03_sun01').convert('RGB').resize((900,900),Image.BICUBIC)
canvas=Image.new('RGB',(W,H)); canvas.paste(sun,(int(W*0.86)-450,int(H*0.10)-450)); sky_rgb=ImageChops.screen(SK,canvas)
# the left third a little hazier, so the menu reads
haze=Image.new('L',(W,1)); haze.putdata([int(150*max(0,1-x/(W*0.42))**1.5) for x in range(W)]); haze=haze.resize((W,H))
white=Image.new('RGB',(W,H),(250,244,240)); sky_rgb=Image.composite(white,sky_rgb,haze)
SKY=sky_rgb.convert('RGBA')
flare=tex('lens_flare').convert('RGB')
# --- clouds: 3D sprites ------------------------------------------------------
def puff(texname,seed):
    r=random.Random(seed); n=256
    yy,xx=np.mgrid[0:n,0:n]/n
    m=np.zeros((n,n))
    for _ in range(7):
        cx,cy,rad=r.uniform(0.3,0.7),r.uniform(0.45,0.62),r.uniform(0.10,0.2)
        m=np.maximum(m,np.exp(-(((xx-cx)**2+(yy-cy)**2)/(rad*rad))*2.2))
    m*=np.clip((yy-0.28)/0.2,0,1)**0.5
    t=tex(texname).resize((n,n)); rgb=np.array(t)[...,:3].astype(float)
    rgb=rgb*0.55+255*0.45*(1-yy[...,None]*0.5)          # lit from above, a little whiter than the layer textures
    a=np.clip(m*1.25,0,1)*(0.55+0.45*np.array(t)[...,3]/255)
    return Image.fromarray(np.dstack([np.clip(rgb,0,255),a*255]).astype(np.uint8),'RGBA')
SPR=[puff(n,i) for i,n in enumerate(['a01m03_kumo00','a01m03_kumo01','a01m02_kumo00','a01m02_kumo01','a01m03_kumo00','a01m02_kumo01'])]
random.seed(4)
CL=[[random.uniform(-60,60),random.uniform(-22,26),random.uniform(-95,-6),random.randrange(len(SPR)),random.uniform(13,26),random.random()<0.5] for _ in range(60)]
BOX=((-60,60),(-22,26),(-95,-6)); FOC=900
SC={}
def sprite(i,px,flip):
    key=(i,int(px/8),flip)
    if key not in SC:
        if len(SC)>250: SC.clear()
        s=SPR[i].resize((max(2,int(px/8)*8),max(2,int(px/8)*8)),Image.BILINEAR)
        SC[key]=s.transpose(Image.FLIP_LEFT_RIGHT) if flip else s
    return SC[key]
def heading(yaw,pitch):
    y,p=math.radians(yaw),math.radians(pitch)
    return np.array([math.sin(y),-math.sin(p)*math.cos(y),math.cos(p)*math.cos(y)])
def clouds(page,near,dt,v):
    for c in CL:
        if near is None:
            for a in range(3):
                c[a]+=v[a]*dt; lo,hi=BOX[a]
                if c[a]<lo: c[a]+=hi-lo
                if c[a]>hi: c[a]-=hi-lo
            continue
        z=c[2]
        if (z>-14)!=near: continue
        s=FOC/(-z); px=c[4]*s
        if px<6 or px>1600: continue
        x=W/2+c[0]*s; y=H*0.55-c[1]*s
        if x+px/2<0 or x-px/2>W or y+px/2<0 or y-px/2>H: continue
        a=min(1,(z+95)/25)*min(1,(-z-5)/6)*(0.9 if not near else 0.55)
        if a<=0.02: continue
        sp=sprite(c[3],px,c[5])
        if a<0.98: sp=sp.copy(); sp.putalpha(sp.split()[3].point(lambda q:int(q*a)))
        over(page,sp,x-sp.width/2,y-sp.height/2)
def over(page,img,x,y):
    x,y=int(x),int(y); l,t=max(0,-x),max(0,-y); r,b=min(img.width,W-x),min(img.height,H-y)
    if r>l and b>t: page.alpha_composite(img.crop((l,t,r,b)),(x+l,y+t))
def cursor(page,x,y,down):
    s=1.3*(0.9 if down else 1.0); pts=[(0,0),(0,34),(9,26),(15,40),(21,37),(15,24),(27,24)]
    ImageDraw.Draw(page).polygon([(x+px*s,y+py*s) for px,py in pts],fill=(255,255,255,255),outline=(0,0,0,255),width=3)
def ease(t): t=max(0,min(1,t)); return t*t*(3-2*t)
hall=Image.open('/mnt/user-data/uploads/Kid icarus/build/menu-captures/20261109-222311/004-030-auto-upper.png').convert('RGBA')
hall=hall.resize((W,int(hall.height*W/hall.width)),Image.LANCZOS).crop((0,0,W,H))
def scaled(img,z):
    w,h=int(img.width*z),int(img.height*z); x,y=(w-W)//2,(h-H)//2
    return img.resize((w,h),Image.BILINEAR).crop((x,y,x+W,y+H))
GLOW=Image.new('RGBA',(800,800)); ImageDraw.Draw(GLOW).ellipse((200,200,600,600),fill=(255,240,220,90)); GLOW=GLOW.filter(ImageFilter.GaussianBlur(90))
PINK=(255,150,200)
def speed_lines(f,cx,cy,amount):
    lay=Image.new('RGBA',(W//2,H//2)); d=ImageDraw.Draw(lay); rnd=random.Random(f//2)
    for _ in range(70):
        a=rnd.uniform(0,2*math.pi); r0=rnd.uniform(260,520)/2; r1=r0+rnd.uniform(500,1500)/2; w=rnd.uniform(0.004,0.012)
        p=[(cx/2+math.cos(a)*r0,cy/2+math.sin(a)*r0),(cx/2+math.cos(a-w)*r1,cy/2+math.sin(a-w)*r1),(cx/2+math.cos(a+w)*r1,cy/2+math.sin(a+w)*r1)]
        d.polygon(p,fill=(255,255,255,int(rnd.uniform(120,230)*amount)))
    return lay.resize((W,H),Image.BILINEAR)
out='sky_frames_v7'; os.makedirs(out,exist_ok=True)
if STILL<0:
    for old in os.listdir(out): os.remove(f'{out}/{old}')
swept=Image.new('L',(W//2,H//2)); trail=[]; scroll=0.0; v_prev=np.zeros(3)
for e in T:
    f=e['f']; t=f/FPS; gg=f-CLICK
    if 0<=STILL and f<STILL:        # checking one frame: only move the clouds up to it
        scroll+=-v_prev[0]*(1/FPS); v_prev=-heading(e['yaw'],e['pitch'])*(16 if gg<0 else 16+40*ease(gg/20)); clouds(None,None,1/FPS,v_prev); continue
    scroll+=-v_prev[0]*(1/FPS)
    base=Image.new('RGB',(W,H)); base.paste(sky,(0,0)); base.paste(floor(scroll),(0,HOR))
    base=Image.composite(HAZE,base,BAND); base=ImageChops.screen(base,canvas); base=Image.composite(white,base,haze)
    page=base.convert('RGBA')
    v=-heading(e['yaw'],e['pitch'])*(16 if gg<0 else 16+40*ease(gg/20))
    v_prev=v; clouds(page,None,1/FPS,v); clouds(page,False,0,v)
    # Pit, with a short smear behind him when he passes
    pit=Image.open(f'{R}/sky/{f:04d}.png').convert('RGBA'); ax,ay=e['at']; z=e['z']
    if z<2.5: over(page,GLOW,ax-400,ay-380)
    if gg>=6:
        for k,(img,x,y) in enumerate(trail[-3:]):
            gh=img.copy(); gh.putalpha(gh.split()[3].point(lambda a,q=0.18*(k+1):int(a*q))); over(page,gh,x-gh.width/2,y-gh.height/2)
    over(page,pit,ax-pit.width/2,ay-pit.height/2)
    trail.append((pit,ax,ay)); trail=trail[-4:]
    clouds(page,True,0,v)
    # cutscene light: feathers, star flares on his brightest points (wings), the grade
    particles(page,'solo',t,ax,ay)
    if z<2.5:
        pts=[(x,y,k*(0.75+0.25*math.sin(t*3+n*2.1))) for n,(x,y,k) in enumerate(G.bright_points(pit,int(ax-pit.width/2),int(ay-pit.height/2)))]
        page=G.flares(page,pts,size=110)
    page=G.grade(page,vignette=0.2)
    # the menu, leaving after the click: heading rises, band sinks, buttons slide off
    leave=ease((gg-1)/12) if gg>=0 else 0
    if leave<1:
        hdl=hd.copy(); hdl.putalpha(hdl.split()[3].point(lambda a:int(a*(1-leave)))); page.alpha_composite(hdl,(0,int(260*leave)))
        u=ui60(0,t)
        if 0<=gg<6: u=u.resize((int(W*0.995),int(H*0.995)))
        page.alpha_composite(u,(int(-760*leave),0))
    # the pass: speed lines, and the hall through the trail he cuts
    if gg>=6:
        k=ease((gg-6)/10)
        page.alpha_composite(speed_lines(f,ax,ay,k*(1-ease((gg-30)/8))))
        a=pit.split()[3].resize((max(1,pit.width//2),max(1,pit.height//2)))
        tmp=Image.new('L',(W//2,H//2)); tmp.paste(a,(int((ax-pit.width/2)/2),int((ay-pit.height/2)/2)))
        swept=ImageChops.lighter(swept,tmp.filter(ImageFilter.MaxFilter(9)))
        if z>2.2:
            r=pit.width/2*0.55*ease((z-2.2)/5)
            d=ImageDraw.Draw(swept); d.ellipse(((ax-r)/2,(ay-r)/2,(ax+r)/2,(ay+r)/2),fill=255)
        mask=swept.filter(ImageFilter.GaussianBlur(2)).resize((W,H),Image.BILINEAR)
        if z>2.2:
            edge=ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(15)),mask)
            rim=Image.new('RGBA',(W,H),PINK+(0,)); rim.putalpha(edge); 
            hz=scaled(hall,1.08-0.08*ease((gg-14)/30)); page=Image.composite(hz,page,mask); page.alpha_composite(rim)
            over(page,pit,ax-pit.width/2,ay-pit.height/2) if z<9 else None
    if gg>=36:
        page=scaled(hall,1.08-0.08*ease((gg-14)/30))
    if gg<5: cursor(page,*e['pointer'],gg>=0)
    if f==STILL: page.convert('RGB').save('check/v7_solo.png'); break
    if STILL<0: page.convert('RGB').save(f'{out}/{f:04d}.png')
print(len(T))
