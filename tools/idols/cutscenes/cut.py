# A cutscene's characters as one model (heads on their bodies), sampled at
# N moments, and a pose sheet of them.
import sys, os, subprocess, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import merge
S=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D=f'{S}/spica/dump/bin/Release/net8.0/dump'
SCENES={
 'T06':('028',[('23','c06_030_pith00',{'Face'}),('21','c06_030_pith',set(),'23','HeadN'),('24','c06_030_bpith04',{'Face'}),('22','c06_030_bpith',set(),'24','HeadN')],960),
 'T05':('024',[('24','c05_040_pith00',{'Face'}),('21','c05_040_pith',set(),'24','HeadN'),('25','c05_040_bpith04',{'Face'}),('22','c05_040_bpith',set(),'25','HeadN')],2095),
 'T25':('122',[('21','c25_040_pith03',{'Face'}),('22','c25_040_pith',set(),'21','HeadN'),('23','c25_040_bpith04',{'Face'}),('24','c25_040_bpith',set(),'23','HeadN')],7390),
 'T21':('096',[('27','c21_030_pith00',{'Face'}),('21','c21_030_pith',set(),'27','HeadN'),('28','c21_030_bpith04',{'Face'}),('22','c21_030_bpith',set(),'28','HeadN'),('23','c21_030_paluh01',set())],1500),
 'P82':('129',[('21','c82_010_paluh00',set())],360),
 'P20':('091',[('22','c20_030_paluh',set())],836),
 'V11':('051',[('23','c11_030_natur',{'Effect'})],1550),
 'H25':('119',[('22','c25_030_hadeh',set())],1760),
}
# The clips the main menu plays (render/cast.py), chosen from pose sheets:
#   T05 clash: the chapter 5 grapple, from the moment they lock (frame 258)
#              through the throw and the kick
#   P20 idle:  Palutena's calm opening pose (head bowed, staff in hand)
#   P20 clip:  her staff flourish at the end of the chapter 20 scene
CLIPS={'clash':('T05',258,392,1),'idle':('P20',0,166,1),'clip':('P20',650,836,1)}
def clips():
    for name,(key,a,b,step) in CLIPS.items(): build(key,start=a,end=b,step=step,name=name)
def build(key, n=40, start=None, end=None, step=None, name='scene'):
    d,parts,frames=SCENES[key]
    if step is None: step=frames/n
    env=dict(os.environ)
    if start is not None: env.update(ANIM_START=str(start), ANIM_END=str(end))
    done={}
    for p in parts:
        f,anim=p[0],p[1]
        out=f'{S}/idols/out{key}_{f}'
        os.makedirs(out,exist_ok=True)
        subprocess.run([D,f'{S}/demo/{d}/mdl/{f}.bcres',out,anim,str(step)],capture_output=True,env=env)
        done[f]=(out,anim)
    mparts=[]
    for p in parts:
        out,anim=done[p[0]]
        if len(p)>3: mparts.append((out,anim,p[2],done[p[3]],p[4]))
        else: mparts.append((out,anim,p[2]))
    merge.merge(f'{S}/idols/out{key}',mparts,name)
if __name__=='__main__':
    if sys.argv[1:]==['clips']: clips()
    else:
        for k in sys.argv[1:]: build(k)
