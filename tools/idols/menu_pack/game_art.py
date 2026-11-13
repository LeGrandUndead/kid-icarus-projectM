"""The game's own art: menu textures by name, and particle images from its
effect files."""
import glob

import numpy as np
from PIL import Image

from . import config

_SOURCES = None


def _sources():
    """Art name -> texture fingerprint (ui-sources.tsv: fingerprint, ..., path)."""
    global _SOURCES
    if _SOURCES is None:
        _SOURCES = {}
        for line in open(config.UI_SOURCES):
            p = line.split('\t')
            if len(p) >= 3: _SOURCES.setdefault(p[2].split('/')[-1], p[0])
    return _SOURCES


def art(menu, name):
    """A menu texture by its name in menu archive `menu`, as RGBA, and its
    scale: the 4x texture pack's version when there is one (4, or 2 for a
    texture the pack doubled only), else the original (1)."""
    h = _sources().get(name)
    original = f'{config.MENU_ART}/{menu}/{name}.png'
    if h:
        f = glob.glob(f'{config.MENU_ART_4X}/*-{h}.png')
        if f: return Image.open(f[0]).convert('RGBA'), 4 if Image.open(f[0]).width >= Image.open(original).width * 3 else 2
    return Image.open(original).convert('RGBA'), 1


_EFFECTS = {}


def effect_image(effect, name):
    """A particle image from a converted effect file (fx/<effect>), as an
    RGBA array, top row first."""
    if (effect, name) not in _EFFECTS:
        for line in open(f'{config.EFFECTS}/{effect}/textures.txt'):
            n, w, h = line.split('\t')
            if n == name:
                a = np.fromfile(f'{config.EFFECTS}/{effect}/{n}.rgba', np.uint8).reshape(int(h), int(w), 4)[::-1]
                _EFFECTS[effect, name] = np.ascontiguousarray(a)
    return _EFFECTS[effect, name]


def particle_images():
    """The particles the menu uses: a feather (Together, Solo), a spark
    (Vault, completed by mirroring), powder and four leaves (Options), and
    the flash of an impact."""
    from .images import mirrored
    leaf = effect_image('demo_051_demo', 'ptc_c11_030_NatLeaf')
    return dict(feather=effect_image('demo_024_demo', 'ptc_c05_040_hane'),
                powder=effect_image('demo_051_demo', 'ptc_c11_030_konaA'),
                leaves=[leaf[y:y + 32, x:x + 32] for x in (0, 32) for y in (0, 32)],
                flash=effect_image('doll_008_doll', 'ptc_cmn_flashA'),
                spark=mirrored(effect_image('demo_024_demo', 'ptc_c05_040_hikari01')))
