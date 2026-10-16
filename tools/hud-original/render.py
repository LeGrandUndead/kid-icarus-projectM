import os,sys
from playwright.sync_api import sync_playwright
here=os.path.dirname(os.path.abspath(__file__))
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium',args=['--allow-file-access-from-files'])
    pg=b.new_page(viewport={'width':1920,'height':1080})
    for sc in ['air','land']:
        pg.goto(f'file://{here}/hud.html?scene={sc}'); pg.wait_for_timeout(700)
        pg.screenshot(path=f'{here}/out-{sc}.png')
    b.close()
