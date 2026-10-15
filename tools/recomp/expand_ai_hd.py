"""Build a reviewed stage-material expansion without modifying the active pack."""
from pathlib import Path
import hashlib, json, shutil, subprocess
import numpy as np
from PIL import Image
from export_texture_sources import fingerprint

ROOT = Path(__file__).resolve().parents[2] / 'build/ai-hd-edition'
# Contact-sheet review: normals, ambiguous data textures, and an illustrated
# enemy card. Keep these byte-for-byte original rather than reconstruct them.
EXCLUDED = {17,31,115,127,128,129,130,131,135,136,141,184,216,232,
    265,292,327,429,440,472,538,594,604,609,611,612,614,616,623,
    632,633,636,637,641,642,675,702,752,753,759,813,857,868,870,877}

def main():
    audit = ROOT/'asset-audit'
    expected='5c3ff535dea1e6a7d4c0fafff4607f1c3ee0867199e673b9d2b42a375d234055'
    if hashlib.sha256((audit/'material-candidates.json').read_bytes()).hexdigest()!=expected:
        raise ValueError('Candidate list changed: repeat visual review before processing')
    candidates = json.loads((audit/'material-candidates.json').read_text())
    policy = json.loads((ROOT/'art-policy.json').read_text())
    rows = json.loads((ROOT/'sources.json').read_text())
    known = {r['file'] for r in rows}
    pack = ROOT/'textures-stage-candidate'
    pack.mkdir(exist_ok=True)
    active = json.loads((ROOT/'textures/pack.json').read_text())
    validated = {r['file']:r for r in active['assets']}
    for row in active['assets']:
        shutil.copy2(ROOT/'textures'/row['file'],pack/row['file'])
    review = []
    for i, row in enumerate(candidates):
        if i in EXCLUDED:
            review.append(dict(index=i,decision='keep original',origins=row['origins']))
            continue
        w,h = row['width'],row['height']
        raw = (audit/'decoded'/row['file']).read_bytes()
        im = Image.frombytes('RGBA',(w,h),raw).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        name = f'{w}x{h}-{fingerprint(im.tobytes()):016X}.png'
        if name in policy['original_only']:
            raise ValueError(f'Portrait collision: {name}')
        review.append(dict(index=i,decision='reviewed stage color material',file=name))
        if name in known: continue
        im.save(ROOT/'sources'/name)
        rows.append(dict(file=name,width=w,height=h,source=row['origins'],
            classification='visually reviewed stage material',model='realesrgan-x4plus',
            factor=2 if w*h>65536 else 4))
        known.add(name)
        policy['approved_for_ai'].append(name)
    (audit/'material-review.json').write_text(json.dumps(review,indent=2))
    (ROOT/'sources-stage.json').write_text(json.dumps(rows,indent=2))
    (ROOT/'art-policy-stage.json').write_text(json.dumps(policy,indent=2))
    pending = [r for r in rows if r['file'] in policy['approved_for_ai'] and r['file'] not in validated]
    inputs = ROOT/'tooling/input-stage-expansion'
    outputs = ROOT/'tooling/output-stage-expansion'
    inputs.mkdir(exist_ok=True); outputs.mkdir(exist_ok=True)
    for row in pending:
        with Image.open(ROOT/'sources'/row['file']) as im:
            pixels=np.asarray(im.convert('RGBA'))
            pixels=np.pad(pixels,((0,max(0,32-im.height)),(0,max(0,32-im.width)),(0,0)),mode='edge')
            Image.fromarray(pixels).save(inputs/row['file'])
    print(f'Processing {len(pending)} additional materials; {len(EXCLUDED)} candidates excluded',flush=True)
    tool=ROOT/'tooling/realesrgan/realesrgan-ncnn-vulkan.exe'
    logpath=ROOT/'tooling/stage-expansion.log'
    with logpath.open('w') as log:
        subprocess.run([str(tool),'-i',str(inputs),'-o',str(outputs),'-n','realesrgan-x4plus',
            '-m',str(tool.parent/'models'),'-s','4','-t','32','-j','1:1:1','-f','png'],
            stdout=log,stderr=subprocess.STDOUT,check=True)
    logtext=logpath.read_text().lower()
    if 'failed' in logtext or 'error' in logtext: raise RuntimeError('Inference errors; active pack unchanged')
    for row in pending:
        w,h,factor=row['width'],row['height'],row.get('factor',4)
        with Image.open(outputs/row['file']) as result:
            result.load()
            expected=(max(w,32)*4,max(h,32)*4)
            if result.size!=expected or result.mode!='RGBA': raise ValueError(row['file'])
            result=result.crop((0,0,w*4,h*4))
            if factor==2: result=result.resize((w*2,h*2),Image.Resampling.LANCZOS)
            if result.width*result.height>1048576: raise ValueError('Runtime pixel limit')
            with Image.open(ROOT/'sources'/row['file']) as original:
                if original.getchannel('A').getextrema()[0]<255 and result.getchannel('A').getextrema()[0]==255:
                    raise ValueError('Lost alpha: '+row['file'])
            result.save(pack/row['file'])
        validated[row['file']]=dict(row,sha256=hashlib.sha256((pack/row['file']).read_bytes()).hexdigest())
    active['assets']=list(validated.values())
    active['technique']='Offline Real-ESRGAN; 4x small textures, 2x larger materials; original character drawings'
    (pack/'pack.json').write_text(json.dumps(active,indent=2))
    print(f'Candidate ready: {len(validated)} replacements; active edition unchanged',flush=True)

if __name__=='__main__': main()
