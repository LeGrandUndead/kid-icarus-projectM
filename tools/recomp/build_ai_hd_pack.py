"""Offline AI restoration of reviewed/ETC sources in the isolated edition."""
from pathlib import Path
import hashlib, json, shutil, subprocess
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]/'build/ai-hd-edition'

def main():
    (ROOT/'textures/pack.json').unlink(missing_ok=True)
    rows=json.loads((ROOT/'sources.json').read_text())
    policy=json.loads((ROOT/'art-policy.json').read_text())
    excluded=set(policy['original_only'])
    approved=set(policy['approved_for_ai'])-excluded
    rows=[row for row in rows if row['file'] in approved]
    quarantine=ROOT/'excluded-character-art'
    quarantine.mkdir(exist_ok=True)
    for name in excluded:
        if Path(name).name!=name: raise ValueError('Unsafe policy filename')
        replacement=ROOT/'textures'/name
        if replacement.exists():
            if not (quarantine/name).exists(): shutil.copy2(replacement,quarantine/name)
            replacement.unlink()
    tool=ROOT/'tooling/realesrgan/realesrgan-ncnn-vulkan.exe'
    models=tool.parent/'models'
    for model in sorted({row['model'] for row in rows}):
        input_dir=ROOT/'tooling'/('input-'+model)
        input_dir.mkdir(exist_ok=True)
        # These directories previously included portraits; exclude them from
        # both inference and upload even on an incremental rebuild.
        for name in excluded: (input_dir/name).unlink(missing_ok=True)
        for path in input_dir.glob('*.png'):
            if path.name not in approved: path.unlink()
        for row in rows:
            if row['model']==model:
                with Image.open(ROOT/'sources'/row['file']) as original:
                    pixels=np.asarray(original.convert('RGBA'))
                    # NCNN's reflection padding fails on very narrow inputs.
                    # Extend edge pixels, then crop back to the original atlas.
                    padded=np.pad(pixels,((0,max(0,32-original.height)),
                        (0,max(0,32-original.width)),(0,0)),mode='edge')
                    Image.fromarray(padded).save(input_dir/row['file'])
        with (ROOT/'tooling'/f'{model}.log').open('w') as log:
            subprocess.run([str(tool),'-i',str(input_dir),'-o',str(ROOT/'textures'),
                '-n',model,'-m',str(models),'-s','4','-t','32','-j','1:1:1','-f','png'],
                stdout=log,stderr=subprocess.STDOUT,check=True)
        log_text=(ROOT/'tooling'/f'{model}.log').read_text()
        if 'failed' in log_text.lower() or 'error' in log_text.lower():
            raise RuntimeError(f'{model}: inference log reports an error; pack is not validated')
    validated=[]
    for row in rows:
        path=ROOT/'textures'/row['file']
        with Image.open(path) as im:
            factor=row.get('factor',4)
            if factor not in (2,4): raise ValueError('Unsupported restoration factor')
            if row['width']<32 or row['height']<32:
                im=im.crop((0,0,row['width']*4,row['height']*4))
                im.save(path)
            if factor==2:
                im=im.resize((row['width']*2,row['height']*2),Image.Resampling.LANCZOS)
                im.save(path)
            if im.size!=(row['width']*factor,row['height']*factor) or im.width*im.height>1048576:
                raise ValueError(f'Invalid replacement dimensions: {path}')
            if im.mode!='RGBA': raise ValueError(f'Missing alpha channel: {path}')
            with Image.open(ROOT/'sources'/row['file']) as source:
                # Preserve original full transparency/opacity regions. Some
                # antialiasing at the contour is expected from reconstruction.
                lo,hi=source.getchannel('A').getextrema()
                if lo<255 and im.getchannel('A').getextrema()[0]==255:
                    raise ValueError(f'Lost transparency: {path}')
        validated.append(dict(row,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (ROOT/'textures/pack.json').write_text(json.dumps(dict(
        technique='Real-ESRGAN offline AI restoration; 2x/4x; no new-layout generation',
        upstream='https://github.com/xinntao/Real-ESRGAN',
        archive_sha256=hashlib.sha256((ROOT/'tooling/realesrgan.zip').read_bytes()).hexdigest(),
        original_only=sorted(excluded),assets=validated),indent=2))
    print(f'Validated {len(validated)} AI texture replacements',flush=True)

if __name__=='__main__': main()
