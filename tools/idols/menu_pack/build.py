"""Builds the whole pack into one folder: every layer, each mode's character
frames (only the missing ones), the packed frames and the manifest.

    IDOLS_WORK=<work folder> python3 -m menu_pack <out folder> [--modes 0123]

--modes: the modes whose missing character frames are built (default all).
Frames already in the folder are always kept and listed, so a partial run
never drops another mode's character from the manifest.
"""
import os
import sys

from PIL import Image

from . import characters, frame_pak, layers, manifest
from .config import BAND_Y, H, W
from .game_art import particle_images
from .images import light_on_black, mix, white_shape
from .modes import MODES, PALETTE

NAMES = ['solo', 'together', 'vault', 'options']


def build(out, modes='0123'):
    os.makedirs(out, exist_ok=True)

    def save_rgb(img, name, q=92):
        img.convert('RGB').save(f'{out}/{name}.webp', quality=q, method=4)
        return f'{name}.webp'

    def save_rgba(img, name):
        img.save(f'{out}/{name}.png', optimize=True)
        return f'{name}.png'

    def cropped(img, name):
        bb = img.getchannel('A').getbbox()
        return dict(file=save_rgba(img.crop(bb), name), at=[bb[0], bb[1]])

    papers = layers.papers()
    stages = layers.stages()
    solo_glow = layers.key_glow(0)
    place = characters.placements()
    impact = characters.impact(place)
    man = dict(size=[W, H], band_y=BAND_Y, panel=dict(x0=900, lean=330), impact=list(impact), modes=[])
    for m in range(4):
        pal = PALETTE[m]
        rays_at = pal['at'] if m != 1 else impact            # Together's rays start where the kick lands
        heading = layers.heading(m)
        e = dict(name=NAMES[m], color=list(MODES[m]['color']), key=list(pal['key']), key_at=list(pal['at']),
                 high=list(pal['high']), deep=list(pal['deep']),
                 paper=save_rgb(papers[m], f'paper_{m}'), stage=save_rgb(stages[m], f'stage_{m}'), stage_scroll=7 if m == 0 else 0,
                 emblem=dict(file=save_rgba(layers.emblem(m), f'emblem_{m}'), at=[-180, 0]),
                 rays=save_rgb(light_on_black(layers.rays(rays_at, pal['key'])), f'rays_{m}', 85), rays_at=list(rays_at),
                 heading=dict(file=save_rgba(heading, f'heading_{m}'), base=[100 + heading.width / 2, 64 + heading.height]),
                 caption=cropped(layers.caption(m), f'caption_{m}'))
        if m == 0: e['glow'] = save_rgb(light_on_black(solo_glow), 'glow_0', 85)
        print('mode', m, 'layers'); sys.stdout.flush()
        if m in place:
            e['character'] = characters.frames(m, out, place, stages[m], solo_glow, build_missing=str(m) in modes)
        else:
            e['character'] = {}
        print('mode', m, 'frames', len(e['character'].get('frames', {}))); sys.stdout.flush()
        man['modes'].append(e)
    man['band'] = cropped(layers.ground_band(), 'band')
    man['controls'] = cropped(layers.controls(), 'controls')
    swirl = layers.swirl()
    man['swirl'] = dict(file=save_rgba(swirl, 'swirl'), at=[W - swirl.width + 40, -42])
    man['sprig'] = dict(file=save_rgba(layers.sprig(), 'sprig'), base=[780, BAND_Y + 40])
    p = particle_images()
    man['sprites'] = dict(feather=save_rgba(white_shape(p['feather']), 'sprite_feather'),
                          spark=save_rgba(white_shape(p['spark']), 'sprite_spark'),
                          powder=save_rgba(white_shape(p['powder']), 'sprite_powder'),
                          leaves=[save_rgba(white_shape(l), f'sprite_leaf{i}') for i, l in enumerate(p['leaves'])],
                          flash=save_rgba(white_shape(p['flash']), 'sprite_flash'))
    for e in man['modes']:                       # frames as [index, x, y, width, height] rows
        ch = e['character']
        if ch: ch['frames'] = [[int(i)] + [int(v) for v in f] for i, f in sorted(ch['frames'].items())]
    open(f'{out}/manifest.toml', 'w').write(manifest.document(man))
    for m, e in enumerate(man['modes']):
        if e['character']: frame_pak.pack(out, m)
    print('pack written:', out)
