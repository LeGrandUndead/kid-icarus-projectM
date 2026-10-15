"""Stage local CGFX resources from stage archives for the installed SPICA reader."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/formats/darc'))
from darc_tool_fixed import parse_darc
OUT=ROOT/'build/ai-hd-edition/asset-audit/containers'
OUT.mkdir(parents=True,exist_ok=True)
manifest=[]; seen={}; skipped=[]
def add(data,source):
    if data[:4]!=b'CGFX': return
    key=hashlib.sha256(data).hexdigest()
    if key in seen:
        seen[key]['sources'].append(source);return
    path=OUT/(key+'.bcres')
    if not path.exists():path.write_bytes(data)
    row=dict(path=str(path),sources=[source]);seen[key]=row;manifest.append(row)
for p in sorted((ROOT/'ROM/gameFiles/RomFS/us/stage').rglob('*')):
    if not p.is_file() or p.suffix not in ('.arc','.bcres','.bctex'):continue
    data=p.read_bytes();source=str(p.relative_to(ROOT/'ROM/gameFiles/RomFS'))
    if data[:4]==b'CGFX':add(data,source)
    elif data[:4]==b'darc':
        try:
            for entry in parse_darc(data).entries:
                if not entry.is_dir:add(data[entry.data_offset:entry.data_offset+entry.size],source+'::'+entry.path)
        except ValueError as e:skipped.append(dict(source=source,error=str(e)))
    else:skipped.append(dict(source=source,reason='not uncompressed DARC/CGFX'))
(OUT.parent/'containers.json').write_text(json.dumps(manifest,indent=2))
(OUT.parent/'container-skips.json').write_text(json.dumps(skipped,indent=2))
print(f'{len(manifest)} unique CGFX containers; {len(skipped)} skipped files')
