# Animation catalog: every animation we can play, numbered and labelled,
# 18 to a page, each cell looping its move. Also one still index sheet.
import os; WORK=os.environ.get('IDOLS_WORK','work')  # the folder with the extracted models and renders
import json, os, re, sys
from PIL import Image, ImageDraw, ImageFont
S=WORK
def F(p,s,w=None):
    f=ImageFont.truetype(p,s)
    if w:
        try: f.set_variation_by_axes([w])
        except Exception: pass
    return f
SANS=S+'/mock/Nunito.ttf'; SERIF=S+'/mock/Cinzel.ttf'
E_=json.load(open('entries.json'))
def name(e):
    label,d,an,src,n=e
    who=label.split(':')[0]
    move=re.sub(r'^(Dol[A-Za-z]+00|ChrPit00)','',an) or an
    if move=='Action00': move='Action (idol)'
    if move=='Wait': move='Wait (idol)'
    return who,move,n
BG=(24,18,22); CARD=(38,30,36); GOLD=(240,200,110); INK=(236,230,222); DIM=(160,150,150)
COLS,ROWS=6,3; CW,CH=310,328; IMG=280; TOP=70
W,H=1920,1080; X0=(W-COLS*CW)//2
pages=[list(range(i,min(i+COLS*ROWS,len(E_)))) for i in range(0,len(E_),COLS*ROWS)]
def cell_img(i,k):
    p=f'cells/{i:03d}/{k:03d}.png'
    if not os.path.exists(p):
        fs=sorted(x for x in os.listdir(f'cells/{i:03d}') if x.endswith('.png'))
        if not fs: return None
        p=f'cells/{i:03d}/{fs[k%len(fs)]}'
    return Image.open(p).convert('RGBA').resize((IMG,IMG),Image.LANCZOS)
f_id=F(SANS,22,800); f_mv=F(SANS,21,700); f_who=F(SANS,16,600); f_h=F(SERIF,34,700); f_s=F(SANS,20,600)
def page(pi,k,static=False):
    im=Image.new('RGBA',(W,H),BG+(255,)); d=ImageDraw.Draw(im)
    ids=pages[pi]
    groups=sorted(set(name(E_[i])[0] for i in ids),key=lambda g:[name(E_[i])[0] for i in ids].index(g))
    d.text((X0+8,18),'Animation catalog',font=f_h,fill=GOLD)
    d.text((W-X0-8,30),f'page {pi+1}/{len(pages)}  ·  #{ids[0]:03d}–#{ids[-1]:03d}  ·  '+', '.join(groups),font=f_s,fill=DIM,anchor='ra')
    for j,i in enumerate(ids):
        x=X0+(j%COLS)*CW+5; y=TOP+(j//COLS)*CH
        d.rounded_rectangle((x,y,x+CW-10,y+CH-10),12,fill=CARD+(255,))
        c=cell_img(i,k)
        if c: im.alpha_composite(c,(x+(CW-10-IMG)//2,y+4))
        who,mv,n=name(E_[i])
        d.text((x+10,y+CH-58),f'#{i:03d}',font=f_id,fill=GOLD)
        d.text((x+72,y+CH-57),mv[:20],font=f_mv,fill=INK)
        d.text((x+10,y+CH-32),f'{who} · {n} frames',font=f_who,fill=DIM)
    return im
if sys.argv[1:]==['still']:
    for pi in range(len(pages)):
        page(pi,12).convert('RGB').save(f'sheet_{pi+1:02d}.png')
else:
    os.makedirs('vid',exist_ok=True); n=0
    for pi in range(len(pages)):
        for rep in range(2):
            for k in range(24):
                page(pi,k).convert('RGB').save(f'vid/{n:05d}.png'); n+=1
    print(n)
