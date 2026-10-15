"""Run an isolated camera replay; never reads or writes the live save directory."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--save-snapshot', type=Path, required=True)
    parser.add_argument('--frames', type=int, default=2200)
    parser.add_argument('--dump-at', default='1200,1500,1800,2200')
    parser.add_argument('--relative', action='store_true')
    parser.add_argument('--experimental-air', action='store_true')
    parser.add_argument('--experimental-wide', action='store_true')
    parser.add_argument('--experimental-hud', action='store_true')
    parser.add_argument('--projection-trace', action='store_true')
    parser.add_argument('--texture-pack', type=Path)
    parser.add_argument('--texture-filter', choices=('original','cubic'), default='original')
    parser.add_argument('--experimental-runtime', action='store_true')
    parser.add_argument('--runtime', type=Path, help='explicit isolated probe executable')
    parser.add_argument('--dialogue-sources', type=Path, help='original portrait hash catalog')
    parser.add_argument('--camera-scale', type=float, default=1.0)
    parser.add_argument('--resolution', type=int, choices=range(1, 9), default=1)
    parser.add_argument('--shared-font', type=Path, help='explicit shared font copied into the isolated replay')
    parser.add_argument('--pipeline-cache', type=Path, help='seed an isolated warm-cache performance test')
    parser.add_argument('--rasterizer', choices=('hardware', 'software'), default='hardware')
    parser.add_argument('--render-capture', action='store_true')
    parser.add_argument('--cpu-shaders', action='store_true', help='isolate host vertex shading from shared raster state')
    parser.add_argument('--ignore-depth-test', action='store_true', help='diagnostic only: isolate depth rejection artifacts')
    parser.add_argument('--draw-frame', type=int, help='offline per-draw image capture for one frame')
    parser.add_argument('--watch', help='hexadecimal guest address to watch')
    parser.add_argument('--memory', help='guest memory dumps: hex-address,decimal-size;...')
    args = parser.parse_args()
    import math
    if not math.isfinite(args.camera_scale) or not 0.75 <= args.camera_scale <= 1.0:
        parser.error('camera scale must be between 0.75 and 1.0')
    if args.camera_scale != 1.0 and (not args.dialogue_sources or not args.experimental_wide):
        parser.error('camera scale requires dialogue sources and the existing wide projection')
    if not args.name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in args.name):
        parser.error('name must contain only lowercase letters, digits, hyphens or underscores')
    inputs = args.inputs.resolve()
    snapshot = args.save_snapshot.resolve()
    recorded_font = snapshot.parent / 'sysdata/shared_font.bin'
    if args.shared_font is None and recorded_font.is_file():
        args.shared_font = recorded_font
    if not (inputs / 'input.replay').is_file() or not snapshot.is_dir():
        parser.error('replay and initial save snapshot must exist')
    if args.relative and not (inputs / 'input.csv').is_file():
        parser.error('relative replay also requires the raw input.csv')
    if args.shared_font and not args.shared_font.is_file():
        parser.error('shared font must exist')
    if args.pipeline_cache and not args.pipeline_cache.is_file():
        parser.error('pipeline cache must exist')
    output = ROOT / 'build/evaluation' / args.name
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(snapshot, output / 'user')
    if args.shared_font:
        (output / 'sysdata').mkdir()
        shutil.copyfile(args.shared_font, output / 'sysdata/shared_font.bin')
    cache_sha = None
    if args.pipeline_cache:
        cache = output / 'local/zakuro/pipelines.bin'
        cache.parent.mkdir(parents=True)
        shutil.copyfile(args.pipeline_cache, cache)
        cache_sha = sha(cache)
    runtime = ROOT / 'tools/zakuro/target/release/examples/boot.exe'
    if args.experimental_runtime:
        runtime = ROOT / 'tools/zakuro/target/release/examples/boot-experimental.exe'
    if args.runtime: runtime = args.runtime.resolve()
    library = ROOT / 'build/kiu-aot-o2/0004000000030100.dll'
    env = {k: v for k, v in os.environ.items() if not k.startswith(('KIU_', 'ZAKURO_'))}
    env['PATH'] = str(ROOT / 'tools/toolchains/winlibs/mingw64/bin') + os.pathsep + env.get('PATH', '')
    env.update(ZAKURO_RECOMPILED=str(library), ZAKURO_REPLAY=str(inputs / 'input.replay'),
               ZAKURO_RASTERIZER=args.rasterizer, ZAKURO_DUMP_AT=args.dump_at,
               ZAKURO_RESOLUTION=str(args.resolution),
               TEMP=str(output), TMP=str(output), APPDATA=str(output / 'roaming'),
               LOCALAPPDATA=str(output / 'local'))
    if args.texture_filter == 'cubic':
        env['KIU_TEXTURE_FILTER'] = 'cubic'
    if args.dialogue_sources:
        env['KIU_NATIVE_DIALOGUE'] = str(args.dialogue_sources.resolve())
        env['KIU_GAMEPLAY_CAMERA_SCALE'] = str(args.camera_scale)
    if args.texture_pack:
        env['KIU_TEXTURE_PACK'] = str(args.texture_pack.resolve())
    if args.projection_trace:
        env['KIU_PROJECTION_TRACE'] = str(output / 'projections.csv')
    if args.experimental_hud:
        env['KIU_EXPERIMENTAL_HUD'] = '1'
    if args.experimental_wide:
        env['KIU_EXPERIMENTAL_WIDE'] = '1'
    if args.experimental_air:
        env['KIU_EXPERIMENTAL_AIR'] = '1'
    if args.relative:
        env['KIU_MOUSE_TRACE_REPLAY'] = str(inputs / 'input.csv')
        env['KIU_MOUSE_SENSITIVITY'] = '0.55'
    if args.render_capture:
        env['KIU_RENDER_CAPTURE'] = str(output / 'capture')
        env['KIU_TEXTURE_TRACE'] = str(output / 'texture-states.csv')
    if args.cpu_shaders:
        env['ZAKURO_CPU_SHADERS'] = '1'
    if args.ignore_depth_test:
        env['KIU_DIAGNOSTIC_IGNORE_DEPTH'] = '1'
    if args.draw_frame is not None:
        env['KIU_DRAW_FRAME'] = str(args.draw_frame)
        env['KIU_DRAW_CAPTURE'] = str(output / 'draws')
    if args.watch:
        int(args.watch, 16)
        env.update(KIU_TRACE_TOUCH_READER='1', KIU_TRACE_TOUCH_STATE=args.watch)
    if args.memory:
        env.update(ZAKURO_DUMP_MEM=args.memory, ZAKURO_DUMP_MEM_AT='1')
    with (output / 'run.log').open('w') as log:
        result = subprocess.run([str(runtime), str(ROOT / 'Kid Icarus - Uprising (USA) (En,Fr,Es).3ds'),
                                 str(args.frames)], cwd=output, env=env, stdout=log, stderr=subprocess.STDOUT)
    log_text = (output / 'run.log').read_text()
    completed = re.search(r'outcome:\s+Completed after (\d+) frames', log_text)
    valid = result.returncode == 0 and completed is not None and int(completed[1]) == args.frames
    dimensions = {}
    for path in output.glob('*.ppm'):
        with path.open('rb') as stream:
            if stream.readline().strip() != b'P6':
                raise ValueError(f'Unexpected image format: {path}')
            dimensions[path.name] = [int(n) for n in stream.readline().split()]
    report = dict(texture_filter=args.texture_filter, texture_pack=str(args.texture_pack.resolve()) if args.texture_pack else None, experimental_hud=args.experimental_hud, experimental_wide=args.experimental_wide, experimental_air=args.experimental_air, experimental_runtime=args.experimental_runtime, exit_code=result.returncode, completed=valid, frames=args.frames, relative=args.relative,
                  resolution_scale=args.resolution,
                  shared_font_sha256=sha(output / 'sysdata/shared_font.bin') if args.shared_font else None,
                  initial_pipeline_cache_sha256=cache_sha,
                  rasterizer=args.rasterizer,
                  render_capture=args.render_capture,
                  cpu_shaders=args.cpu_shaders, ignore_depth_test=args.ignore_depth_test,
                  draw_frame=args.draw_frame,
                  screen_dimensions=dimensions,
                  metrics=[line for line in log_text.splitlines()
                           if line.startswith(('outcome:', 'frame times:', 'gpu:'))],
                  runtime_sha256=sha(runtime), library_sha256=sha(library),
                  replay_sha256=sha(inputs / 'input.replay'),
                  screens={p.name: sha(p) for p in output.glob('*.ppm')})
    if args.relative:
        report['mouse_sha256'] = sha(inputs / 'input.csv')
    report['camera_scale'] = args.camera_scale
    report['dialogue_sources_sha256'] = sha(args.dialogue_sources) if args.dialogue_sources else None
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(output)
    for line in log_text.splitlines():
        if line.startswith(('outcome:', 'frame times:', 'gpu:', 'KIU relative mouse publications:')) or 'touch reader:' in line:
            print(line)
    return result.returncode or (0 if valid else 1)


if __name__ == '__main__':
    raise SystemExit(main())
