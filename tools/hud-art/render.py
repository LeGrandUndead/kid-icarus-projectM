import sys, os
from playwright.sync_api import sync_playwright
here = os.path.dirname(os.path.abspath(__file__))
jobs = [(s, sc, 'play') for s in 'ABC' for sc in ('air', 'land')] + [(s, 'air', 'pause') for s in 'ABC']
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium' if os.path.exists('/opt/pw-browsers/chromium') else None,
                          args=['--allow-file-access-from-files'])
    pg = b.new_page(viewport={'width': 1920, 'height': 1080})
    for s, sc, mode in jobs:
        pg.goto(f'file://{here}/hud.html?style={s}&scene={sc}&mode={mode}')
        pg.wait_for_timeout(600)
        pg.screenshot(path=f'{here}/out/{s}-{sc if mode=="play" else "pause"}.png')
    b.close()
