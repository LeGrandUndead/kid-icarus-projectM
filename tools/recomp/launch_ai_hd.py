"""Launch only the isolated AI-HD edition, with no shared writable profile."""
from pathlib import Path
import argparse, json, os, subprocess

def validate_art_policy(root):
    policy=json.loads((root/'art-policy.json').read_text())
    for name in policy['original_only']:
        if Path(name).name!=name: raise ValueError('Invalid artwork policy filename')
        if (root/'textures'/name).exists():
            raise ValueError(f'Character artwork must remain original: {name}')
    approved=set(policy['approved_for_ai'])
    for texture in (root/'textures').glob('*.png'):
        if texture.name not in approved:
            raise ValueError(f'Unreviewed texture replacement: {texture.name}')

def configuration(root):
    root=root.resolve()
    env={k:v for k,v in os.environ.items() if not k.startswith(('KIU_','ZAKURO_'))}
    env.update(APPDATA=str(root/'profile/roaming'),LOCALAPPDATA=str(root/'profile/local'),
        KIU_TEXTURE_PACK=str(root/'textures'),KIU_EXPERIMENTAL_HUD='1',
        KIU_EXPERIMENTAL_WIDE='1',KIU_EXPERIMENTAL_AIR='1',KIU_PC_DISPLAY='1080p',
        KIU_PC_CONTROLS='1',KIU_RELATIVE_CAMERA='1',KIU_MOUSE_SENSITIVITY='0.55',KIU_WALK_STRENGTH='0.6')
    command=[str(root/'runtime/zakuro-ai-hd.exe'),str(root/'game.3ds'),
        '--data',str(root/'data'),'--recompiled',str(root/'runtime/0004000000030100.dll'),'--resolution','5']
    return command,env

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--headless',type=int,default=0)
    parser.add_argument('--capture',action='store_true',help='F8 captures more local textures into this edition')
    parser.add_argument('--previous-textures',action='store_true',help='Use the preserved pack from before the stage expansion')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    if (root/'DISABLED.txt').exists():
        raise SystemExit('AI texture experiments are retired. Use Launch-KIU.cmd for original textures and widescreen.')
    command,env=configuration(root)
    for directory in ('profile/roaming','profile/local','logs'): (root/directory).mkdir(parents=True,exist_ok=True)
    artwork=root/'rollback-before-stage-expansion' if args.previous_textures else root
    if not (artwork/'textures/pack.json').is_file(): raise SystemExit('Selected AI texture pack has not finished validation.')
    validate_art_policy(artwork)
    env['KIU_TEXTURE_PACK']=str(artwork/'textures')
    if args.headless: command+=['--headless',str(args.headless),'--mute']
    if args.capture:
        from datetime import datetime
        capture=root/'captures'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        capture.mkdir(parents=True)
        env.update(KIU_RENDER_CAPTURE=str(capture/'capture'),KIU_RENDER_CAPTURE_WAIT='1',
                   KIU_TEXTURE_TRACE=str(capture/'texture-states.csv'))
        print('Press F8 in a new area to capture original texture sources locally.',flush=True)
    print('AI-HD EDITION: isolated executable, textures, settings and saves. Tab: bottom screen; F2: aim; F11: fullscreen.',flush=True)
    with (root/'logs/latest.log').open('w') as log:
        return subprocess.call(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)

if __name__=='__main__': raise SystemExit(main())
