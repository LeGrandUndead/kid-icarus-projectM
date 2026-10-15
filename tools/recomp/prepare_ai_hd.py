"""Create an isolated local AI-HD edition and provenance-tracked source set."""
from pathlib import Path
import csv, hashlib, json, shutil
from PIL import Image
from export_texture_sources import fingerprint

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/ai-hd-edition'

def copy_once(source, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists(): shutil.copy2(source, dest)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).with_name('ai_hd_art_policy.json'),OUT/'art-policy.json')
    for source, dest in [
        ('tools/zakuro/target/release/zakuro-experimental.exe','runtime/zakuro-ai-hd.exe'),
        ('build/kiu-aot-o2/0004000000030100.dll','runtime/0004000000030100.dll'),
        ('Kid Icarus - Uprising (USA) (En,Fr,Es).3ds','game.3ds'),
        ('build/user-data/kiu/sysdata/shared_font.bin','data/sysdata/shared_font.bin')]:
        copy_once(ROOT/source, OUT/dest)
    saves = OUT/'data/user'
    if not saves.exists():
        shutil.copytree(ROOT/'build/user-data/experimental-pc/kiu/user', saves)
    settings = OUT/'profile/roaming/zakuro/settings.toml'
    if not settings.exists():
        copy_once(ROOT/'build/user-data/experimental-pc/roaming/zakuro/settings.toml',settings)
        import re
        settings.write_text(re.sub(r'^layout = .*$', 'layout = "top_only"', settings.read_text(),flags=re.M))
    # Keep all inputs/results of AI processing inside this edition.
    reviewed = ROOT/'build/texture-work/sources-20261011'
    sources = {row['file']:row for row in json.loads((OUT/'sources.json').read_text())} if (OUT/'sources.json').exists() else {}
    for row in json.loads((reviewed/'sources.json').read_text()):
        copy_once(reviewed/row['file'],OUT/'sources'/row['file'])
        sources[row['file']] = dict(row, classification='reviewed original',
            model='realesrgan-x4plus-anime')
    # Compressed ETC textures cannot be the GPU's writable framebuffer images.
    # Other formats require individual review; never blanket-replace captures.
    for table in sorted((ROOT/'build/texture-traces').glob('*/capture/textures.csv')):
        for row in csv.DictReader(table.open()):
            if row['format'] not in ('Etc1','Etc1A4'): continue
            w,h = int(row['width']),int(row['height'])
            raw = table.parent/f"texture-{int(row['id']):04}.rgba"
            if not raw.exists() or w*h>256*256: continue
            data=raw.read_bytes()
            if len(data)!=w*h*4: continue
            name=f'{w}x{h}-{fingerprint(data):016X}.png'
            if name in sources: continue
            Image.frombytes('RGBA',(w,h),data).save(OUT/'sources'/name)
            sources[name]=dict(file=name,width=w,height=h,source=str(raw),
                classification='static ETC texture',model='realesrgan-x4plus')
    (OUT/'sources.json').write_text(json.dumps(list(sources.values()),indent=2))
    binaries={str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [OUT/'runtime/zakuro-ai-hd.exe',OUT/'runtime/0004000000030100.dll']}
    (OUT/'build.json').write_text(json.dumps(dict(runtime='copied experimental runtime; isolated installation',binaries=binaries,source_count=len(sources)),indent=2))
    print(f'Isolated edition prepared: {len(sources)} static sources')

if __name__=='__main__': main()
