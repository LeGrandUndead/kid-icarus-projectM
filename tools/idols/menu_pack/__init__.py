"""The main menu's scene pack: every picture the game's PC main menu draws
(tools/zakuro/crates/zakuro/src/pc_menus/scene), made once from the
player's own ROM data. Nothing it makes is committed: the pack stays on the
player's machine (build/texture-work/menu-pc/scene-040).

    IDOLS_WORK=<work folder> python3 -m menu_pack <out folder> [--modes 0123]

(run from tools/idols). The work folder holds what was extracted from the
ROM and rendered (see config.py for each input).

The parts, in the order the build uses them:
    config      the inputs' folders, the design's size, tuning
    images      small picture helpers (fit, mask, glow, colour spaces)
    game_art    the game's own menu art and particle images
    modes       the four modes: colours, stage palettes, captions, light
    layers      the scene's layers: paper, emblems, stages, rays, heading,
                caption, ground band, controls, ink ornaments, particles
    relight     relighting a rendered character for its stage
    characters  each mode's character frames: framed, relit, tied into the
                stage, encoded (JPEG colour + PNG coverage)
    frame_pak   each character's frames packed into one file
    manifest    the manifest the game reads (TOML)
    build       all of it, into one folder
"""
