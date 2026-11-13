# The main menu's scene pack for the game (zakuro: menu_scene.rs): every layer
# of the v11 mock-up (menu_v11.py), made once from the player's ROM data, in
# 1920x1080 reference pixels. Nothing here is committed: the pack is written
# to <out> and copied to build/texture-work/menu-pc/scene-040 on the PC.
#
#   python3 scene_pack.py <out>          (run in the menu_v7 work folder)
#
# Layers (manifest.json says where each goes):
#   paper_M, stage_M (opaque), emblem_M, heading_M, caption_M, band, swirl,
#   sprig, controls (alpha), rays_M, glow_0 (light: added, stored on black),
#   sprite_* (white particle shapes, tinted at run time),
#   char_M/NNNN.jpg + NNNN_a.png: the character, relit for its stage,
#   light-wrapped, with its soft glow, cropped: colour as JPEG, coverage as a
#   grey PNG (both decode about 4x faster than WebP, so the game can stream
#   them at 60 fps); the manifest gives each frame's corner and size and
#   the sequences (loop, back-and-forth, one-shot).
import os, sys, json
g = {'__name__': 'scene_pack'}
exec(open('menu_v11.py').read(), g)
globals().update({k: v for k, v in g.items() if not k.startswith('__')})
from PIL import Image
import numpy as np

OUT = sys.argv[1] if sys.argv[1:] else 'scene-040'
os.makedirs(OUT, exist_ok=True)
NAMES = ['solo', 'together', 'vault', 'options']

def toml_value(v):
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (int, np.integer)): return str(int(v))
    if isinstance(v, (float, np.floating)): return repr(float(v))
    if isinstance(v, str): return json.dumps(v)
    if isinstance(v, (list, tuple)): return '[' + ', '.join(toml_value(x) for x in v) + ']'
    if isinstance(v, dict): return '{ ' + ', '.join(f'{k} = {toml_value(x)}' for k, x in v.items()) + ' }'
    raise TypeError(type(v))
def toml_doc(man):
    """The manifest as TOML (what the runtime reads): plain keys first, then
    one [[modes]] table per mode, its character as a sub-table."""
    out = []
    for k, v in man.items():
        if k != 'modes': out.append(f'{k} = {toml_value(v)}')
    for e in man['modes']:
        out.append('\n[[modes]]')
        for k, v in e.items():
            if k != 'character': out.append(f'{k} = {toml_value(v)}')
        ch = e.get('character') or {}
        if ch:
            out.append('[modes.character]')
            for k, v in ch.items(): out.append(f'{k} = {toml_value(v)}')
    return '\n'.join(out) + '\n'
def save_rgb(img, name, q=92):
    img.convert('RGB').save(f'{OUT}/{name}.webp', quality=q, method=4)
    return f'{name}.webp'
def save_rgba(img, name):
    img.save(f'{OUT}/{name}.png', optimize=True)
    return f'{name}.png'
def light_on_black(img):
    """An added light layer, as the colour it adds (RGB on black)."""
    return Image.alpha_composite(Image.new('RGBA', img.size, (0, 0, 0, 255)), img).convert('RGB')
def cropped(img, name):
    bb = img.getchannel('A').getbbox()
    return dict(file=save_rgba(img.crop(bb), name), at=[bb[0], bb[1]])

# --- the characters: which frames each mode plays --------------------------------
SEQ = {
    # Pit: a seamless 6 s glide with a glance and a barrel roll (render/solo_loop.py)
    0: dict(dir=f'{R}/solo_loop_buf', idle=dict(range=[0, 359], play='loop'), confirm=dict(range=[1000, 1047])),
    1: dict(dir=f'{R}/poster_tog_buf', idle=dict(range=[0, 149], play='pingpong'), confirm=dict(range=[150, 215], impact=190)),
    # Palutena and Viridi: their new key-art animations (render/promo.py): an
    # entrance into the hero pose, a held pose that loops in 4 s, a confirm pose
    2: dict(dir=f'{R}/promo_P02_buf', intro=dict(range=[0, 39]), idle=dict(range=[100, 339], play='loop'), confirm=dict(range=[400, 439])),
    3: dict(dir=f'{R}/promo_V12_buf', intro=dict(range=[0, 39]), idle=dict(range=[100, 339], play='loop'), confirm=dict(range=[400, 439])),
}

# --- v13 framing: full figures standing on the ground band, none cut off --------
FEET = 900          # the ground band's top edge (the band starts at 905)
REF = {0: (f'{R}/poster_solo/0060.png', None), 1: (f'{R}/poster_tog_buf/0100_post.png', 'stand'),
       2: (f'{R}/promo_P02_buf/0100_post.png', 'stand'), 3: (f'{R}/promo_V12_buf/0100_post.png', 'stand')}
SIZE = {0: (640, 1340, 880), 1: (820, 1390, FEET + 4), 2: (860, 1420, FEET), 3: (800, 1410, FEET)}
for mode, (h, cx, feet) in SIZE.items():
    if not os.path.exists(REF[mode][0]): print('no reference yet for mode', mode); continue
    ref = Image.open(REF[mode][0]).getchannel('A').point(lambda a: 255 if a > 40 else 0).getbbox()
    k = h / (ref[3] - ref[1]); PLACE[mode] = (k, cx - (ref[0] + ref[2]) / 2 * k, feet - ref[3] * k)
# Pit's new loop (glance, barrel roll) sweeps wider than the old poster pose:
# measured over the whole loop, his wings reached x 690-2070 and y -50-970.
# Shrink him about his flight centre and move him into the window so the
# whole wingspan stays on screen.
FIT0 = dict(scale=0.82, about=(1380, 460), move=(-90, 40))
if 0 in PLACE:
    k, x0, y0 = PLACE[0]; sc = FIT0['scale']; (ax, ay), (mx, my) = FIT0['about'], FIT0['move']
    PLACE[0] = (k * sc, ax + (x0 - ax) * sc + mx, ay + (y0 - ay) * sc + my)
b190 = Image.open(f'{R}/poster_tog_buf/0190_post.png').getbbox(); k1, x1, y1 = PLACE[1]
IMPACT = (int(x1 + (b190[0] + b190[2]) / 2 * k1), int(y1 + (b190[1] + 0.45 * (b190[3] - b190[1])) * k1))
RAYS[1] = G.backlight_rays((W, H), IMPACT[0], IMPACT[1], PAL[1]['key'], n=24, length=1700, strength=TUNE['rays'])
# the light: shading blurred so it draws no hard edges across faces, the rim
# only at the outline (relight.py), no separate skin tint
for m in range(4):
    LIGHT[m].update(soft=6, skin_shadow=None, skin_flat=0.0, dark=0.6 if m == 1 else 0.5)

def rest_panel(mode):
    """The window as it stands at rest, for the light wrap."""
    win = Image.new('RGBA', (W, H)); o = 60
    win.paste(STAGE[mode].crop((o, 35, o + W, 35 + H)), (0, 0))
    if mode == 0: win = G.add(win, GLOW0)
    return win

def bleed(img):
    """The colour under the see-through pixels, filled from the nearby
    visible ones (a premultiplied blur divided by the blurred coverage), so
    JPEG has no dark or stray colour to bleed into the soft edges."""
    from scipy import ndimage
    a = np.asarray(img, np.float32) / 255
    alpha = a[:, :, 3:4]
    rgb = a[:, :, :3]
    soft = np.zeros_like(rgb); cover = np.zeros_like(alpha)
    for sigma in (2, 6, 18):                       # near colour first, far colour for big gaps
        pre = np.stack([ndimage.gaussian_filter(rgb[:, :, c] * alpha[:, :, 0], sigma) for c in range(3)], 2)
        cov = ndimage.gaussian_filter(alpha[:, :, 0], sigma)[:, :, None]
        fill = (cover < 1e-3) & (cov > 1e-3)
        soft = np.where(fill, pre / np.maximum(cov, 1e-6), soft)
        cover = np.where(fill, 1.0, cover)
    out = np.where(alpha > 0.98, rgb, alpha * rgb + (1 - alpha) * soft)
    return Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8))

def save_frame(lay, base):
    """One character frame: colour (JPEG) and coverage (grey PNG)."""
    bleed(lay).save(base + '.jpg', quality=92, subsampling=0)
    lay.getchannel('A').save(base + '_a.png', optimize=False, compress_level=6)

def char_frames(mode):
    seq = SEQ[mode]; k, x0, y0 = PLACE[mode]; panel = rest_panel(mode)
    os.makedirs(f'{OUT}/char_{mode}', exist_ok=True)
    frames = {}
    wanted = sorted({i for part in ('intro', 'idle', 'confirm') if part in seq for i in range(seq[part]['range'][0], seq[part]['range'][1] + 1)})
    for i in wanted:
        pre = f'{seq["dir"]}/{i:04d}'
        if not os.path.exists(pre + '_nrm.png'):
            print('missing', pre); continue
        done = f'{OUT}/char_{mode}/{i:04d}.jpg'
        if os.path.exists(done) and os.path.exists(done + '.at'):       # already built (incremental)
            frames[i] = [int(x) for x in open(done + '.at').read().split()]; continue
        old = f'{OUT}/char_{mode}/{i:04d}.webp'
        if os.path.exists(old) and os.path.exists(old + '.at'):         # built before as WebP: convert
            lay = Image.open(old).convert('RGBA'); x, y = [int(v) for v in open(old + '.at').read().split()]
            save_frame(lay, done[:-4]); frames[i] = [x, y, lay.width, lay.height]
            open(done + '.at', 'w').write(' '.join(map(str, frames[i]))); os.remove(old); os.remove(old + '.at'); continue
        ch = scaled(relight.relight(pre, **LIGHT[mode]), k)
        pos = (int(x0), int(y0))
        ch = integrate(ch, mode, panel, pos)
        pad = 40
        lay = Image.new('RGBA', (ch.width + 2 * pad, ch.height + 2 * pad))
        lay.alpha_composite(soft_glow(ch, mix(MODES[mode]['color'], (255, 240, 220), 0.5), 0.22, 16), (pad, pad))
        lay.alpha_composite(ch, (pad, pad))
        bb = lay.getchannel('A').getbbox()
        lay = lay.crop(bb)
        save_frame(lay, done[:-4])
        frames[i] = [pos[0] - pad + bb[0], pos[1] - pad + bb[1], lay.width, lay.height]
        open(done + '.at', 'w').write(' '.join(map(str, frames[i])))
    out = {p: seq[p] for p in ('intro', 'idle', 'confirm') if p in seq}
    return dict(dir=f'char_{mode}', frames=frames, **out)

if True:
    man = dict(size=[W, H], band_y=BAND_Y, panel=dict(x0=900, lean=330), impact=list(IMPACT), modes=[])
    for m in range(4):
        e = dict(name=NAMES[m], color=list(MODES[m]['color']), key=list(PAL[m]['key']), key_at=list(PAL[m]['at']),
                 high=list(PAL[m]['high']), deep=list(PAL[m]['deep']),
                 paper=save_rgb(PAPERS[m], f'paper_{m}'), stage=save_rgb(STAGE[m], f'stage_{m}'), stage_scroll=7 if m == 0 else 0,
                 emblem=dict(file=save_rgba(EMB[m], f'emblem_{m}'), at=[-180, 0]),
                 rays=save_rgb(light_on_black(RAYS[m]), f'rays_{m}', 85), rays_at=list(PAL[m]['at'] if m != 1 else IMPACT),
                 heading=dict(file=save_rgba(HEAD[m], f'heading_{m}'), base=[100 + HEAD[m].width / 2, 64 + HEAD[m].height]),
                 caption=cropped(CAP[m], f'caption_{m}'))
        if m == 0: e['glow'] = save_rgb(light_on_black(GLOW0), 'glow_0', 85)
        print('mode', m, 'layers'); sys.stdout.flush()
        only = os.environ.get('MODES')
        e['character'] = char_frames(m) if not os.environ.get('NOCHAR') and (not only or str(m) in only) else {}
        print('mode', m, 'frames', len(e['character'].get('frames', {}))); sys.stdout.flush()
        man['modes'].append(e)
    man['band'] = cropped(BAND, 'band')
    man['controls'] = cropped(CTRL, 'controls')
    man['swirl'] = dict(file=save_rgba(SWIRL, 'swirl'), at=[W - SWIRL.width + 40, -42])
    man['sprig'] = dict(file=save_rgba(SPRIG, 'sprig'), base=[780, BAND_Y + 40])
    P = _parts()
    def white(a, name):
        a = np.asarray(a, np.float32); cover = a[:, :, :3].mean(2) * a[:, :, 3] / 255
        out = np.zeros(a.shape[:2] + (4,), np.uint8); out[..., :3] = 255; out[..., 3] = np.clip(cover, 0, 255)
        return save_rgba(Image.fromarray(out), name)
    man['sprites'] = dict(feather=white(P['hane'], 'sprite_feather'), spark=white(P['spark'], 'sprite_spark'),
                          powder=white(P['kona'], 'sprite_powder'), leaves=[white(l, f'sprite_leaf{i}') for i, l in enumerate(P['leaves'])],
                          flash=white(FLASH, 'sprite_flash'))
    for e in man['modes']:                       # frames as [index, x, y, width, height] rows
        ch = e['character']
        if ch: ch['frames'] = [[int(i)] + [int(v) for v in f] for i, f in sorted(ch['frames'].items())]
    open(f'{OUT}/manifest.toml', 'w').write(toml_doc(man))
    print('pack written:', OUT)
