exec(open('mk.py').read())
exec(open('vine.py').read())
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
modes={
 'Solo':dict(color=(224,120,150),emb=('040','MenCmnBgUp0007Sg'),head=(0.0,0.185),cap='The story of Pit, our angelic hero.',node=0),
 'Together':dict(color=(232,140,70),emb=('040','MenCmnBgUp0002Ml'),head=(0.19,0.386),cap='Battle it out wirelessly with others!',node=1),
 'Vault':dict(color=(96,176,104),emb=('040','MenCmnBgUp0007Cl'),head=(0.588,0.785),cap="View content you've unlocked.",node=2),
 'Options':dict(color=(160,112,206),emb=('040','MenCmnBgUp0007Op'),head=(0.79,0.985),cap='Adjust settings to your liking.',node=3),
}
def scene(name):
    m=modes[name]; c=m['color']
    page=paper(seed=m['node']+2)
    # the mode's colour washes in from the right, with its emblem as a watermark
    yy,xx=np.mgrid[0:H,0:W]; t=np.clip((xx/W-0.25)*1.2,0,1)*0.42
    wash=Image.new('RGBA',(W,H),c+(0,)); wash.putalpha(Image.fromarray((t*255).astype(np.uint8))); page.alpha_composite(wash)
    e,_=art(*m['emb']); e=mask(e,c,0.55); e=fit(e,h=1100)
    put(page,e,W*0.74,H*0.5,anchor='c')
    rays(page,int(W*0.71),int(H*0.55),(255,250,235),0.8,spread=1.1)
    # the character
    if name=='Solo':
        s,_=art('140','MenEqipUp0005'); s=mask(s,INK); put(page,fit(s,h=900),W*0.75,H+40,anchor='bc')
    elif name=='Together':
        s,_=art('040','MenTopUp0004'); s=comp(mask(s,INK),(0,0,1,0.5)); s=fit(s,h=760)
        put(page,s,W*0.62,H+30,anchor='bc')
        dark=s.transpose(Image.FLIP_LEFT_RIGHT); dk=np.asarray(dark).copy(); dk[:,:,0]=38;dk[:,:,1]=12;dk[:,:,2]=52; dark=Image.fromarray(dk)
        put(page,dark,W*0.86,H+30,anchor='bc',gl=(9,26,(150,60,200),0.9))
        lt,_=art('280','MenOnlineSelgmUp0004'); 
    elif name=='Vault':
        s,_=art('160','MenCollectionTopUp0027'); s=mask(s,INK); put(page,fit(s,h=1000),W*0.76,H+20,anchor='bc')
    else:
        s,_=art('190','MenOptionSousaUp0002'); s=mask(s,INK); put(page,fit(s,h=900),W*0.72,H+20,anchor='bc')
    # heading: the game's own word art, with its rainbow flourish
    hm=mask(heads,INK); y0,y1=m['head']; hd=hm.crop((0,int(y0*hm.height),hm.width,int(y1*hm.height))); hd=hd.crop(hd.getbbox()); hd=fit(hd,h=96)
    put(page,hd,W*0.415,110,anchor='c',sh=(6,0.25,4,6))
    fl,_=art('040','MenTopUp0000'); fl=mask(fl,(255,255,255)); fl=fit(fl,w=380)
    a=np.asarray(fl).copy(); g=np.linspace(0,1,a.shape[1])[None,:]
    a[:,:,0]=(220*(1-g)+60*g); a[:,:,1]=(60*(1-g)+200*g); a[:,:,2]=(220*(1-g)+230*g)
    put(page,Image.fromarray(a.astype(np.uint8)),W*0.415,200,anchor='c')
    text(page,(W*0.415,262),m['cap'],font(SANS,30,700),INK+(235,),anchor='mm')
    # the vine and the buttons
    s=0.46
    items=[((1,1,193,86),0,(18,20),-2,0),((1,91,184,180),0,(26,71),2,1),((0,182,118,255),0,(18,124),-1.5,2),((203,1,255,174),1,(26,170),1.5,3)]
    rects=[];imgs=[]
    for r,rot,(x,y),ang,node in items:
        p=button(r,rot); w,h=p.width/kA*s,p.height/kA*s; rects.append((x,y,x+w,y+h)); imgs.append((p,x,y,w,h,ang,node))
    big=Image.new('L',(W*2,H*2),0); d=ImageDraw.Draw(big)
    for poly in vine(rects): d.polygon([(px*U*2,py*U*2) for px,py in poly],fill=255)
    mv=big.resize((W,H),Image.LANCZOS)
    sh=Image.new('RGBA',(W,H),(0,0,0,0)); sh.putalpha(mv.filter(ImageFilter.GaussianBlur(5)).point(lambda v:v*0.3)); page.alpha_composite(sh,(5,8))
    blk=Image.new('RGBA',(W,H),(10,6,8,255)); blk.putalpha(mv); page.alpha_composite(blk)
    back,_=art('020','MenCmnBack0002'); put(page,fit(back,w=150),int(14*U),int(208*U),sh=(5,0.4,4,6))
    for p,x,y,w,h,ang,node in imgs:
        sel=node==m['node']; k=1.07 if sel else 1
        im=fit(p,w=w*U*k)
        put(page,im,x*U+w*U/2,y*U+h*U/2,anchor='c',sh=(6,0.5,6,9),gl=(11,12,(255,208,84),1.0) if sel else None,rot=ang)
    return page
pages={n:scene(n) for n in modes}
pages['Solo'].convert('RGB').save('mock_main_solo_v3.png')
grid=Image.new('RGB',(W,H))
for i,n in enumerate(modes): grid.paste(pages[n].convert('RGB').resize((W//2,H//2),Image.LANCZOS),((i%2)*W//2,(i//2)*H//2))
grid.save('mock_main_grid_v3.png')
