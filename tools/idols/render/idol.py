# Renders a posed idol (exported by the SPICA converter) with its own
# textures, plus a stylised look: soft two-tone light, a rim light in a
# chosen colour, a thin ink outline. Software rasteriser (numpy).
import numpy as np, math, sys, os
from PIL import Image
S='/tmp/claude-0/-home-claude/0846ad66-37b8-5f7e-bbd2-eb4c158aa498/scratchpad/idols'

def load(idol):
    out=f'{S}/out{idol}'; tex=f'{S}/tex{idol}'
    v=np.fromfile(f'{out}/mesh.bin',dtype=np.float32).reshape(-1,16)
    groups=[]; at=0
    for line in open(f'{out}/meshes.txt'):
        if line.startswith('#'): continue
        p=line.rstrip('\n').split('\t'); n=int(p[1])
        at_=p[11] if len(p)>11 else '-'; bl=p[12] if len(p)>12 else ''
        groups.append(dict(t0=p[0],t1=p[5],t2=p[6],maps=p[7],name=p[2],layer=int(p[3]),start=at,count=n,test=(int(at_.split(':')[1])/255 if ':' in at_ else None),blend='SourceAlpha' in bl)); at+=n
    texs={}
    for line in open(f'{tex}/textures.txt'):
        name,w,h=line.split('\t'); w,h=int(w),int(h)
        texs[name]=np.fromfile(f'{tex}/{name}.rgba',dtype=np.uint8).reshape(h,w,4).astype(np.float32)/255
    return v,groups,texs

def rot(yaw,pitch):
    cy,sy,cp,sp=math.cos(yaw),math.sin(yaw),math.cos(pitch),math.sin(pitch)
    Ry=np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]]); Rx=np.array([[1,0,0],[0,cp,-sp],[0,sp,cp]])
    return Rx@Ry

def sample(t,u,v,flip=True):
    h,w=t.shape[:2]
    if flip: v=1-v
    x=(u%1)*w-0.5; y=(v%1)*h-0.5
    x0=np.floor(x).astype(int); y0=np.floor(y).astype(int); fx=(x-x0)[:,None]; fy=(y-y0)[:,None]
    x0%=w; y0%=h; x1=(x0+1)%w; y1=(y0+1)%h
    return (t[y0,x0]*(1-fx)*(1-fy)+t[y0,x1]*fx*(1-fy)+t[y1,x0]*(1-fx)*fy+t[y1,x1]*fx*fy)

FRAMES={}
def frame(idol,anim,k):
    key=(idol,anim)
    if key not in FRAMES:
        v,_,_=load(idol); FRAMES[key]=np.fromfile(f'{S}/out{idol}/{anim}.frames',dtype=np.float32).reshape(-1,len(v),6)
    return FRAMES[key][k]
def render(idol,size=1200,yaw=0.0,pitch=0.0,rim=(1,0.8,0.4),plain=False,flip=False,ss=2,anim=None,k=0,span_fix=None,glow_only=False):
    v,groups,texs=load(idol)
    if anim: v=v.copy(); v[:,0:6]=frame(idol,anim,k)
    R=rot(yaw,pitch)
    P=v[:,0:3]@R.T; N=v[:,3:6]@R.T
    # models without normals (the menu's books): flat ones from each triangle
    bad=~np.isfinite(N).all(1)
    if bad.any():
        T=P.reshape(-1,3,3); fn=np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0])
        fn/=np.maximum(np.linalg.norm(fn,axis=1,keepdims=True),1e-9); fn*=np.where(fn[:,2:3]<0,-1,1)
        N=np.where(bad[:,None],np.repeat(fn,3,axis=0),N)
    W=H=size*ss
    lo,hi=P.min(0),P.max(0); span=max(hi[0]-lo[0],hi[1]-lo[1])*1.06; c=(lo+hi)/2
    if span_fix: span,c=span_fix[0],np.array(span_fix[1])
    sx=(P[:,0]-c[0])/span*W+W/2; sy=H/2-(P[:,1]-c[1])/span*H; sz=P[:,2]
    def colour_tex(g):
        maps=g['maps'].split('/'); names=[g['t0'],g['t1'],g['t2']]
        for nm,mp in zip(names,maps):
            if nm in texs and mp=='UvCoordinateMap' and not nm.lower().endswith('mask') and 'High' not in nm and 'Iris' not in nm: return nm
        return None
    # alpha test as the material sets it (blended overlays: half way); the
    # coverage is the strongest of the material's UV-mapped textures
    cutout={}
    for gi,g in enumerate(groups):
        ref=g['test'] if g['test'] is not None else (0.5 if g['blend'] else None)
        if ref is None: continue
        nm=colour_tex(g); ts=[texs[nm]] if nm else []
        if ts: cutout[gi]=(ts,ref)
    depth=np.full((H,W),-1e9,np.float32); gid=np.full((H,W),-1,np.int32)
    attr=np.zeros((H,W,13),np.float32)  # n3 uv0 uv1 uv2 col4
    for g_i,g in enumerate(groups):
        if (g['layer']==2)!=glow_only: continue
        for t in range(g['start'],g['start']+g['count'],3):
            i=np.arange(t,t+3)
            x,y,z=sx[i],sy[i],sz[i]
            x0,x1=int(max(0,math.floor(x.min()))),int(min(W-1,math.ceil(x.max())))
            y0,y1=int(max(0,math.floor(y.min()))),int(min(H-1,math.ceil(y.max())))
            if x1<x0 or y1<y0: continue
            d=(y[1]-y[2])*(x[0]-x[2])+(x[2]-x[1])*(y[0]-y[2])
            if abs(d)<1e-9: continue
            gx,gy=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
            a=((y[1]-y[2])*(gx-x[2])+(x[2]-x[1])*(gy-y[2]))/d
            b=((y[2]-y[0])*(gx-x[2])+(x[0]-x[2])*(gy-y[2]))/d
            cc=1-a-b
            inside=(a>=0)&(b>=0)&(cc>=0)
            if not inside.any(): continue
            zz=a*z[0]+b*z[1]+cc*z[2]
            win=inside&(zz>depth[y0:y1+1,x0:x1+1])
            if g_i in cutout and win.any():
                uu=a[win]*v[i[0],6]+b[win]*v[i[1],6]+cc[win]*v[i[2],6]; vv=a[win]*v[i[0],7]+b[win]*v[i[1],7]+cc[win]*v[i[2],7]
                ts,ref=cutout[g_i]
                al=np.max([sample(t_,uu,vv,flip)[:,3] for t_ in ts],axis=0)
                keep=np.zeros_like(win); keep[win]=al>ref; win=keep
            if not win.any(): continue
            depth[y0:y1+1,x0:x1+1][win]=zz[win]; gid[y0:y1+1,x0:x1+1][win]=g_i
            at=np.concatenate([N[i],v[i,6:16]],1)  # n3 uv0 uv1 uv2 col4
            vals=(a[win][:,None]*at[0][None,:13]+b[win][:,None]*at[1][None,:13]+cc[win][:,None]*at[2][None,:13])
            attr[y0:y1+1,x0:x1+1][win]=vals
    # shade
    out=np.zeros((H,W,4),np.float32)
    mask=gid>=0
    n=attr[...,0:3]; n=n/np.maximum(np.linalg.norm(n,axis=-1,keepdims=True),1e-6)
    L=np.array([-0.45,0.6,0.66]); L/=np.linalg.norm(L)
    for g_i,g in enumerate(groups):
        m=gid==g_i
        if not m.any(): continue
        u0,v0=attr[...,3][m],attr[...,4][m]; u1,v1=attr[...,5][m],attr[...,6][m]; u2,v2=attr[...,7][m],attr[...,8][m]
        nn=n[m]
        base=np.ones((m.sum(),4),np.float32)
        maps=g['maps'].split('/')
        # colour: the first UV-mapped texture
        names=[g['t0'],g['t1'],g['t2']]
        col=None
        for k,(nm,mp) in enumerate(zip(names,maps)):
            if nm in texs and mp=='UvCoordinateMap' and not nm.lower().endswith('mask') and 'High' not in nm and 'Iris' not in nm:
                col=sample(texs[nm],u0,v0,flip); break
        if col is None:
            for nm in names:
                if nm in texs: col=sample(texs[nm],u0,v0,flip); break
        if 'Iris' in g['t1'] and g['t1'] in texs and g['t2'] in texs:
            white=sample(texs[g['t2']],u2,v2,flip); iris=sample(texs[g['t1']],u1,v1,flip)
            col=white.copy(); a_=iris[:,3:4]; col[:,:3]=white[:,:3]*(1-a_)+iris[:,:3]*a_
            if g['t0'] in texs:
                hi=sample(texs[g['t0']],u0,v0,flip); col[:,:3]=np.clip(col[:,:3]+hi[:,:3]*hi[:,3:4],0,1)
            col[:,3]=1
        if col is not None: base=col
        # environment reflection (the figurine's shine)
        env=None
        if maps[0]=='CameraSphereEnvMap' and names[0] in texs:
            env=sample(texs[names[0]],nn[:,0]*0.5+0.5,nn[:,1]*0.5+0.5,flip)[:,:3]
        lam=np.clip(nn@L,0,1)
        if plain:
            shade=0.45+0.55*lam
            rgb=base[:,:3]*shade[:,None]
            if env is not None: rgb=rgb*0.75+env*0.35
        else:
            # soft two tones + rim in the menu colour
            tone=0.62+0.38*np.clip((lam-0.25)*3,0,1)
            rgb=base[:,:3]*tone[:,None]
            if env is not None: rgb=rgb*0.85+env*0.22
            rimk=np.clip(1-abs(nn[:,2]),0,1)**3.0
            rgb=rgb+np.array(rim)[None,:]*rimk[:,None]*0.55
        out[m,:3]=np.clip(rgb,0,1); out[m,3]=1
    if not plain and mask.any():
        # ink outline on the silhouette and where depth jumps
        dz=np.zeros_like(depth); D=np.where(mask,depth,depth[mask].min()-span*0.3 if mask.any() else 0)
        for dy,dx in ((0,1),(1,0),(0,-1),(-1,0)):
            dz=np.maximum(dz,np.abs(D-np.roll(np.roll(D,dy,0),dx,1)))
        edge=(dz>span*0.012)
        grow=edge.copy()
        for dy,dx in ((0,1),(1,0),(0,-1),(-1,0),(1,1),(-1,-1)):
            grow|=np.roll(np.roll(edge,dy,0),dx,1)
        ink=np.array([0.06,0.04,0.05])
        out[grow,:3]=ink; out[grow,3]=np.maximum(out[grow,3],1)
    img=Image.fromarray((out*255).astype(np.uint8),'RGBA')
    img=img.resize((size,size),Image.LANCZOS)
    bb=img.getbbox()
    return img if (span_fix or not bb) else img.crop(bb)

if __name__=='__main__':
    idol=sys.argv[1]; yaw=float(sys.argv[2]) if len(sys.argv)>2 else 0
    render(idol,600,math.radians(yaw),0,plain=True).save(f'plain_{idol}.png')
