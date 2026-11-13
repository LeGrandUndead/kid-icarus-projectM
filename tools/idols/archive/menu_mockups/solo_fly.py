# Solo at 60 fps: Pit glides in place and swings round to head toward the
# pointer; click: he turns to the camera and flies straight at it, and the
# Solo hall is behind him when he has passed.
lib={'__name__':'lib'}; exec(open('menu_anim.py').read(),lib)
g=globals(); g.update({k:v for k,v in lib.items() if not k.startswith('__')})
import json
def ui60(sel,t):  # the buttons sway every frame, not ten times a second
    key=(sel,round(t*60))
    if key not in UI_CACHE:
        if len(UI_CACHE)>8: UI_CACHE.clear()
        UI_CACHE[key]=ui_(sel,t)
    return UI_CACHE[key]
FPS=60
J=json.load(open(f'{R}/fly.json')); T=J['timeline']; CLICK=J['click']; TURN=J['turn']; DIVE=J['dive']
m=MODES[0]; bg,em,hd=background(m,0),emblem(m),header(m); RAYS=rays_layer(); CTRL=controls()
hall=Image.open('/mnt/user-data/uploads/Kid icarus/build/menu-captures/20261109-222311/004-030-auto-upper.png').convert('RGBA')
hall=hall.resize((W,int(hall.height*W/hall.width)),Image.LANCZOS).crop((0,0,W,H))
def cursor(page,x,y,down):
    s=1.3*(0.9 if down else 1.0)
    pts=[(0,0),(0,34),(9,26),(15,40),(21,37),(15,24),(27,24)]
    ImageDraw.Draw(page).polygon([(x+px*s,y+py*s) for px,py in pts],fill=(255,255,255,255),outline=(0,0,0,255),width=3)
def ease(t): t=max(0,min(1,t)); return t*t*(3-2*t)
def scaled(img,z):
    w,h=int(img.width*z),int(img.height*z); x,y=(w-W)//2,(h-H)//2
    return img.resize((w,h),Image.BILINEAR).crop((x,y,x+W,y+H))
def over(page,img,x,y):  # alpha_composite that allows partly off-screen images
    x,y=int(x),int(y); l,t=max(0,-x),max(0,-y); r,b=min(img.width,W-x),min(img.height,H-y)
    if r>l and b>t: page.alpha_composite(img.crop((l,t,r,b)),(x+l,y+t))
GLOW=Image.new('RGBA',(700,700)); ImageDraw.Draw(GLOW).ellipse((150,150,550,550),fill=(255,236,190,120)); GLOW=GLOW.filter(ImageFilter.GaussianBlur(80))
out='fly_frames'; os.makedirs(out,exist_ok=True)
for old in os.listdir(out): os.remove(f'{out}/{old}')
for e in T:
    f=e['f']; t=f/FPS
    page=bg.copy()
    s=1+0.015*math.sin(t*0.7); em2=em.resize((int(em.width*s),int(em.height*s))); put(page,em2,W*0.74,H*0.5,anchor='c')
    r=RAYS.rotate(t*6,resample=Image.BILINEAR).crop((int(750-W*0.35),int(750-H*0.225),int(750-W*0.35)+W//2,int(750-H*0.225)+H//2)).resize((W,H),Image.BILINEAR)
    page.alpha_composite(r); motes(page,m,t,0)
    after=f-CLICK
    leave=ease((after-1)/14) if after>=0 else 0
    if leave<1:
        hdl=hd.copy(); hdl.putalpha(hdl.split()[3].point(lambda a:int(a*(1-leave)))); page.alpha_composite(hdl,(0,int(-80*leave)))
        u=ui60(0,t)
        if 0<=after<6: u=u.resize((int(W*0.995),int(H*0.995)))
        page.alpha_composite(u,(int(-700*leave),0))
        c=CTRL.copy(); c.putalpha(c.split()[3].point(lambda a:int(a*(1-leave)))); page.alpha_composite(c)
    # the scene leans in a little as he comes at us
    z=e['z']
    if z>1: page=scaled(page,1+0.08*ease((z-1)/12))
    # the hall arrives behind him while he fills the screen
    h=ease((z-3)/6)
    if h>0:
        h2=scaled(hall,1.10-0.10*h); h2.putalpha(int(255*h)); page.alpha_composite(h2)
    pit=Image.open(f'{R}/fly/{f:04d}.png').convert('RGBA')
    pa=1-ease((z-8)/5)
    if pa<1: pit.putalpha(pit.split()[3].point(lambda a:int(a*pa)))
    ax,ay=e['at']
    if z<3: over(page,GLOW,ax-350,ay-330)
    over(page,pit,ax-pit.width/2,ay-pit.height/2)
    if after<5: cursor(page,*e['pointer'],after>=0)
    page.convert('RGB').save(f'{out}/{f:04d}.png')
print(len(T))
