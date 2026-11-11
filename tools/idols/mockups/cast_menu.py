# Together / Vault / Options with their cutscene characters (60 fps): the
# mode hovered, its character idling; click: the move, and a transition in
# that character's own style into the mode's title card.
#   together: the screen is cut along a slash and the halves slide apart
#   vault:    a ring of light opens from Palutena's staff
#   options:  Viridi's swing sweeps the next screen in, leaves on its edge
import sys
lib={'__name__':'lib'}; exec(open('menu_anim.py').read(),lib)
g=globals(); g.update({k:v for k,v in lib.items() if not k.startswith('__')})
import json, random
import numpy as np
from PIL import ImageChops
FPS=60
def ui60(sel,t):
    key=(sel,round(t*60))
    if key not in UI_CACHE:
        if len(UI_CACHE)>8: UI_CACHE.clear()
        UI_CACHE[key]=ui_(sel,t)
    return UI_CACHE[key]
def over(page,img,x,y):
    x,y=int(x),int(y); l,t=max(0,-x),max(0,-y); r,b=min(img.width,W-x),min(img.height,H-y)
    if r>l and b>t: page.alpha_composite(img.crop((l,t,r,b)),(x+l,y+t))
def cursor(page,x,y,down):
    s=1.3*(0.9 if down else 1.0); pts=[(0,0),(0,34),(9,26),(15,40),(21,37),(15,24),(27,24)]
    ImageDraw.Draw(page).polygon([(x+px*s,y+py*s) for px,py in pts],fill=(255,255,255,255),outline=(0,0,0,255),width=3)
def ease(t): t=max(0,min(1,t)); return t*t*(3-2*t)
def scaled(img,z,cx=W/2,cy=H/2):
    w,h=int(img.width*z),int(img.height*z); x,y=int(cx*z-cx),int(cy*z-cy)
    return img.resize((w,h),Image.BILINEAR).crop((x,y,x+W,y+H))
def speed_lines(f,cx,cy,amount,col=(255,255,255)):
    lay=Image.new('RGBA',(W//2,H//2)); d=ImageDraw.Draw(lay); rnd=random.Random(f//2)
    for _ in range(70):
        a=rnd.uniform(0,2*math.pi); r0=rnd.uniform(300,560)/2; r1=r0+rnd.uniform(500,1500)/2; w=rnd.uniform(0.004,0.012)
        p=[(cx/2+math.cos(a)*r0,cy/2+math.sin(a)*r0),(cx/2+math.cos(a-w)*r1,cy/2+math.sin(a-w)*r1),(cx/2+math.cos(a+w)*r1,cy/2+math.sin(a+w)*r1)]
        d.polygon(p,fill=col+(int(rnd.uniform(120,230)*amount),))
    return lay.resize((W,H),Image.BILINEAR)
def card(m):
    # stand-in for the next screen: the mode's colours, emblem and heading, large
    c=background(m,3).copy(); e=emblem(m); put(c,e,W*0.5,H*0.52,anchor='c')
    h=header(m); bb=h.getbbox(); h=h.crop(bb); h=h.resize((int(h.width*1.7),int(h.height*1.7)),Image.LANCZOS)
    c.alpha_composite(h,(int(W/2-h.width/2),int(H*0.40-h.height/2)))
    return c
LEAF=None
def leaf(size,rot,col):
    im=Image.new('RGBA',(size*2,size)); d=ImageDraw.Draw(im)
    d.ellipse((0,size*0.2,size*2,size*0.8),fill=col+(255,)); d.line((size*0.1,size/2,size*1.9,size/2),fill=(30,70,30,255),width=max(1,size//10))
    return im.rotate(rot,expand=True,resample=Image.BICUBIC)
def run(mode):
    sel={'together':1,'vault':2,'options':3}[mode]; m=MODES[sel]
    J=json.load(open(f'{R}/{mode}.json')); T=J['timeline']; CLICK=J['click']; WIPE=J['wipe']; END=J['end']
    bg,em,hd=background(m,0),emblem(m),header(m); RAYS=rays_layer(); CTRL=controls(); NEXT=card(m)
    BTN=[(18*U+120,22*U+70),(28*U+130,60.9*U+75),(22*U+120,101.16*U+75),(28*U+125,135.98*U+75)][sel]
    PX,PY=0.68*W,0.52*H
    GLOW=Image.new('RGBA',(900,900)); ImageDraw.Draw(GLOW).ellipse((200,200,700,700),fill=m['color']+(80,)); GLOW=GLOW.filter(ImageFilter.GaussianBlur(110))
    out=f'{mode}_frames'; os.makedirs(out,exist_ok=True)
    for old in os.listdir(out): os.remove(f'{out}/{old}')
    rnd=random.Random(7); leaves=[]
    for e in T:
        f=e['f']; t=f/FPS; gg=f-CLICK
        page=bg.copy()
        s=1+0.015*math.sin(t*0.7); e2=em.resize((int(em.width*s),int(em.height*s))); put(page,e2,W*0.74,H*0.5,anchor='c')
        r=RAYS.rotate(t*6,resample=Image.BILINEAR).crop((int(750-W*0.35),int(750-H*0.225),int(750-W*0.35)+W//2,int(750-H*0.225)+H//2)).resize((W,H),Image.BILINEAR)
        page.alpha_composite(r); motes(page,m,t,0)
        leave=ease((gg-1)/12) if gg>=0 else 0
        if leave<1:
            hdl=hd.copy(); hdl.putalpha(hdl.split()[3].point(lambda a:int(a*(1-leave)))); page.alpha_composite(hdl,(0,int(-90*leave)))
            u=ui60(sel,t)
            if 0<=gg<6: u=u.resize((int(W*0.995),int(H*0.995)))
            page.alpha_composite(u,(int(-760*leave),0))
            c=CTRL.copy(); c.putalpha(c.split()[3].point(lambda a:int(a*(1-leave)))); page.alpha_composite(c)
        ch=Image.open(f'{R}/{mode}/{f:04d}.png').convert('RGBA')
        z=1+0.06*ease(gg/40) if gg>0 else 1          # the camera leans in on the move
        if z!=1: ch=ch.resize((int(ch.width*z),int(ch.height*z)),Image.BILINEAR)
        over(page,GLOW,PX-450,PY-430); over(page,ch,PX-ch.width/2,PY-ch.height/2)
        if 0<=gg<26 and mode=='together': page.alpha_composite(speed_lines(f,PX,PY-60,ease(gg/6)*(1-ease((gg-14)/12))))
        # the pointer: comes in, hovers the button, clicks
        if gg<5:
            k=ease(f/110); cx,cy=W*0.9+(BTN[0]-W*0.9)*k, H*0.85+(BTN[1]-H*0.85)*k
            cursor(page,cx,cy,gg>=0)
        w=f-WIPE
        if w>=0:
            k=ease(w/20)
            if mode=='together':
                # a slash from upper right to lower left; the two halves slide apart
                a=math.radians(-58); dx,dy=math.cos(a),math.sin(a)
                mask=Image.new('L',(W,H)); ImageDraw.Draw(mask).polygon([(W/2-dx*3000-dy*3000,H/2-dy*3000+dx*3000),(W/2+dx*3000-dy*3000,H/2+dy*3000+dx*3000),(W/2+dx*3000,H/2+dy*3000),(W/2-dx*3000,H/2-dy*3000)],fill=255)
                gap=900*ease(w/18)
                A=Image.new('RGBA',(W,H)); A.paste(page,(0,0),mask); B=Image.new('RGBA',(W,H)); B.paste(page,(0,0),ImageChops.invert(mask))
                nx,ny=-dy,dx
                base=scaled(NEXT,1.06-0.06*k)
                base.alpha_composite(A.transform((W,H),Image.AFFINE,(1,0,nx*gap,0,1,ny*gap)))
                base.alpha_composite(B.transform((W,H),Image.AFFINE,(1,0,-nx*gap,0,1,-ny*gap)))
                if w<10:
                    ln=Image.new('RGBA',(W,H)); d=ImageDraw.Draw(ln)
                    L=2600*ease(w/5); d.line((W/2-dx*L,H/2-dy*L,W/2+dx*L,H/2+dy*L),fill=(255,236,170,int(255*(1-w/10))),width=int(18*(1-w/10))+2)
                    base.alpha_composite(ln.filter(ImageFilter.GaussianBlur(2))); base.alpha_composite(ln)
                page=base
            elif mode=='vault':
                cx,cy=PX-40,PY-330
                rad=2300*ease(w/22)**1.4
                mask=Image.new('L',(W,H)); ImageDraw.Draw(mask).ellipse((cx-rad,cy-rad,cx+rad,cy+rad),fill=255)
                page=Image.composite(scaled(NEXT,1.06-0.06*k),page,mask.filter(ImageFilter.GaussianBlur(3)))
                ring=Image.new('RGBA',(W,H)); d=ImageDraw.Draw(ring)
                for wd,col in [(26,(120,230,255,150)),(10,(255,236,170,255))]:
                    d.ellipse((cx-rad,cy-rad,cx+rad,cy+rad),outline=col,width=wd)
                ring=Image.alpha_composite(ring.filter(ImageFilter.GaussianBlur(8)),ring)
                ring.putalpha(ring.split()[3].point(lambda a:int(a*(1-ease((w-14)/8)))))
                page.alpha_composite(ring)
                if w<14:
                    sp=Image.new('RGBA',(W,H)); d=ImageDraw.Draw(sp); rr=random.Random(w)
                    for _ in range(40):
                        an=rr.uniform(0,2*math.pi); q=rad*rr.uniform(0.9,1.1); x,y=cx+math.cos(an)*q,cy+math.sin(an)*q; s2=rr.uniform(4,10)
                        d.polygon([(x,y-s2*2),(x+s2/2,y),(x,y+s2*2),(x-s2/2,y)],fill=(255,250,220,230)); d.polygon([(x-s2*2,y),(x,y+s2/2),(x+s2*2,y),(x,y-s2/2)],fill=(255,250,220,230))
                    page.alpha_composite(sp)
            else:
                # a sweep round Viridi, the way her staff swings
                cx,cy=PX,PY+80; ang=-200+260*ease(w/20)
                mask=Image.new('L',(W,H)); ImageDraw.Draw(mask).pieslice((cx-3000,cy-3000,cx+3000,cy+3000),-200,ang,fill=255)
                page=Image.composite(scaled(NEXT,1.06-0.06*k),page,mask)
                if w<22:
                    a=math.radians(ang); edge=Image.new('RGBA',(W,H)); d=ImageDraw.Draw(edge)
                    d.line((cx,cy,cx+math.cos(a)*3000,cy+math.sin(a)*3000),fill=(190,255,150,220),width=14)
                    page.alpha_composite(edge.filter(ImageFilter.GaussianBlur(6))); page.alpha_composite(edge)
                    for _ in range(6):
                        q=rnd.uniform(150,1500); leaves.append([cx+math.cos(a)*q,cy+math.sin(a)*q,rnd.uniform(-6,6)+math.cos(a+1.57)*14,rnd.uniform(-6,6)+math.sin(a+1.57)*14,rnd.uniform(0,360),rnd.choice([(120,200,90),(90,170,70),(170,220,110),(240,170,200)]),rnd.randint(14,30)])
                for L in leaves:
                    L[0]+=L[2]; L[1]+=L[3]+2; L[3]+=0.25; L[4]+=7
                    over(page,leaf(L[6],L[4],L[5]),L[0],L[1])
        if w>=22: page=scaled(NEXT,1.0)
        page.convert('RGB').save(f'{out}/{f:04d}.png')
    print(mode,len(T))
for mode in sys.argv[1:]: run(mode)
