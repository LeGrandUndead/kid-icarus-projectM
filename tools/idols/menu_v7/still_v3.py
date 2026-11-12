# One still per mode with layout v3, to judge the layout, font and panels
# before rendering videos.  python3 still_v3.py  ->  check/v3_<mode>.png
lib={'__name__':'lib'}; exec(open('menu_anim.py').read(),lib)   # helpers only, not its own video
g=globals(); g.update({k:v for k,v in lib.items() if not k.startswith('__')})
exec(open('ui_v3.py').read())
sys.path.insert(0, S + '/render')

def viridi():
    if os.path.exists('check/_viridi.png'): return Image.open('check/_viridi.png')
    # Viridi's idol, full body, one frame of her Wait (rendered here)
    import idol, cast
    p = cast.pose('V12', [('DolNatur00Wait', 40, 1.0, None)])
    im = idol.render('V12', 1400, math.radians(-20), math.radians(3), pose=p, ss=2).convert('RGBA'); im.save('check/_viridi.png'); return im

SHOTS = {
    # mode index, character image, centre x, feet y, height, close-up?
    'together': (1, lambda: Image.open(f'{R}/together/0100.png').convert('RGBA'), 1460, H + 90, 880, True),
    'vault':    (2, lambda: Image.open(f'{R}/vault/0100.png').convert('RGBA'), 1420, H * 0.85, H * 0.78, False),
    'options':  (3, viridi, 1420, H * 0.85, H * 0.74, False),
}
CTRL3 = controls_v3()
for name, (i, get, cx, feet, height, close) in SHOTS.items():
    m = MODES[i]; t = 2.0
    page = background(m, i)
    put(page, emblem(m), W * 0.72, H * 0.5, anchor='c')
    r = rays_layer().crop((int(750 - W * 0.35), int(750 - H * 0.225), int(750 - W * 0.35) + W // 2, int(750 - H * 0.225) + H // 2)).resize((W, H), Image.BILINEAR)
    page.alpha_composite(r)
    backlight(page, cx, H * 0.45, 430, m['color'])
    motes(page, m, t, i)
    if not close:
        ground(page, cx, feet - 6, 420, m['color'])
    place(page, get(), cx, feet, height)
    if close:
        foreground_fade(page, m['color'])
    page.alpha_composite(header_v3(m))
    page.alpha_composite(ui_(i, t))
    page.alpha_composite(CTRL3)
    page.convert('RGB').save(f'check/v3_{name}.png')
    print(name)
