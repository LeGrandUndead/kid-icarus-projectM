"""Kid Icarus: Uprising experimental native launcher."""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/rom"))
from audit_executable import audit

EXPECTED_CODE_SHA256 = "2718aa2077a29560208c4e499288e5fecc4446d7adec95efb91ebf1b19eda679"
BUILD_DIRS = {"debug": ROOT / "build/kiu-aot-debug", "o2": ROOT / "build/kiu-aot-o2"}

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

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--texture-filter", choices=("original", "cubic"), default="original", help="experimental build: original-art magnification filtering")
    ap.add_argument("--texture-pack", type=Path, help="experimental build: folder of content-addressed HD replacement PNGs")
    ap.add_argument("--experimental", action="store_true", help="separate experimental executable, settings and copied saves")
    ap.add_argument("--single-screen", action="store_true", help="isolated single-screen compositor test build")
    ap.add_argument("--dialogue-preview", action="store_true", help="isolated original-portrait gameplay preview")
    ap.add_argument("--original-hud-resolution", action="store_true", help="PC interface: original HUD art (same as --hud-art original)")
    ap.add_argument("--hud-art", choices=("pc", "original"), default="pc", help="pc = HUD reconstructed from your ROM (build/texture-work/hud-pc), original = ROM resolution")
    ap.add_argument("--menu-art", choices=("pc", "original"), default="pc", help="pc = menu screens' art reconstructed from your ROM (build/texture-work/menu-pc, tools/recomp/build_menu_pc_pack.py), original = as on the 3DS")
    ap.add_argument("--pc-interface", action="store_true", help="gameplay preview + original specials/powers/counters HUD and automatic pause panel (separate executable, preview profile)")
    ap.add_argument("--no-native-hud", action="store_true", help="PC interface: keep only the portraits, for comparison")
    ap.add_argument("--ui-census", action="store_true", help="PC interface: record catalogued lower-screen draws to a CSV for tracing")
    ap.add_argument("--ram-snapshots", action="store_true", help="research: F7 saves game memory to build/ram-snapshots/<time> (the comparison script is archived)")
    ap.add_argument("--camera-scale", type=float, help="override saved preview lens scale, 0.75 to 1.0; 1 keeps the previous view")
    ap.add_argument("--original-aspect", action="store_true", help="experimental build: disable wider projection")
    ap.add_argument("--original-flight-aim", action="store_true", help="experimental build: disable direct relative flight aiming")
    ap.add_argument("--original-hud-sampling", action="store_true", help="experimental build: disable HUD atlas-edge correction")
    ap.add_argument("--interpreter", action="store_true")
    ap.add_argument("--software", action="store_true")
    ap.add_argument("--headless", type=int, default=0)
    ap.add_argument("--build", choices=("auto","debug","o2"), default="auto")
    ap.add_argument("--library", type=Path)
    ap.add_argument("--scale", type=int)
    ap.add_argument("--display", choices=("original", "1080p"), default="original",
                    help="1080p: separate presentation profile, top screen, 1920x1080 window; original camera aspect")
    ap.add_argument("--resolution", type=int, choices=range(1, 9),
                    help="internal 3D scale: 3=1200x720, 5=2000x1200, 6=2400x1440, 8=3200x1920; preserves original aspect")
    ap.add_argument("--input-trace", action="store_true", help="save raw mouse and final guest input CSV")
    ap.add_argument("--record-input", action="store_true", help="record guest input for deterministic replay")
    ap.add_argument("--legacy-controls", action="store_true", help="disable KIU PC control layer")
    ap.add_argument("--relative-camera", action="store_true", default=True,
                    help="use direct relative mouse movement for the land camera (default)")
    ap.add_argument("--original-land-camera", dest="relative_camera", action="store_false",
                    help="restore the bounded land camera while retaining the other PC controls")
    ap.add_argument("--mouse-sensitivity", type=float, default=0.55)
    ap.add_argument("--walk-strength", type=float, default=0.60,
                    help="Alt+WASD analog strength")
    ap.add_argument("--diagnostics", action="store_true", help="log frame pacing and GPU pipeline/timing data")
    ap.add_argument("--texture-trace", action="store_true",
                    help="record unique PICA texture filtering/LOD states to CSV")
    ap.add_argument("--render-capture", action="store_true",
                    help="press F8 in the affected scene to capture local texture images/raw bytes and fragment registers")
    ap.add_argument("--legacy-texture-sampling", action="store_true",
                    help="A/B test: restore the old base-level sampler behavior")
    ap.add_argument("--profile", action="store_true", help="enable guest-PC sampling profiler")
    rate = ap.add_mutually_exclusive_group()
    rate.add_argument("--sixty-fps", action="store_true", help="60 FPS mode for this run (Settings > Graphics keeps the saved choice)")
    rate.add_argument("--thirty-fps", action="store_true", help="original 30 FPS for this run")
    ap.add_argument("--replay", type=Path, help="test: play back a recorded input file on copied saves, never the real ones")
    ap.add_argument("--replay-save", type=Path, help="with --replay: folder holding the recording's starting 'user' saves (and optionally 'sysdata')")
    args = ap.parse_args()
    if args.pc_interface: args.dialogue_preview = True
    if (args.no_native_hud or args.ui_census) and not args.pc_interface:
        ap.error("--no-native-hud and --ui-census require --pc-interface")
    camera_override = args.camera_scale is not None
    # The PC interface starts at the original view: a wider lens alone makes
    # enemies pop in at the edges (the game still culls its original frustum).
    if args.camera_scale is None: args.camera_scale = 0.85 if args.dialogue_preview and not args.pc_interface and not args.original_aspect else 1.0
    if args.dialogue_preview: args.single_screen = True
    if args.dialogue_preview and (args.software or args.headless):
        ap.error("the gameplay portrait preview requires the hardware-rendered game window")
    if args.single_screen: args.experimental = True
    import math
    if not math.isfinite(args.camera_scale) or not 0.75 <= args.camera_scale <= 1.0:
        ap.error("camera scale must be finite and between 0.75 and 1.0")
    if args.camera_scale != 1.0 and (not args.dialogue_preview or args.original_aspect):
        ap.error("camera scale requires the dialogue preview with its existing wide projection")
    for name, value, lo, hi in (("mouse sensitivity", args.mouse_sensitivity, 0.05, 4.0),
                               ("walk strength", args.walk_strength, 0.51, 0.90)):
        if not math.isfinite(value) or not lo <= value <= hi:
            ap.error(f"{name} must be finite and between {lo} and {hi}")

    rom = ROOT / "Kid Icarus - Uprising (USA) (En,Fr,Es).3ds"
    runtime = ROOT / "tools/zakuro/target/release/zakuro.exe"
    if args.texture_pack and not args.experimental: ap.error("Texture replacements currently require --experimental")
    if args.texture_pack and not args.texture_pack.is_dir(): ap.error("Texture pack folder does not exist")
    if args.experimental: runtime = runtime.with_name("zakuro-experimental.exe")
    if args.single_screen: runtime = runtime.with_name("zakuro-single-screen.exe")
    if args.dialogue_preview: runtime = runtime.with_name("zakuro-gameplay-preview.exe")
    if args.pc_interface: runtime = runtime.with_name("zakuro-pc-interface.exe")
    if not runtime.is_file(): ap.error(f"Runtime missing: {runtime}")
    if not rom.is_file(): ap.error(f"ROM missing: {rom}")

    library = None; build_name = "interpreter"
    if not args.interpreter:
        report = audit(ROOT / "ROM/gameFiles", rom)
        if report["code_sha256"] != EXPECTED_CODE_SHA256:
            ap.error("This native build targets a different executable revision")
        try: library, build_name = choose_library(args.build, args.library)
        except ValueError as exc: ap.error(str(exc))

    env = os.environ.copy()
    env.pop("KIU_TEXTURE_FILTER", None)
    env.pop("KIU_TEXTURE_PACK", None)
    env.pop("KIU_SINGLE_SCREEN", None)
    env.pop("KIU_NATIVE_DIALOGUE", None)
    env.pop("KIU_GAMEPLAY_CAMERA_SCALE", None)
    for name in ("KIU_NATIVE_UI", "KIU_NATIVE_HUD", "KIU_UI_CENSUS", "KIU_RAM_SNAPSHOT", "KIU_HUD_PACK", "KIU_MENU_PACK"):
        env.pop(name, None)
    if args.pc_interface:
        sources = ROOT / "build/native-ui/ui-sources.tsv"
        if not sources.is_file(): ap.error("Original UI catalog missing; run: python tools/recomp/prepare_native_ui_sources.py")
        env["KIU_NATIVE_UI"] = str(sources)
        if args.no_native_hud: env["KIU_NATIVE_HUD"] = "0"
        # PC HUD: the game's own HUD atlases rebuilt locally from the ROM by
        # tools/recomp/build_hud_pc_pack.py. Only those atlases are in it.
        art = "original" if args.original_hud_resolution else args.hud_art
        packs = {"pc": ["hud-pc"], "original": []}[art]
        hud_pack = next((ROOT / "build/texture-work" / name for name in packs if (ROOT / "build/texture-work" / name).is_dir()), None)
        if hud_pack:
            env["KIU_HUD_PACK"] = str(hud_pack.resolve())
            print(f"HUD art: {hud_pack.name}, reconstructed from your ROM (--hud-art original to compare).", flush=True)
        # PC menu art: every menu screen's textures rebuilt locally from the
        # ROM (sharper, 3DS-only icons removed) by build_menu_pc_pack.py
        menu_pack = ROOT / "build/texture-work/menu-pc"
        if args.menu_art == "pc" and menu_pack.is_dir():
            env["KIU_MENU_PACK"] = str(menu_pack.resolve())
            print("Menu art: menu-pc, reconstructed from your ROM (--menu-art original to compare).", flush=True)
        if camera_override or args.original_aspect: env["KIU_GAMEPLAY_CAMERA_SCALE"] = str(args.camera_scale)
    elif args.dialogue_preview:
        sources = ROOT / "build/native-ui/dialogue-sources/portrait-hashes.txt"
        if not sources.is_file(): ap.error("Original portrait catalog missing; run tools/recomp/prepare_dialogue_sources.ps1")
        env["KIU_NATIVE_DIALOGUE"] = str(sources)
        if camera_override or args.original_aspect: env["KIU_GAMEPLAY_CAMERA_SCALE"] = str(args.camera_scale)
    if args.single_screen: env["KIU_SINGLE_SCREEN"] = "1"
    env.pop("KIU_60FPS", None)
    if args.sixty_fps: env["KIU_60FPS"] = "1"
    if args.thirty_fps: env["KIU_60FPS"] = "0"
    env.pop("KIU_PROJECTION_TRACE", None)
    env.pop("KIU_EXPERIMENTAL_HUD", None)
    env.pop("KIU_RENDER_CAPTURE_WAIT", None)
    for name in ("KIU_DRAW_FRAME", "KIU_DRAW_CAPTURE", "KIU_DIAGNOSTIC_IGNORE_DEPTH"):
        env.pop(name, None)
    # A baseline must not inherit an enabled adapter from a parent terminal.
    for name in ("KIU_EXPERIMENTAL_AIR", "KIU_EXPERIMENTAL_WIDE", "KIU_PC_DISPLAY", "KIU_PC_CONTROLS", "KIU_INPUT_TRACE", "KIU_MOUSE_MODEL", "KIU_CONTROL_PROFILE", "KIU_MOUSE_ACCELERATION", "KIU_RELATIVE_CAMERA", "ZAKURO_RECORD", "KIU_TEXTURE_TRACE", "ZAKURO_LEGACY_TEXTURE_SAMPLING", "KIU_RENDER_CAPTURE"):
        env.pop(name, None)
    env["PATH"] = str(ROOT / "tools/toolchains/winlibs/mingw64/bin") + os.pathsep + env.get("PATH", "")
    profile = ROOT / "build/user-data"
    if args.display == "1080p" or args.experimental:
        import shutil
        profile = ROOT / ("build/user-data/single-screen-pc" if args.single_screen else "build/user-data/experimental-pc" if args.experimental else "build/user-data/presentation-1080p")
        if args.dialogue_preview: profile = ROOT / "build/user-data/gameplay-preview"
        settings_file = profile / "roaming/zakuro/settings.toml"
        if not settings_file.exists():
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            original_settings = ROOT / "build/user-data/roaming/zakuro/settings.toml"
            if args.single_screen: original_settings = ROOT / "build/user-data/experimental-pc/roaming/zakuro/settings.toml"
            if original_settings.exists():
                import re
                text = original_settings.read_text(encoding="utf-8")
                text, count = re.subn(r"(?m)^resolution\s*=.*$", "resolution = 5", text)
                if not count: text = "resolution = 5\n" + text
                settings_file.write_text(text, encoding="utf-8")
            else:
                settings_file.write_text("resolution = 5\n", encoding="utf-8")
        env["KIU_PC_DISPLAY"] = "1080p"
        # Reuse the existing compatible pipeline cache on the first profile run.
        cache = profile / "local/zakuro/pipelines.bin"
        original_cache = ROOT / "build/user-data/local/zakuro/pipelines.bin"
        if args.single_screen: original_cache = ROOT / "build/user-data/experimental-pc/local/zakuro/pipelines.bin"
        if not cache.exists() and original_cache.is_file():
            cache.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original_cache, cache)
        if args.experimental:
            if args.texture_filter == "cubic": env["KIU_TEXTURE_FILTER"] = "cubic"
            # Texture replacement is opt-in; an old pack left on disk must
            # never silently replace the original artwork.
            if args.texture_pack: env["KIU_TEXTURE_PACK"] = str(args.texture_pack.resolve())
            if not args.original_hud_sampling: env["KIU_EXPERIMENTAL_HUD"] = "1"
            if not args.original_aspect: env["KIU_EXPERIMENTAL_WIDE"] = "1"
            if not args.original_flight_aim and not args.legacy_controls: env["KIU_EXPERIMENTAL_AIR"] = "1"
            print("EXPERIMENTAL PC build: separate saves/settings; Tab bottom-screen cursor; F11 fullscreen. Wider projection and flight aiming need chapter testing.", flush=True)
        else:
            print("1080p presentation: real high-resolution 3D, original 5:3 framing (side bars). Tab: bottom screen/menu cursor; F11: fullscreen.", flush=True)
    for variable, folder in (("APPDATA","roaming"),("LOCALAPPDATA","local")):
        target = profile / folder; target.mkdir(parents=True, exist_ok=True); env[variable] = str(target)
    if not args.legacy_controls:
        env["KIU_PC_CONTROLS"] = "1"
        if args.relative_camera: env["KIU_RELATIVE_CAMERA"] = "1"
        env["KIU_MOUSE_SENSITIVITY"] = str(args.mouse_sensitivity)
        env["KIU_WALK_STRENGTH"] = str(args.walk_strength)
    if args.diagnostics:
        env["RUST_LOG"] = "info,zakuro::fps=debug,zakuro_gpu::pipelines=debug"
        env["ZAKURO_GPU_TIMES"] = "1"
    if args.legacy_texture_sampling:
        env["ZAKURO_LEGACY_TEXTURE_SAMPLING"] = "1"
    settings_snapshot = None
    shared_font = ROOT / "build/user-data/kiu/sysdata/shared_font.bin"
    font_sha = digest(shared_font) if shared_font.is_file() else None
    if args.texture_trace or args.render_capture or args.input_trace or args.record_input:
        settings_path = profile / "roaming/zakuro/settings.toml"
        if settings_path.is_file():
            import tomllib
            settings_snapshot = tomllib.loads(settings_path.read_text(encoding="utf-8"))
    if args.texture_trace or args.render_capture:
        from datetime import datetime
        texture_trace_dir = ROOT / "build/texture-traces" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        texture_trace_dir.mkdir(parents=True)
        env["KIU_TEXTURE_TRACE"] = str(texture_trace_dir / "texture-states.csv")
        if args.render_capture:
            env["KIU_RENDER_CAPTURE"] = str(texture_trace_dir / "capture")
            env["KIU_RENDER_CAPTURE_WAIT"] = "1"
            print("Render capture ready: press F8 once in the affected scene, then play briefly.", flush=True)
        (texture_trace_dir / "session.json").write_text(json.dumps({
            "build": build_name,
            "resolution_override": args.resolution,
            "settings_at_launch": settings_snapshot,
            "shared_font_sha256": font_sha,
            "legacy_texture_sampling": args.legacy_texture_sampling,
            "render_capture": args.render_capture,
            "runtime_sha256": digest(runtime),
            "library_sha256": digest(library) if library else None,
        }, indent=2) + "\n", encoding="utf-8")
        print(f"Texture diagnostics: {texture_trace_dir}", flush=True)
    if args.ui_census:
        from datetime import datetime
        census_dir = ROOT / "build/native-ui/census" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        census_dir.mkdir(parents=True)
        env["KIU_UI_CENSUS"] = str(census_dir / "lower-screen-draws.csv")
        print(f"Lower-screen census: {census_dir}", flush=True)
    if args.ram_snapshots:
        from datetime import datetime
        ram_dir = ROOT / "build/ram-snapshots" / datetime.now().strftime("%Y%m%d-%H%M%S")
        ram_dir.mkdir(parents=True)
        env["KIU_RAM_SNAPSHOT"] = str(ram_dir)
        print(f"RAM snapshots (F7): {ram_dir}", flush=True)
    if args.input_trace or args.record_input:
        from datetime import datetime
        trace_dir = ROOT / "build/input-traces" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        trace_dir.mkdir(parents=True)
        if args.input_trace: env["KIU_INPUT_TRACE"] = str(trace_dir / "input.csv")
        if args.record_input: env["ZAKURO_RECORD"] = str(trace_dir / "input.replay")
        print(f"Input diagnostics: {trace_dir}", flush=True)

    saves = ROOT / "build/user-data/kiu"
    if args.experimental:
        import shutil
        original_saves = saves
        if args.single_screen: original_saves = ROOT / "build/user-data/experimental-pc/kiu"
        saves = profile / "kiu"
        saves.mkdir(parents=True, exist_ok=True)
        if not (saves / "user").exists() and (original_saves / "user").is_dir():
            staging = saves / "user-copying"
            if staging.exists(): ap.error(f"Incomplete experimental save copy exists: {staging}")
            shutil.copytree(original_saves / "user", staging)
            staging.rename(saves / "user")
        if shared_font.is_file() and not (saves / "sysdata/shared_font.bin").exists():
            shutil.copytree(original_saves / "sysdata", saves / "sysdata", dirs_exist_ok=True)
        print(f"Experimental saves: {saves} (normal progress is untouched)", flush=True)
        if args.pc_interface and (saves / "user").is_dir():
            # The PC interface shares the gameplay-preview profile. Keep one
            # untouched copy of that profile's saves from before its first use.
            backup = saves / "user-before-pc-interface"
            if not backup.exists():
                shutil.copytree(saves / "user", saves / "user-backup-copying")
                (saves / "user-backup-copying").rename(backup)
                print(f"Preview saves backed up once: {backup}", flush=True)
    saves.mkdir(parents=True, exist_ok=True)
    env.pop("ZAKURO_REPLAY", None)
    if args.replay:
        # a replay never touches real progress: it runs on its own copy
        import shutil
        from datetime import datetime
        if not args.replay.is_file(): ap.error(f"Replay missing: {args.replay}")
        if not args.replay_save or not (args.replay_save / "user").is_dir():
            ap.error("--replay needs --replay-save with the recording's starting 'user' folder")
        run = ROOT / "build/live-test" / datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copytree(args.replay_save / "user", run / "kiu/user")
        sysdata = args.replay_save / "sysdata"
        shutil.copytree(sysdata if sysdata.is_dir() else saves / "sysdata", run / "kiu/sysdata")
        saves = run / "kiu"
        env["ZAKURO_REPLAY"] = str(args.replay.resolve())
        print(f"Replay test on copied saves: {saves}", flush=True)
    if args.input_trace or args.record_input:
        (trace_dir / "session.json").write_text(json.dumps({
            "build": build_name, "mouse_model": "bounded",
            "relative_camera": args.relative_camera and not args.legacy_controls,
            "sensitivity": args.mouse_sensitivity,
            "walk_strength": args.walk_strength, "resolution_override": args.resolution,
            "settings_at_launch": settings_snapshot,
            "shared_font_sha256": font_sha,
            "runtime_sha256": digest(runtime),
            "library_sha256": digest(library) if library else None,
        }, indent=2) + "\n", encoding="utf-8")
        if args.record_input and (saves / "user").is_dir():
            import shutil
            shutil.copytree(saves / "user", trace_dir / "initial-save/user")
        if args.record_input and shared_font.is_file():
            import shutil
            font_snapshot = trace_dir / "initial-save/sysdata/shared_font.bin"
            font_snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(shared_font, font_snapshot)
    command = [str(runtime), str(rom), "--data", str(saves)]
    command += ["--interpreter"] if args.interpreter else ["--recompiled", str(library)]
    if args.software: command += ["--renderer","software","--rasterizer","software"]
    if args.headless: command += ["--headless",str(args.headless),"--mute"]
    if args.scale: command += ["--scale",str(max(1,args.scale))]
    if args.resolution: command += ["--resolution", str(args.resolution)]
    if args.profile: command += ["--profile"]

    if args.interpreter: print("Launching KIU: interpreter baseline", flush=True)
    else:
        meta=json.loads((library.parent/"build-result.json").read_text(encoding="utf-8"))
        print(f"Launching KIU: {build_name} AOT library (optimization {meta.get('optimization','?')}, interpreter fallback enabled)", flush=True)
        print(f"Library: {library}", flush=True)
    if args.pc_interface:
        print("PC interface: original portraits, specials/Power Palette and counters over gameplay; the game's pause menu opens as a panel (Settings > Interface). Tab: lower screen, F9: original two screens.", flush=True)
    if not args.legacy_controls:
        camera = "relative land camera" if args.relative_camera else "original land camera"
        flight = "relative flight aim" if "KIU_EXPERIMENTAL_AIR" in env else "bounded flight aim"
        print(
            f"PC controls: WASD run, Alt walk, Shift dash, F2 mouse aim, Tab bottom screen/menu cursor, "
            f"left click attack; defaults E special/power, 1/3 select power (rebind in Settings) ({camera}, {flight}, sensitivity {args.mouse_sensitivity:g})",
            flush=True,
        )
    if args.diagnostics and (args.render_capture or args.texture_trace or args.record_input or args.input_trace):
        log_dir = texture_trace_dir if args.render_capture or args.texture_trace else trace_dir
        log_path = log_dir / "runtime.log"
        print(f"Runtime diagnostics: {log_path}", flush=True)
        with log_path.open("w", encoding="utf-8") as log:
            return subprocess.call(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    return subprocess.call(command, cwd=ROOT, env=env)

if __name__ == "__main__": raise SystemExit(main())
