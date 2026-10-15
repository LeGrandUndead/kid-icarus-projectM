"""Promote only a replay-validated expansion, keeping the previous pack intact."""
from pathlib import Path
import hashlib,json,shutil

ROOT=Path(__file__).resolve().parents[2]/'build/ai-hd-edition'

def main():
    result=json.loads((ROOT/'validation-stage-expansion/result.json').read_text())
    if not result['completed'] or result['pack']!='textures-stage-candidate':
        raise ValueError('Candidate replay has not passed')
    candidate=ROOT/'textures-stage-candidate'
    policy=json.loads((ROOT/'art-policy-stage.json').read_text())
    assets=json.loads((candidate/'pack.json').read_text())['assets']
    names={r['file'] for r in assets}
    if names!={p.name for p in candidate.glob('*.png')}: raise ValueError('Unexpected PNGs')
    if names & set(policy['original_only']) or not names<=set(policy['approved_for_ai']):
        raise ValueError('Art policy violation')
    for row in assets:
        if hashlib.sha256((candidate/row['file']).read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Asset changed after validation')
    backup=ROOT/'rollback-before-stage-expansion'
    backup.mkdir(exist_ok=False)
    for name in ('sources.json','art-policy.json'):
        shutil.copy2(ROOT/name,backup/name)
    # All targets are fixed descendants of this isolated edition. Retain the
    # old pack so switching back does not require rerunning any AI processing.
    (ROOT/'textures').rename(backup/'textures')
    try:
        candidate.rename(ROOT/'textures')
        shutil.copy2(ROOT/'sources-stage.json',ROOT/'sources.json')
        shutil.copy2(ROOT/'art-policy-stage.json',ROOT/'art-policy.json')
    except Exception:
        if (ROOT/'textures').exists(): (ROOT/'textures').rename(candidate)
        (backup/'textures').rename(ROOT/'textures')
        for name in ('sources.json','art-policy.json'): shutil.copy2(backup/name,ROOT/name)
        raise
    shutil.copy2(ROOT/'art-policy.json',Path(__file__).with_name('ai_hd_art_policy.json'))
    print(f'Installed {len(assets)} replacements; previous pack retained at {backup}')

if __name__=='__main__': main()
