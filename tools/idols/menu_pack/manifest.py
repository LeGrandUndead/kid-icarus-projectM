"""The pack's manifest.toml, read by the game (pc_menus/scene/manifest.rs):
plain keys first, then one [[modes]] table per mode with its character as a
sub-table."""
import json

import numpy as np


def value(v):
    """One value in TOML."""
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (int, np.integer)): return str(int(v))
    if isinstance(v, (float, np.floating)): return repr(float(v))
    if isinstance(v, str): return json.dumps(v)
    if isinstance(v, (list, tuple)): return '[' + ', '.join(value(x) for x in v) + ']'
    if isinstance(v, dict): return '{ ' + ', '.join(f'{k} = {value(x)}' for k, x in v.items()) + ' }'
    raise TypeError(type(v))


def document(man):
    """The whole manifest (a dict with a 'modes' list) as TOML text."""
    out = []
    for k, v in man.items():
        if k != 'modes': out.append(f'{k} = {value(v)}')
    for e in man['modes']:
        out.append('\n[[modes]]')
        for k, v in e.items():
            if k != 'character': out.append(f'{k} = {value(v)}')
        ch = e.get('character') or {}
        if ch:
            out.append('[modes.character]')
            for k, v in ch.items(): out.append(f'{k} = {value(v)}')
    return '\n'.join(out) + '\n'
