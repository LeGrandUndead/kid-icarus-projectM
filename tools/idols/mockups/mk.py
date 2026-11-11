# helpers for the menu mock-ups (game art from the player's own ROM; stays local)
import glob, os, math, numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops
from scipy import ndimage
S='/tmp/claude-0/-home-claude/0846ad66-37b8-5f7e-bbd2-eb4c158aa498/scratchpad'
W,H=1920,1080; U=H/240
TSV={}
for line in open('/mnt/user-data/uploads/Kid icarus/build/native-ui/ui-sources.tsv'):
    p=line.split('\t')
    if len(p)>=3: TSV.setdefault(p[2].split('/')[-1],p[0])
def art(menu,name):
    h=TSV.get(name)
    if h:
        f=glob.glob(f'{S}/menu-pc-trial/*-{h}.png')
        if f: return Image.open(f[0]).convert('RGBA'),4 if Image.open(f[0]).width>=Image.open(f'all/{menu}/{name}.png').width*3 else 2
    return Image.open(f'all/{menu}/{name}.png').convert('RGBA'),1
def mask(img,color=(0,0,0),alpha=1.0):
    """a white-on-black mask picture as `color` with the luminance as coverage"""
    a=np.asarray(img).astype(float)
    L=a[:,:,:3].mean(axis=2)*(a[:,:,3]/255.0)
    out=np.zeros(a.shape,np.uint8); out[:,:,0],out[:,:,1],out[:,:,2]=color
    out[:,:,3]=np.clip(L*alpha,0,255).astype(np.uint8)
    return Image.fromarray(out)
def comp(img,box_frac):
    """the shapes of a picture whose centre lies in box (fractions of its size), cropped"""
    a=np.asarray(img); lab,_=ndimage.label(a[:,:,3]>12); w,h=img.size
    x0,y0,x1,y1=box_frac[0]*w,box_frac[1]*h,box_frac[2]*w,box_frac[3]*h
    keep=np.zeros(lab.shape,bool)
    for i,o in enumerate(ndimage.find_objects(lab)):
        cy=(o[0].start+o[0].stop)/2; cx=(o[1].start+o[1].stop)/2
        if x0<=cx<x1 and y0<=cy<y1: keep|=lab==i+1
    b=a.copy(); b[~keep,3]=0; im=Image.fromarray(b)
    return im.crop(im.getbbox())
def fit(img,w=None,h=None):
    if w and not h: h=img.height*w/img.width
    if h and not w: w=img.width*h/img.height
    return img.resize((max(1,int(w)),max(1,int(h))),Image.LANCZOS)
def shadow(img,blur,alpha=0.45,color=(0,0,0)):
    a=img.split()[3].filter(ImageFilter.GaussianBlur(blur)).point(lambda v:int(v*alpha))
    s=Image.new('RGBA',img.size,color+(0,)); s.putalpha(a); return s
def glow(img,grow,blur,color=(255,208,84),alpha=1.0):
    a=img.split()[3].filter(ImageFilter.MaxFilter(grow|1)).filter(ImageFilter.GaussianBlur(blur)).point(lambda v:int(v*alpha))
    g=Image.new('RGBA',img.size,color+(0,)); g.putalpha(a); return g
def pad(img,p):
    c=Image.new('RGBA',(img.width+2*p,img.height+2*p)); c.alpha_composite(img,(p,p)); return c
def put(page,img,x,y,anchor='tl',sh=None,gl=None,rot=0):
    """img's anchor point at (x, y); padded so shadows and glows fit"""
    w0,h0=img.size
    fx={'tl':0,'tr':1,'c':0.5,'bl':0,'bc':0.5,'br':1}[anchor]; fy={'tl':0,'tr':0,'c':0.5,'bl':1,'bc':1,'br':1}[anchor]
    cx,cy=x-fx*w0+w0/2,y-fy*h0+h0/2
    if rot: img=img.rotate(rot,expand=True,resample=Image.BICUBIC)
    p=int(max(img.size)*0.12)+4; im=pad(img,p)
    X,Y=int(cx-im.width/2),int(cy-im.height/2)
    if sh: page.alpha_composite(shadow(im,sh[0],sh[1]),(X+sh[2],Y+sh[3]))
    if gl: page.alpha_composite(glow(im,*gl),(X,Y))
    page.alpha_composite(im,(X,Y))
FONT=S+'/mock/Cinzel.ttf'; SANS=S+'/mock/Nunito.ttf'
def font(f,size,weight=None):
    ft=ImageFont.truetype(f,size)
    if weight:
        try: ft.set_variation_by_axes([weight])
        except Exception: pass
    return ft
def text(page,xy,s,f,fill,anchor='la',stroke=0,sfill=(0,0,0,255),shadow_px=0):
    d=ImageDraw.Draw(page)
    if shadow_px:
        layer=Image.new('RGBA',page.size); ImageDraw.Draw(layer).text((xy[0]+shadow_px,xy[1]+shadow_px),s,font=f,fill=(0,0,0,150),anchor=anchor,stroke_width=stroke,stroke_fill=(0,0,0,150))
        page.alpha_composite(layer.filter(ImageFilter.GaussianBlur(shadow_px*0.8)))
    d.text(xy,s,font=f,fill=fill,anchor=anchor,stroke_width=stroke,stroke_fill=sfill)
def paper(c0=(242,234,216),c1=(226,213,186),lines=True,seed=1):
    rng=np.random.default_rng(seed)
    y=np.linspace(0,1,H)[:,None]; x=np.linspace(0,1,W)[None,:]
    r=np.sqrt((x-0.5)**2*1.2+(y-0.42)**2)
    t=np.clip(r*1.3,0,1)[...,None]
    base=np.array(c0)[None,None,:]*(1-t)+np.array(c1)[None,None,:]*t
    noise=ndimage.gaussian_filter(rng.normal(0,1,(H,W)),1.2)*5
    base=base+noise[...,None]
    if lines:
        ly=(np.sin(np.arange(H)/H*2*math.pi*48)>0.92)[:,None,None]*-7
        base=base+ly
    return Image.fromarray(np.clip(base,0,255).astype(np.uint8)).convert('RGBA')
def rays(page,cx,cy,color,alpha,n=18,spread=1.0,seed=3):
    layer=Image.new('L',page.size,0); d=ImageDraw.Draw(layer); rng=np.random.default_rng(seed)
    for k in range(n):
        a=k/n*2*math.pi+rng.uniform(-0.05,0.05); w=rng.uniform(0.04,0.09)
        R=2400
        d.polygon([(cx,cy),(cx+R*math.cos(a-w),cy+R*math.sin(a-w)),(cx+R*math.cos(a+w),cy+R*math.sin(a+w))],fill=255)
    yy,xx=np.mgrid[0:page.height,0:page.width]; fall=np.clip(1-np.sqrt((xx-cx)**2+(yy-cy)**2)/(900*spread),0,1)**1.6
    a=np.asarray(layer.filter(ImageFilter.GaussianBlur(18))).astype(float)/255*fall*alpha*255
    l=Image.new('RGBA',page.size,color+(0,)); l.putalpha(Image.fromarray(a.astype(np.uint8))); page.alpha_composite(l)
def keycap(page,x,y,label,word,f,fs,ink=(30,22,20)):
    d=ImageDraw.Draw(page)
    tw=d.textlength(label,font=fs); w=max(tw+22,40); h=40
    d.rounded_rectangle((x,y,x+w,y+h),radius=9,outline=ink+(255,),width=3)
    d.text((x+w/2,y+h/2+1),label,font=fs,fill=ink+(255,),anchor='mm')
    d.text((x+w+12,y+h/2+1),word,font=f,fill=ink+(255,),anchor='lm')
    return x+w+12+d.textlength(word,font=f)+34
