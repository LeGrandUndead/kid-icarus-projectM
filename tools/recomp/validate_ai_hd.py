"""Replay the AI-HD pack using only the isolated edition's files and saves."""
from pathlib import Path
import os,subprocess,json,hashlib,shutil,argparse

root=Path(__file__).resolve().parents[2]/'build/ai-hd-edition'
parser=argparse.ArgumentParser()
parser.add_argument('--name',default='validation-hardware')
parser.add_argument('--pack',default='textures',help='Pack directory inside the isolated edition')
args=parser.parse_args()
if Path(args.pack).name!=args.pack or args.pack in ('.','..'): raise SystemExit('Pack must be a directory name')
pack=root/args.pack
if Path(args.name).name!=args.name or args.name in ('.','..'): raise SystemExit('Name must be a directory name')
out=root/args.name
out.mkdir(exist_ok=False)
shutil.copytree(root.parent/'input-traces/20261009-072852-462179/initial-save/user',out/'user')
shutil.copytree(root/'data/sysdata',out/'sysdata')
for name in ('input.replay','input.csv'): shutil.copy2(root/'validation'/name,out/name)
if not (pack/'pack.json').exists(): raise SystemExit('Pack not validated')
env={k:v for k,v in os.environ.items() if not k.startswith(('KIU_','ZAKURO_'))}
env.update(ZAKURO_RECOMPILED=str(root/'runtime/0004000000030100.dll'),
    RUST_LOG='warn,zakuro_gpu::replacements=info',
    ZAKURO_REPLAY=str(out/'input.replay'),KIU_MOUSE_TRACE_REPLAY=str(out/'input.csv'),
    KIU_MOUSE_SENSITIVITY='0.55',ZAKURO_RASTERIZER='hardware',
    ZAKURO_DUMP_AT='1000,7000,10000,13000,13030',ZAKURO_RESOLUTION='5',
    KIU_TEXTURE_PACK=str(pack),KIU_EXPERIMENTAL_HUD='1',KIU_EXPERIMENTAL_WIDE='1',
    TEMP=str(out),TMP=str(out),APPDATA=str(out/'roaming'),LOCALAPPDATA=str(out/'local'))
with (out/'run.log').open('w') as log:
    result=subprocess.run([str(root/'runtime/boot-ai-hd.exe'),str(root/'game.3ds'),'13030'],
        cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
text=(out/'run.log').read_text()
complete=result.returncode==0 and 'Completed after 13030 frames' in text
report=dict(completed=complete,exit_code=result.returncode,
    metrics=[line for line in text.splitlines() if line.startswith(('outcome:','frame times:','gpu:'))],
    texture_count=len(json.loads((pack/'pack.json').read_text())['assets']),
    pack=args.pack,
    runtime_sha256=hashlib.sha256((root/'runtime/boot-ai-hd.exe').read_bytes()).hexdigest(),
    note='Replay binary predates frontend 1MP/LOD guards; all replacements <=1MP, cubic disabled')
(out/'result.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
raise SystemExit(0 if complete else 1)
