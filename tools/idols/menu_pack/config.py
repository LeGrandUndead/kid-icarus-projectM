"""Where the build's inputs are, and the design's fixed numbers.

Every input comes from the work folder (IDOLS_WORK), made from the player's
ROM by the other tools in tools/idols:
    menu-pc-trial/            the game's menu art at 4x (texture packs)
    redraw/all/<menu>/        the same art at its original size, by name
    rom/native-ui/ui-sources.tsv
                              which texture file each art name is
    redraw/bg/<mode>.png      Together, Vault, Options: their stages, rendered
    stages/tex/               stage textures (Solo's sky is built from them)
    fx/<effect>/              particle images from the game's effect files
    mock/Montserrat-Regular.otf
                              the font the 3DS system font is drawn from
    render/frames/            the characters' renders (render/promo.py,
                              render/solo_loop.py...)
"""
import os

WORK = os.environ.get('IDOLS_WORK', 'work')

MENU_ART_4X = f'{WORK}/menu-pc-trial'
MENU_ART = f'{WORK}/redraw/all'
UI_SOURCES = f'{WORK}/rom/native-ui/ui-sources.tsv'
STAGE_RENDERS = f'{WORK}/redraw/bg'
STAGE_TEXTURES = f'{WORK}/stages/tex'
EFFECTS = f'{WORK}/fx'
GAME_FONT = f'{WORK}/mock/Montserrat-Regular.otf'
RENDERS = f'{WORK}/render/frames'

# The design: 1920x1080 pixels; the game's units (240 to the screen's height)
W, H = 1920, 1080
U = H / 240
BAND_Y = 905                     # top of the black ground band
GOLD = (255, 208, 84)            # the selection's colour, nothing else
BLACK = (12, 8, 14)              # the ink

# Tuned by measuring (claude/DESIGN_ANIMATION_BIBLE.md, section 15)
TUNE = dict(glow=0.30, rays=0.14, wrap=0.35)
