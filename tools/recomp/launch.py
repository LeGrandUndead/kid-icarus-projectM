"""Kid Icarus: Uprising native launcher (the PC interface runtime).

Starts tools/zakuro/target/release/zakuro-pc-interface.exe on the ROM with the
recompiled library, the PC profile (build/user-data/gameplay-preview: its own
saves, settings and pipeline cache) and the PC interface: the original HUD art
over gameplay, the lower screen on Tab, PC controls. Diagnostics are opt-in
flags; see doc/DIAGNOSTICS.md.

The older experimental / single-screen / dialogue-preview executables were the
same program under other names and profiles; they were removed on October 28
(git history keeps them). Their profiles and saves under build/user-data are
left where they are.
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/rom"))
from audit_executable import audit  # noqa: E402

EXPECTED_CODE_SHA256 = "2718aa2077a29560208c4e499288e5fecc4446d7adec95efb91ebf1b19eda679"
BUILD_DIRS = {"debug": ROOT / "build/kiu-aot-debug", "o2": ROOT / "build/kiu-aot-o2"}
ROM = ROOT / "Kid Icarus - Uprising (USA) (En,Fr,Es).3ds"
RUNTIME = ROOT / "tools/zakuro/target/release/zakuro-pc-interface.exe"
PROFILE = ROOT / "build/user-data/gameplay-preview"
# where the profile's saves and settings were first copied from
ORIGINAL_SAVES = ROOT / "build/user-data/kiu"
ORIGINAL_SETTINGS = ROOT / "build/user-data/roaming/zakuro/settings.toml"
ORIGINAL_CACHE = ROOT / "build/user-data/local/zakuro/pipelines.bin"
# variables this launcher owns: never inherited from a parent terminal
OWNED_ENV = (
    "KIU_TEXTURE_FILTER", "KIU_TEXTURE_PACK", "KIU_SINGLE_SCREEN", "KIU_NATIVE_DIALOGUE",
    "KIU_GAMEPLAY_CAMERA_SCALE", "KIU_NATIVE_UI", "KIU_NATIVE_HUD", "KIU_UI_CENSUS",
    "KIU_RAM_SNAPSHOT", "KIU_HUD_PACK", "KIU_60FPS", "KIU_PROJECTION_TRACE", "KIU_EXPERIMENTAL_HUD",
    "KIU_RENDER_CAPTURE_WAIT", "KIU_DRAW_FRAME", "KIU_DRAW_CAPTURE", "KIU_DIAGNOSTIC_IGNORE_DEPTH",
    "KIU_EXPERIMENTAL_AIR", "KIU_EXPERIMENTAL_WIDE", "KIU_PC_DISPLAY", "KIU_PC_CONTROLS",
    "KIU_INPUT_TRACE", "KIU_MOUSE_MODEL", "KIU_CONTROL_PROFILE", "KIU_MOUSE_ACCELERATION",
    "KIU_RELATIVE_CAMERA", "ZAKURO_RECORD", "KIU_TEXTURE_TRACE", "ZAKURO_LEGACY_TEXTURE_SAMPLING",
    "KIU_RENDER_CAPTURE", "ZAKURO_REPLAY", "KIU_MOUSE_SENSITIVITY", "KIU_WALK_STRENGTH",
    "RUST_LOG", "ZAKURO_GPU_TIMES",
)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_library(library: Path) -> None:
    result = library.parent / "build-result.json"
    if not library.is_file(): raise ValueError(f"Native library does not exist: {library}")
    if not result.is_file(): raise ValueError(f"Missing build metadata: {result}")
    metadata = json.loads(result.read_text(encoding="utf-8"))
    actual = digest(library)
    if metadata.get("sha256") != actual:
        raise ValueError(f"Native library differs from build-result.json ({actual})")


def choose_library(mode: str, explicit: Path | None):
    if explicit is not None:
        library = explicit.resolve(); validate_library(library); return library, "custom"
    if mode == "auto":
        for name in ("o2", "debug"):
            library = BUILD_DIRS[name] / "0004000000030100.dll"
            if library.is_file(): validate_library(library); return library, name
        raise ValueError("No AOT build found")
    library = BUILD_DIRS[mode] / "0004000000030100.dll"
    validate_library(library); return library, mode


def stamped(folder: str, fmt: str = "%Y%m%d-%H%M%S-%f") -> Path:
    path = ROOT / folder / datetime.now().strftime(fmt)
    path.mkdir(parents=True)
    return path


def arguments():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    look = ap.add_argument_group("presentation")
    look.add_argument("--hud-art", choices=("pc", "original"), default="pc", help="pc = HUD reconstructed from your ROM (build/texture-work/hud-pc), original = ROM resolution")
    look.add_argument("--original-hud-resolution", action="store_true", help="same as --hud-art original")
    look.add_argument("--no-native-hud", action="store_true", help="keep only the portraits over gameplay, for comparison")
    look.add_argument("--texture-filter", choices=("original", "cubic"), default="original", help="magnification filtering of the original art")
    look.add_argument("--texture-pack", type=Path, help="folder of content-addressed HD replacement PNGs (opt-in)")
    look.add_argument("--camera-scale", type=float, help="lens scale, 0.75 to 1.0 (1 = the original view)")
    look.add_argument("--original-aspect", action="store_true", help="no wider projection")
    look.add_argument("--original-hud-sampling", action="store_true", help="no HUD atlas-edge correction")
    look.add_argument("--resolution", type=int, choices=range(1, 9), help="internal 3D scale: 3=1200x720, 5=2000x1200, 8=3200x1920")
    look.add_argument("--scale", type=int)
    look.add_argument("--display", choices=("1080p",), default="1080p", help="kept for old shortcuts; the PC interface is always 1080p")
    rate = look.add_mutually_exclusive_group()
    rate.add_argument("--sixty-fps", action="store_true", help="60 FPS mode for this run (Settings > Graphics keeps the saved choice)")
    rate.add_argument("--thirty-fps", action="store_true", help="original 30 FPS for this run")

    controls = ap.add_argument_group("controls")
    controls.add_argument("--legacy-controls", action="store_true", help="no PC control layer")
    # The relative camera and flight aim work by writing into the game's own
    # camera memory every frame. They are opt-in until the chapter 9 white
    # screen is cleared of them (October 28): the default writes nothing into
    # game state, it only presses the game's own inputs.
    controls.add_argument("--relative-camera", action="store_true", default=False, help="experimental: direct relative mouse for the land camera (writes the game's camera memory)")
    controls.add_argument("--original-land-camera", dest="relative_camera", action="store_false", help="bounded land camera (the default)")
    controls.add_argument("--relative-flight-aim", dest="original_flight_aim", action="store_false", default=True, help="experimental: relative flight aim (writes the game's camera memory)")
    controls.add_argument("--original-flight-aim", dest="original_flight_aim", action="store_true", help="bounded flight aim (the default)")
    controls.add_argument("--mouse-sensitivity", type=float, default=0.55)
    controls.add_argument("--walk-strength", type=float, default=0.60, help="Alt+WASD analog strength")

    run = ap.add_argument_group("runtime")
    run.add_argument("--build", choices=("auto", "debug", "o2"), default="auto")
    run.add_argument("--library", type=Path)
    run.add_argument("--interpreter", action="store_true", help="no recompiled library (slow baseline)")
    run.add_argument("--software", action="store_true", help="software renderer")
    run.add_argument("--headless", type=int, default=0, help="run this many frames without a window")
    run.add_argument("--profile", action="store_true", help="guest-PC sampling profiler")
    run.add_argument("--replay", type=Path, help="test: play back a recorded input file on copied saves, never the real ones")
    run.add_argument("--replay-save", type=Path, help="with --replay: folder holding the recording's starting 'user' saves (and optionally 'sysdata')")

    diag = ap.add_argument_group("diagnostics (doc/DIAGNOSTICS.md)")
    diag.add_argument("--diagnostics", action="store_true", help="log frame pacing and GPU pipeline/timing data")
    diag.add_argument("--render-capture", action="store_true", help="F8 captures two frames draw by draw")
    diag.add_argument("--texture-trace", action="store_true", help="record unique texture filtering/LOD states")
    diag.add_argument("--legacy-texture-sampling", action="store_true", help="A/B: the old base-level sampler")
    diag.add_argument("--input-trace", action="store_true", help="save raw mouse and final guest input CSV")
    diag.add_argument("--record-input", action="store_true", help="record guest input for deterministic replay")
    diag.add_argument("--ui-census", action="store_true", help="record catalogued lower-screen draws to a CSV")
    diag.add_argument("--ram-snapshots", action="store_true", help="F7 saves game memory to build/ram-snapshots/<time>")
    # accepted so old shortcuts keep working; the PC interface is the only mode now
    for legacy in ("--pc-interface", "--experimental", "--single-screen", "--dialogue-preview"):
        ap.add_argument(legacy, action="store_true", help=argparse.SUPPRESS)
    return ap


def main() -> int:
    ap = arguments()
    args = ap.parse_args()
    if args.camera_scale is not None and (not math.isfinite(args.camera_scale) or not 0.75 <= args.camera_scale <= 1.0):
        ap.error("camera scale must be finite and between 0.75 and 1.0")
    for name, value, lo, hi in (("mouse sensitivity", args.mouse_sensitivity, 0.05, 4.0),
                                ("walk strength", args.walk_strength, 0.51, 0.90)):
        if not math.isfinite(value) or not lo <= value <= hi:
            ap.error(f"{name} must be finite and between {lo} and {hi}")
    if args.texture_pack and not args.texture_pack.is_dir(): ap.error("Texture pack folder does not exist")
    if not RUNTIME.is_file(): ap.error(f"Runtime missing: {RUNTIME} (run Build-And-Run.cmd)")
    if not ROM.is_file(): ap.error(f"ROM missing: {ROM}")

    library = None; build_name = "interpreter"
    if not args.interpreter:
        report = audit(ROOT / "ROM/gameFiles", ROM)
        if report["code_sha256"] != EXPECTED_CODE_SHA256:
            ap.error("This native build targets a different executable revision")
        try: library, build_name = choose_library(args.build, args.library)
        except ValueError as exc: ap.error(str(exc))

    env = os.environ.copy()
    for name in OWNED_ENV:
        env.pop(name, None)
    env["PATH"] = str(ROOT / "tools/toolchains/winlibs/mingw64/bin") + os.pathsep + env.get("PATH", "")

    # the PC interface: original UI art catalogue, HUD art, one screen
    sources = ROOT / "build/native-ui/ui-sources.tsv"
    if not sources.is_file(): ap.error("Original UI catalog missing; run: python tools/recomp/prepare_native_ui_sources.py")
    env["KIU_NATIVE_UI"] = str(sources)
    if args.no_native_hud: env["KIU_NATIVE_HUD"] = "0"
    art = "original" if args.original_hud_resolution else args.hud_art
    hud_pack = ROOT / "build/texture-work/hud-pc"
    if art == "pc" and hud_pack.is_dir():
        env["KIU_HUD_PACK"] = str(hud_pack.resolve())
        print("HUD art: hud-pc, reconstructed from your ROM (--hud-art original to compare).", flush=True)
    if args.camera_scale is not None or args.original_aspect:
        env["KIU_GAMEPLAY_CAMERA_SCALE"] = str(args.camera_scale if args.camera_scale is not None else 1.0)
    env["KIU_SINGLE_SCREEN"] = "1"
    env["KIU_PC_DISPLAY"] = "1080p"
    if args.texture_filter == "cubic": env["KIU_TEXTURE_FILTER"] = "cubic"
    if args.texture_pack: env["KIU_TEXTURE_PACK"] = str(args.texture_pack.resolve())
    if not args.original_hud_sampling: env["KIU_EXPERIMENTAL_HUD"] = "1"
    if not args.original_aspect: env["KIU_EXPERIMENTAL_WIDE"] = "1"
    if args.sixty_fps: env["KIU_60FPS"] = "1"
    if args.thirty_fps: env["KIU_60FPS"] = "0"

    # the profile: settings, pipeline cache, saves (copied once from the
    # normal ones, never written back)
    settings_file = PROFILE / "roaming/zakuro/settings.toml"
    if not settings_file.exists():
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        text = ORIGINAL_SETTINGS.read_text(encoding="utf-8") if ORIGINAL_SETTINGS.exists() else ""
        import re
        text, count = re.subn(r"(?m)^resolution\s*=.*$", "resolution = 5", text)
        settings_file.write_text(text if count else "resolution = 5\n" + text, encoding="utf-8")
    cache = PROFILE / "local/zakuro/pipelines.bin"
    if not cache.exists() and ORIGINAL_CACHE.is_file():
        cache.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ORIGINAL_CACHE, cache)
    for variable, folder in (("APPDATA", "roaming"), ("LOCALAPPDATA", "local")):
        target = PROFILE / folder; target.mkdir(parents=True, exist_ok=True); env[variable] = str(target)
    saves = PROFILE / "kiu"
    saves.mkdir(parents=True, exist_ok=True)
    if not (saves / "user").exists() and (ORIGINAL_SAVES / "user").is_dir():
        staging = saves / "user-copying"
        if staging.exists(): ap.error(f"Incomplete save copy exists: {staging}")
        shutil.copytree(ORIGINAL_SAVES / "user", staging)
        staging.rename(saves / "user")
    shared_font = ORIGINAL_SAVES / "sysdata/shared_font.bin"
    if shared_font.is_file() and not (saves / "sysdata/shared_font.bin").exists():
        shutil.copytree(ORIGINAL_SAVES / "sysdata", saves / "sysdata", dirs_exist_ok=True)
    if (saves / "user").is_dir() and not (saves / "user-before-pc-interface").exists():
        shutil.copytree(saves / "user", saves / "user-backup-copying")
        (saves / "user-backup-copying").rename(saves / "user-before-pc-interface")
        print(f"Saves backed up once: {saves / 'user-before-pc-interface'}", flush=True)

    if not args.legacy_controls:
        env["KIU_PC_CONTROLS"] = "1"
        if args.relative_camera: env["KIU_RELATIVE_CAMERA"] = "1"
        if not args.original_flight_aim: env["KIU_EXPERIMENTAL_AIR"] = "1"
        env["KIU_MOUSE_SENSITIVITY"] = str(args.mouse_sensitivity)
        env["KIU_WALK_STRENGTH"] = str(args.walk_strength)

    # diagnostics
    if args.diagnostics:
        env["RUST_LOG"] = "info,zakuro::fps=debug,zakuro_gpu::pipelines=debug"
        env["ZAKURO_GPU_TIMES"] = "1"
    if args.legacy_texture_sampling: env["ZAKURO_LEGACY_TEXTURE_SAMPLING"] = "1"
    settings_snapshot = None
    if args.texture_trace or args.render_capture or args.input_trace or args.record_input:
        import tomllib
        if settings_file.is_file(): settings_snapshot = tomllib.loads(settings_file.read_text(encoding="utf-8"))
    font_sha = digest(shared_font) if shared_font.is_file() else None
    log_dir = None
    if args.texture_trace or args.render_capture:
        log_dir = stamped("build/texture-traces")
        env["KIU_TEXTURE_TRACE"] = str(log_dir / "texture-states.csv")
        if args.render_capture:
            env["KIU_RENDER_CAPTURE"] = str(log_dir / "capture")
            env["KIU_RENDER_CAPTURE_WAIT"] = "1"
            print("Render capture ready: press F8 once in the affected scene, then play briefly.", flush=True)
        (log_dir / "session.json").write_text(json.dumps({
            "build": build_name, "resolution_override": args.resolution,
            "settings_at_launch": settings_snapshot, "shared_font_sha256": font_sha,
            "legacy_texture_sampling": args.legacy_texture_sampling, "render_capture": args.render_capture,
            "runtime_sha256": digest(RUNTIME), "library_sha256": digest(library) if library else None,
        }, indent=2) + "\n", encoding="utf-8")
        print(f"Texture diagnostics: {log_dir}", flush=True)
    if args.ui_census:
        census_dir = stamped("build/native-ui/census")
        env["KIU_UI_CENSUS"] = str(census_dir / "lower-screen-draws.csv")
        print(f"Lower-screen census: {census_dir}", flush=True)
    if args.ram_snapshots:
        ram_dir = stamped("build/ram-snapshots", "%Y%m%d-%H%M%S")
        env["KIU_RAM_SNAPSHOT"] = str(ram_dir)
        print(f"RAM snapshots (F7): {ram_dir}", flush=True)
    trace_dir = None
    if args.input_trace or args.record_input:
        trace_dir = stamped("build/input-traces")
        if args.input_trace: env["KIU_INPUT_TRACE"] = str(trace_dir / "input.csv")
        if args.record_input: env["ZAKURO_RECORD"] = str(trace_dir / "input.replay")
        print(f"Input diagnostics: {trace_dir}", flush=True)
        log_dir = log_dir or trace_dir
    if args.replay:
        # a replay never touches real progress: it runs on its own copy
        if not args.replay.is_file(): ap.error(f"Replay missing: {args.replay}")
        if not args.replay_save or not (args.replay_save / "user").is_dir():
            ap.error("--replay needs --replay-save with the recording's starting 'user' folder")
        run_dir = stamped("build/live-test", "%Y%m%d-%H%M%S")
        shutil.copytree(args.replay_save / "user", run_dir / "kiu/user")
        sysdata = args.replay_save / "sysdata"
        shutil.copytree(sysdata if sysdata.is_dir() else saves / "sysdata", run_dir / "kiu/sysdata")
        saves = run_dir / "kiu"
        env["ZAKURO_REPLAY"] = str(args.replay.resolve())
        print(f"Replay test on copied saves: {saves}", flush=True)
    if trace_dir is not None:
        (trace_dir / "session.json").write_text(json.dumps({
            "build": build_name, "mouse_model": "bounded",
            "relative_camera": args.relative_camera and not args.legacy_controls,
            "sensitivity": args.mouse_sensitivity, "walk_strength": args.walk_strength,
            "resolution_override": args.resolution, "settings_at_launch": settings_snapshot,
            "shared_font_sha256": font_sha, "runtime_sha256": digest(RUNTIME),
            "library_sha256": digest(library) if library else None,
        }, indent=2) + "\n", encoding="utf-8")
        if args.record_input and (saves / "user").is_dir():
            shutil.copytree(saves / "user", trace_dir / "initial-save/user")
        if args.record_input and shared_font.is_file():
            font_snapshot = trace_dir / "initial-save/sysdata/shared_font.bin"
            font_snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(shared_font, font_snapshot)

    command = [str(RUNTIME), str(ROM), "--data", str(saves)]
    command += ["--interpreter"] if args.interpreter else ["--recompiled", str(library)]
    if args.software: command += ["--renderer", "software", "--rasterizer", "software"]
    if args.headless: command += ["--headless", str(args.headless), "--mute"]
    if args.scale: command += ["--scale", str(max(1, args.scale))]
    if args.resolution: command += ["--resolution", str(args.resolution)]
    if args.profile: command += ["--profile"]

    if args.interpreter:
        print("Launching KIU: interpreter baseline", flush=True)
    else:
        meta = json.loads((library.parent / "build-result.json").read_text(encoding="utf-8"))
        print(f"Launching KIU: {build_name} AOT library (optimization {meta.get('optimization', '?')}, interpreter fallback enabled)", flush=True)
        print(f"Library: {library}", flush=True)
    print("PC interface: original portraits, specials/Power Palette and counters over gameplay; the game's pause menu opens as a panel. Tab: lower screen, F9: original two screens.", flush=True)
    if not args.legacy_controls:
        camera = "relative land camera" if args.relative_camera else "original land camera"
        flight = "bounded flight aim" if args.original_flight_aim else "relative flight aim"
        print(f"PC controls: WASD run, Alt walk, Shift dash, F2 mouse aim, Tab bottom screen/menu cursor, "
              f"left click attack; E special/power, 1/3 select power (rebind in Settings) ({camera}, {flight}, sensitivity {args.mouse_sensitivity:g})", flush=True)
    if args.diagnostics and log_dir is not None:
        log_path = log_dir / "runtime.log"
        print(f"Runtime diagnostics: {log_path}", flush=True)
        with log_path.open("w", encoding="utf-8") as log:
            return subprocess.call(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    return subprocess.call(command, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
