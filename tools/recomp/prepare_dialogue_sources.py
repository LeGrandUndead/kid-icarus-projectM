"""Fingerprint original encoded portrait resources for the opt-in draw adapter."""
from pathlib import Path
import json
from export_texture_sources import fingerprint

root = Path(__file__).resolve().parents[2] / 'build/native-ui/dialogue-sources'
rows = json.loads((root / 'sources.json').read_text(encoding='utf-8-sig'))
keys = set()
for row in rows:
    row['encoded_hash'] = f"{fingerprint((root / row['file']).read_bytes()):016X}"
    keys.add(row['encoded_hash'])
(root / 'portrait-hashes.txt').write_text('\n'.join(sorted(keys)) + '\n')
(root / 'sources.json').write_text(json.dumps(rows, indent=2) + '\n')
print(f'{len(rows)} original portrait references; {len(keys)} distinct encoded textures')
