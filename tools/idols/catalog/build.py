# The animation catalog: every idol's Wait and Action00, every Pit gameplay
# animation (ground g0, air a0) on the Pit idol. 24 frames each, looping cells.
import os; WORK=os.environ.get('IDOLS_WORK','work')  # the folder with the extracted models and renders
import subprocess, os, sys, math, re, numpy as np
sys.path.insert(0,WORK+'/render')
S=WORK
D=f'{S}/spica/dump/bin/Release/net8.0/dump'
IDOLS={'000':'Pit','002':'Palutena','006':'Medusa','007':'Magnus','009':'Dark Pit','010':'Poseidon','011':'Hades','012':'Viridi'}
G0=[f for f in os.popen(f"find {S}/scan/player_g0_character_mdl.arc -name '*.bcres'").read().split()][0]
A0=[f for f in os.popen(f"find {S}/scan/player_a0_character_mdl.arc -name '*.bcres'").read().split()][0]
def anims(src):
    out=subprocess.run([D,src,'/tmp/catx'],capture_output=True,text=True).stdout
    return [(m.group(1),int(m.group(2))) for m in re.finditer(r'anim (\S+) frames (\d+)',out)]
entries=[]
for d,name in IDOLS.items():
    for an,n in anims(f'{S}/idols/{d}/fmdl/00.bcres'):
        entries.append((f'{name}: idol {an.split("00")[-1] if "00" in an else an}',d,an,None,n))
for src,kind in ((G0,'ground'),(A0,'air')):
    for an,n in anims(src):
        entries.append((f'Pit {kind}: {an.replace("ChrPit00","")}','000',an,src,n))
print(len(entries),'animations')
import json; json.dump(entries,open('entries.json','w'))
for label,d,an,src,n in entries:
    out=f'{S}/idols/out{d}/{an}.frames'
    if os.path.exists(out): os.remove(out)
    step=max(1.0,n/24)
    cmd=[D,f'{S}/idols/{d}/fmdl/00.bcres',f'{S}/idols/out{d}',an,f'{step:.4f}']+([src] if src else [])
    subprocess.run(cmd,capture_output=True)
print('frames exported')
