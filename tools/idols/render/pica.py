# The 3DS GPU's (PICA200) per-pixel shading, as the game's materials ask
# for it: texture lookups, fragment lighting with the material's look-up
# tables, and the six-stage colour combiner. Follows SPICA.Rendering's
# FragmentShaderGenerator and DefaultVertexShader, in numpy, for many
# pixels at once (arrays of shape (n, ...)).
import numpy as np

# The scene's lights: the game's own character light rig, from a cutscene's
# light file (RomFS demo/098 00.bcres: Chr_Light01 and HemiSphereLight01).
# Directions are in the game's world space; the renderer turns them into
# view space with the model's rotation.
ENV = dict(
    light_dir=-np.array([0.70, -0.18, -0.70]),        # toward the light (the file stores where it shines)
    light_ambient=np.array([0.30, 0.30, 0.30]),
    light_diffuse=np.array([0.40, 0.40, 0.40]),
    light_specular0=np.array([0.50, 0.50, 0.63]),
    light_specular1=np.array([0.50, 0.70, 1.00]),
    scene_ambient=np.array([0.0, 0.0, 0.0]),
    hemi_sky=np.array([0.16, 0.14, 0.14]),
    hemi_ground=np.array([0.54, 0.54, 0.54]),
    hemi_dir=np.array([0.0, 1.0, 0.0]),
)
# Chapter 1's character light (stage a0101 mdl 00.bcres: Chr_Light01), the
# one Pit flies under in the sky of chapter 1
CH1 = dict(ENV, light_ambient=np.array([0.30, 0.30, 0.30]), light_diffuse=np.array([0.30, 0.30, 0.30]),
           light_specular0=np.array([0.30, 0.30, 0.30]), light_specular1=np.array([0.60, 0.55, 0.50]))
# Viridi's own light in her chapter 11 cutscene (demo/051 00.bcres: Natu_Light)
NATU = dict(ENV, light_ambient=np.array([0.15, 0.27, 0.40]), light_diffuse=np.array([0.42, 0.51, 0.55]),
            light_specular0=np.array([0.51, 0.65, 0.71]), light_specular1=np.array([0.62, 0.65, 0.68]),
            # her eyes' shader boosts the colour x8, tuned for the cutscene's own
            # light (from above and behind); the rest keeps the front key light
            eye_dir=np.array([0.0, 0.5455, -0.838]))
# which light each converted model gets (by its name); the rest: Chr_Light01
LIGHTS = {'Viri': NATU, 'V11': NATU, 'ViriH': NATU, 'PitHF': CH1, '000': CH1, 'T05': CH1, 'PitH': CH1, 'DPitH': CH1}

def in_view(env, R):
    """The lights seen from the camera. The key light stays where the
    cutscene cameras have it (front left, a little above), whichever way
    the model is turned; the sky/ground light follows the world's up."""
    e = dict(env)
    e['light_dir'] = env['light_dir'] / np.linalg.norm(env['light_dir'])
    e['hemi_dir'] = R @ (env['hemi_dir'] / np.linalg.norm(env['hemi_dir']))
    return e

def _wrap(i, n, mode):
    # texel index -> texel inside the texture, by the unit's wrap mode
    if mode == 'Mirror':
        i = i % (2 * n); return np.where(i >= n, 2 * n - 1 - i, i)
    if mode in ('ClampToEdge', 'ClampToBorder'):
        return np.clip(i, 0, n - 1)
    return i % n                                     # Repeat

def sample(t, u, v, wrap=('Repeat', 'Repeat'), border=None):
    """Bilinear look-up, with the hardware's wrap modes (Repeat, Mirror,
    ClampToEdge, ClampToBorder) per axis."""
    h, w = t.shape[:2]
    x = u * w - 0.5; y = v * h - 0.5
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    fx = (x - x0)[:, None]; fy = (y - y0)[:, None]
    xa, xb = _wrap(x0, w, wrap[0]), _wrap(x0 + 1, w, wrap[0])
    ya, yb = _wrap(y0, h, wrap[1]), _wrap(y0 + 1, h, wrap[1])
    out = t[ya, xa] * (1 - fx) * (1 - fy) + t[ya, xb] * fx * (1 - fy) + t[yb, xa] * (1 - fx) * fy + t[yb, xb] * fx * fy
    if border is not None and 'ClampToBorder' in wrap:
        outside = np.zeros(len(u), bool)
        if wrap[0] == 'ClampToBorder': outside |= (u < 0) | (u > 1)
        if wrap[1] == 'ClampToBorder': outside |= (v < 0) | (v > 1)
        out[outside] = np.asarray(border, float) * (255 if t.max() > 1.5 else 1)
    return out

def lut(table, x, absolute):
    # the hardware's 256-entry tables: |x| over 0..1 when the input is
    # absolute, otherwise a signed index (0..127 for 0..1, 128..255 for -1..0)
    t = np.asarray(table, np.float32)
    if absolute:
        f = np.clip(np.abs(x), 0, 1) * 255
    else:
        x = np.clip(x, -1, 1)
        f = np.where(x >= 0, x * 127, 256 + x * 128)
        f = np.clip(f, 0, 255)
    i = np.floor(f).astype(int); w = f - i
    return t[i] * (1 - w) + t[np.minimum(i + 1, 255)] * w

def coord_unit(m, unit):
    """Which texture coordinate (0..2) a texture unit reads."""
    if unit == 2 and m['texcoord_config'] in ('Config0110', 'Config0111', 'Config0112'):
        return 1
    return unit

def texcoord(m, c, uvs, n):
    """Texture coordinate c: from a UV set, or from the normal (sphere map)."""
    mapping = m['mapping'][c]
    if mapping == 'CameraSphereEnvMap':
        return n[:, 0] * 0.5 + 0.5, n[:, 1] * 0.5 + 0.5
    src = int(m['texture_sources'][c]) if c < len(m['texture_sources']) else c
    src = src if src in (0, 1, 2) else c
    u, v = uvs[src]
    return u, v

def fragment_colours(m, n, luts, env=ENV):
    """The lit primary (diffuse) and secondary (specular) colours."""
    k = len(n)
    V = np.array([0.0, 0.0, 1.0])
    d = env['eye_dir'] if ('eye_dir' in env and 'Eye' in m['name']) else env['light_dir']
    L = d / np.linalg.norm(d)
    Hh = (V + L); Hh /= np.linalg.norm(Hh)
    cos = dict(
        CosNormalHalf=n @ Hh, CosViewHalf=np.full(k, float(V @ Hh)), CosNormalView=n @ V,
        CosLightNormal=n @ L, CosLightSpot=np.full(k, -1.0), CosPhi=np.zeros(k))
    ff = m['fragment_flags']
    def table(name):
        sel, scale, _, ref = m['lut_input'][name]
        if ref and ref not in luts and '/' in ref:          # the material names it sampler/table
            a, b = ref.split('/', 1); ref = b + '/' + a
        if not ref or ref not in luts: return None
        val = lut(luts[ref]['table'], cos[sel], luts[ref]['absolute'] or m['lut_input'][name][2])
        return np.minimum(val * scale, 1) if scale != 1 else val
    ln = np.maximum(cos['CosLightNormal'], 0)
    spec0 = np.tile(np.array(m['specular0'][:3]), (k, 1))
    spec1 = np.tile(np.array(m['specular1'][:3]), (k, 1))
    if 'IsLUTDist0Enabled' in ff:
        d0 = table('dist0')
        if d0 is not None: spec0 = spec0 * d0[:, None]
    if 'IsLUTReflectionEnabled' in ff:
        r = [table(c) for c in ('reflec_r', 'reflec_g', 'reflec_b')]
        if all(x is not None for x in r): spec1 = np.stack(r, 1)
    if 'IsLUTDist1Enabled' in ff:
        d1 = table('dist1')
        if d1 is not None: spec1 = spec1 * d1[:, None]
    if 'IsLUTGeoFactorEnabled' in ff:
        if 'IsLUTGeoFactor0Enabled' in ff: spec0 = spec0 * ln[:, None]
        if 'IsLUTGeoFactor1Enabled' in ff: spec1 = spec1 * ln[:, None]
    amb = np.array(m['ambient'][:3]); dif = np.array(m['diffuse'][:3])
    pri = np.tile(np.array(m['emission'][:3]) + amb * env['scene_ambient'], (k, 1))
    pri = pri + amb * env['light_ambient'] + dif * env['light_diffuse'] * np.clip(ln, 0, 1)[:, None]
    sec = spec0 * env['light_specular0'] + spec1 * env['light_specular1']
    if 'IsClampHighLightEnabled' in ff: sec = sec * (cos['CosLightNormal'] >= 0)[:, None]
    pri_a = np.ones(k); sec_a = np.ones(k)
    fr = table('fresnel') if m['fresnel_selector'] != 'No' else None
    if fr is not None:
        if 'Pri' in m['fresnel_selector']: pri_a = fr
        if 'Sec' in m['fresnel_selector']: sec_a = fr
    return np.c_[np.clip(pri, 0, 1), pri_a], np.c_[np.clip(sec, 0, 1), sec_a]

def vertex_colour(m, n, vcol, env=ENV):
    """The vertex shader's colour output (PrimaryColor in the combiner)."""
    k = len(n)
    flags = m['flags']
    dif = np.array(m['diffuse'][:3])
    used = False
    rgb = np.zeros((k, 3)); a = np.full(k, m['diffuse'][3] if len(m['diffuse']) > 3 else 1.0)
    if m['has_color']:
        rgb = vcol[:, :3] * m['color_scale']; used = True
    if 'IsHemiSphereLightingEnabled' in flags:
        d = env['hemi_dir'] / np.linalg.norm(env['hemi_dir'])
        t = (n @ d) * 0.5 + 0.5
        hemi = env['hemi_ground'][None] + (env['hemi_sky'] - env['hemi_ground'])[None] * t[:, None]
        rgb = rgb + hemi * dif; used = True
    if not used:
        rgb = np.tile(dif, (k, 1)); a = np.full(k, 1.0)
    return np.c_[np.maximum(rgb, 0), a]

def _arg(src, op, S, const, prev, buf, alpha):
    v = {'PrimaryColor': S['primary'], 'FragmentPrimaryColor': S['fpri'], 'FragmentSecondaryColor': S['fsec'],
         'Texture0': S['tex'][0], 'Texture1': S['tex'][1], 'Texture2': S['tex'][2], 'Texture3': S['tex'][0],
         'PreviousBuffer': buf, 'Constant': const, 'Previous': prev}.get(src, S['primary'])
    if alpha:
        base = {'Alpha': v[:, 3], 'OneMinusAlpha': 1 - v[:, 3], 'Red': v[:, 0], 'OneMinusRed': 1 - v[:, 0],
                'Green': v[:, 1], 'OneMinusGreen': 1 - v[:, 1], 'Blue': v[:, 2], 'OneMinusBlue': 1 - v[:, 2]}
        return base.get(op, v[:, 3])
    base = {'Color': v[:, :3], 'OneMinusColor': 1 - v[:, :3], 'Alpha': np.repeat(v[:, 3:4], 3, 1),
            'OneMinusAlpha': np.repeat(1 - v[:, 3:4], 3, 1), 'Red': np.repeat(v[:, 0:1], 3, 1),
            'OneMinusRed': np.repeat(1 - v[:, 0:1], 3, 1), 'Green': np.repeat(v[:, 1:2], 3, 1),
            'OneMinusGreen': np.repeat(1 - v[:, 1:2], 3, 1), 'Blue': np.repeat(v[:, 2:3], 3, 1),
            'OneMinusBlue': np.repeat(1 - v[:, 2:3], 3, 1)}
    return base.get(op, v[:, :3])

def _combine(mode, a, b, c):
    if mode == 'Replace': return a
    if mode == 'Modulate': return a * b
    if mode == 'Add': return np.minimum(a + b, 1)
    if mode == 'AddSigned': return np.clip(a + b - 0.5, 0, 1)
    if mode == 'Interpolate': return b + (a - b) * c
    if mode == 'Subtract': return np.maximum(a - b, 0)
    if mode in ('DotProduct3Rgb', 'DotProduct3Rgba'):
        if a.ndim == 1: return np.minimum(a * b * 3, 1)
        d = np.minimum(((a - 0.5) * (b - 0.5)).sum(1, keepdims=True) * 4, 1)
        return np.repeat(np.maximum(d, 0), 3, 1)
    if mode == 'MultAdd': return np.minimum(a * b + c, 1)
    if mode == 'AddMult': return np.minimum(a + b, 1) * c
    return a

def combiner(m, S):
    """The six combiner stages. S: the sources (arrays (k, 4))."""
    k = len(S['primary'])
    prev = np.zeros((k, 4)); buf = np.tile(np.array(m['buffer_color'], float), (k, 1)); out = prev
    for st in m['stages']:
        const = np.tile(np.array(st['constant'], float), (k, 1))
        new = prev.copy()
        if not st['color_pass']:
            a, b, c = [_arg(st['color_src'][i], st['color_op'][i], S, const, prev, buf, False) for i in range(3)]
            new[:, :3] = np.minimum(_combine(st['color_mode'], a, b, c) * st['color_scale'], 1)
        if not st['alpha_pass']:
            a, b, c = [_arg(st['alpha_src'][i], st['alpha_op'][i], S, const, prev, buf, True) for i in range(3)]
            new[:, 3] = np.minimum(_combine(st['alpha_mode'], a, b, c) * st['alpha_scale'], 1)
        # the buffer keeps the previous stage's result, for the next stages
        nb = buf.copy()
        if st['update_color_buffer']: nb[:, :3] = prev[:, :3]
        if st['update_alpha_buffer']: nb[:, 3] = prev[:, 3]
        buf = nb
        if not (st['color_pass'] and st['alpha_pass']): prev = new
    return np.clip(prev, 0, 1)

def shade(m, n, uvs, vcol, textures, luts, env=ENV, need_light=True):
    """RGBA of k pixels of one material. n: view-space normals (k, 3);
    uvs: three (u, v) pairs; vcol: vertex colours (k, 4); textures: name -> array."""
    k = len(n)
    tex = []
    for unit in range(3):
        name = m['textures'][unit]
        if name and name in textures:
            u, v = texcoord(m, coord_unit(m, unit), uvs, n)
            wrap = m.get('wrap', [['Repeat', 'Repeat']] * 3)[unit]
            border = m.get('border', [None] * 3)[unit]
            tex.append(sample(textures[name], u, v, wrap, border))
        else:
            tex.append(np.ones((k, 4)))
    S = dict(tex=tex, primary=vertex_colour(m, n, vcol, env))
    if need_light and 'IsFragmentLightingEnabled' in m['flags']:
        S['fpri'], S['fsec'] = fragment_colours(m, n, luts, env)
    else:
        S['fpri'] = np.ones((k, 4)); S['fsec'] = np.c_[np.zeros((k, 3)), np.ones(k)]
    return combiner(m, S)

def passes_alpha_test(m, a):
    t = m.get('alpha_test')
    if not t: return np.ones(len(a), bool)
    f, ref = t
    return {'Never': a < -1, 'Always': a > -1, 'Equal': a == ref, 'Notequal': a != ref, 'Less': a < ref,
            'Lequal': a <= ref, 'Greater': a > ref, 'Gequal': a >= ref}.get(f, a > ref)

BLEND = {'Zero': 0, 'One': 1}
def blend_factor(name, src, dst):
    if name == 'Zero': return np.zeros((len(src), 1))
    if name == 'One': return np.ones((len(src), 1))
    if name == 'SourceAlpha': return src[:, 3:4]
    if name == 'OneMinusSourceAlpha': return 1 - src[:, 3:4]
    if name == 'DestinationAlpha': return dst[:, 3:4]
    if name == 'OneMinusDestinationAlpha': return 1 - dst[:, 3:4]
    if name == 'SourceColor': return src[:, :3]
    if name == 'OneMinusSourceColor': return 1 - src[:, :3]
    if name == 'DestinationColor': return dst[:, :3]
    if name == 'OneMinusDestinationColor': return 1 - dst[:, :3]
    return np.ones((len(src), 1))
