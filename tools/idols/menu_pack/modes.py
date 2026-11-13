"""The four modes of the main menu, in the game's order (its choices 0-3):
their colours, word art, caption, stage palette and character light."""
from .images import mix_white

MODES = [
    dict(name='Solo', color=(224, 120, 150), emblem=('040', 'MenCmnBgUp0007Sg'), head=(0.0, 0.185),
         caption='The story of Pit, our angelic hero.'),
    dict(name='Together', color=(232, 140, 70), emblem=('040', 'MenCmnBgUp0002Ml'), head=(0.19, 0.386),
         caption='Battle it out wirelessly with others!'),
    dict(name='Vault', color=(96, 176, 104), emblem=('040', 'MenCmnBgUp0007Cl'), head=(0.588, 0.785),
         caption="View content you've unlocked."),
    dict(name='Options', color=(160, 112, 206), emblem=('040', 'MenCmnBgUp0007Op'), head=(0.79, 0.985),
         caption='Adjust settings to your liking.'),
]
"""`emblem`: the mode's watermark (menu archive, art name); `head`: where its
heading is in the word-art sheet (fractions of its height)."""

PALETTE = {
    0: dict(deep=(36, 22, 64), mid=(132, 70, 112), high=(250, 178, 150), key=(255, 214, 180), at=(1080, 90)),
    1: dict(deep=(26, 14, 18), mid=(88, 44, 34), high=(176, 112, 66), key=(255, 210, 140), at=(1180, 160)),
    2: dict(deep=(8, 22, 26), mid=(30, 66, 62), high=(104, 150, 128), key=(210, 255, 230), at=(1150, 120)),
    3: dict(deep=(18, 10, 32), mid=(60, 38, 92), high=(134, 108, 172), key=(232, 210, 255), at=(1150, 120)),
}
"""Per mode: the stage's shadow, middle and light colours, the key light's
colour, and where the key light is (upper left of the window, matching the
light of the renders)."""

STAGE_STOPS = {
    0: [(0.20, 0.07, 285), (0.37, 0.11, 340), (0.57, 0.12, 30), (0.76, 0.10, 70)],     # indigo, rose, coral, gold
    1: [(0.18, 0.06, 285), (0.34, 0.10, 35), (0.54, 0.13, 60), (0.74, 0.10, 85)],      # indigo, ember, amber, cream
    2: [(0.18, 0.06, 245), (0.35, 0.08, 195), (0.55, 0.11, 155), (0.76, 0.08, 115)],   # navy, teal, green, pale lime
    3: [(0.18, 0.07, 270), (0.35, 0.11, 305), (0.55, 0.12, 345), (0.74, 0.07, 20)],    # blue-violet, purple, pink, blush
}
"""Per mode: the stage's gradient map, OKLCH (lightness, chroma, hue) stops
from its shadows to its lights: cool shadows, warm lights."""


def light(mode):
    """How a mode's character is relit for its stage (relight.relight): the
    key light's colour, the shadow and rim from the stage's palette, a
    little bounce from below; the shading blurred so it draws no hard edges
    across faces; Together's two fighters a little darker in shadow."""
    p = PALETTE[mode]
    return dict(key=(-0.7, 0.5, 0.6), key_col=mix_white(p['key'], 0.45), dark=0.6 if mode == 1 else 0.5,
                shadow=mix_white(p['mid'], 0.35), rim=tuple(x / 255 for x in p['high']), rim_strength=1.8,
                bounce=tuple(x / 255 for x in p['mid']), bounce_strength=0.35,
                skin_shadow=None, skin_flat=0.0, soft=6)
