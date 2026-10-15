"""Profile-isolation checks; never launch a game or touch live saves."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import tomllib

spec = importlib.util.spec_from_file_location("kiu_launch", Path(__file__).parents[1] / "launch.py")
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)

class PresentationProfile(unittest.TestCase):
    def test_experimental_saves_are_copied_once_and_flags_do_not_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ["tools/zakuro/target/release/zakuro.exe", "tools/zakuro/target/release/zakuro-experimental.exe", "tools/zakuro/target/release/zakuro-single-screen.exe", "tools/zakuro/target/release/zakuro-gameplay-preview.exe", "tools/zakuro/target/release/zakuro-pc-interface.exe", "Kid Icarus - Uprising (USA) (En,Fr,Es).3ds"]:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch()
            catalog = root / "build/native-ui/dialogue-sources/portrait-hashes.txt"
            catalog.parent.mkdir(parents=True)
            catalog.write_text("0123456789ABCDEF\n")
            original = root / "build/user-data/kiu/user/progress.bin"
            original.parent.mkdir(parents=True)
            original.write_bytes(b"normal progress")
            settings = root / "build/user-data/roaming/zakuro/settings.toml"
            settings.parent.mkdir(parents=True)
            settings.write_text('[keys]\npc_action = "KeyR"\n')
            with patch.object(launch, "ROOT", root), patch.object(launch.subprocess, "call", return_value=0) as call:
                def run(*args):
                    with patch("sys.argv", ["launch", "--interpreter", *args]):
                        self.assertEqual(launch.main(), 0)
                    return call.call_args.args[0], call.call_args.kwargs["env"]
                command, env = run("--experimental")
                self.assertTrue(command[0].endswith("zakuro-experimental.exe"))
                self.assertEqual(env["KIU_EXPERIMENTAL_AIR"], "1")
                self.assertEqual(env["KIU_EXPERIMENTAL_WIDE"], "1")
                self.assertEqual(env["KIU_EXPERIMENTAL_HUD"], "1")
                self.assertNotIn("KIU_TEXTURE_FILTER", env)
                self.assertNotIn("KIU_TEXTURE_PACK", env)
                saves = Path(command[command.index("--data") + 1])
                self.assertNotEqual(saves, original.parent.parent)
                copied = saves / "user/progress.bin"
                self.assertEqual(copied.read_bytes(), original.read_bytes())
                copied.write_bytes(b"experimental progress")
                single, single_env = run("--single-screen", "--display", "1080p")
                self.assertTrue(single[0].endswith("zakuro-single-screen.exe"))
                self.assertEqual(single_env["KIU_SINGLE_SCREEN"], "1")
                single_save=Path(single[single.index("--data")+1])/"user/progress.bin"
                self.assertEqual(single_save.read_bytes(),b"experimental progress")
                single_save.write_bytes(b"separate test progress")
                run("--single-screen")
                self.assertEqual(single_save.read_bytes(),b"separate test progress")
                self.assertEqual(copied.read_bytes(),b"experimental progress")
                preview, preview_env = run("--dialogue-preview", "--camera-scale", "0.92")
                self.assertTrue(preview[0].endswith("zakuro-gameplay-preview.exe"))
                self.assertEqual(preview_env["KIU_GAMEPLAY_CAMERA_SCALE"], "0.92")
                self.assertEqual(preview_env["KIU_NATIVE_DIALOGUE"], str(catalog))
                preview_save = Path(preview[preview.index("--data")+1])/"user/progress.bin"
                self.assertEqual(preview_save.read_bytes(), b"experimental progress")
                self.assertNotEqual(preview_save, single_save)
                preview_save.write_bytes(b"preview progress")
                run("--dialogue-preview")
                self.assertEqual(preview_save.read_bytes(), b"preview progress")
                self.assertEqual(tomllib.loads((Path(env["APPDATA"]) / "zakuro/settings.toml").read_text())["resolution"], 5)
                # PC interface: own executable, the preview's profile, a one-time backup
                with patch("sys.argv", ["launch", "--interpreter", "--pc-interface"]):
                    with self.assertRaises(SystemExit):
                        launch.main()  # catalog missing
                ui = root / "build/native-ui/ui-sources.tsv"
                ui.write_text("F303562AB938B926\thud\tgc_00\n")
                pc, pc_env = run("--pc-interface", "--ui-census")
                self.assertTrue(pc[0].endswith("zakuro-pc-interface.exe"))
                self.assertEqual(pc_env["KIU_NATIVE_UI"], str(ui))
                self.assertNotIn("KIU_NATIVE_DIALOGUE", pc_env)
                self.assertNotIn("KIU_NATIVE_HUD", pc_env)
                self.assertTrue(pc_env["KIU_UI_CENSUS"].endswith("lower-screen-draws.csv"))
                self.assertEqual(Path(pc[pc.index("--data")+1]) / "user/progress.bin", preview_save)
                backup = preview_save.parent.parent / "user-before-pc-interface/progress.bin"
                self.assertEqual(backup.read_bytes(), b"preview progress")
                preview_save.write_bytes(b"interface progress")
                _, pc_env = run("--pc-interface", "--no-native-hud")
                self.assertEqual(pc_env["KIU_NATIVE_HUD"], "0")
                self.assertEqual(backup.read_bytes(), b"preview progress")
                preview_save.write_bytes(b"preview progress")
                with patch("sys.argv", ["launch", "--interpreter", "--dialogue-preview", "--ui-census"]):
                    with self.assertRaises(SystemExit):
                        launch.main()
                _, env = run("--experimental", "--original-aspect", "--original-flight-aim", "--original-hud-sampling", "--texture-filter", "original")
                self.assertNotIn("KIU_EXPERIMENTAL_HUD", env)
                self.assertNotIn("KIU_TEXTURE_FILTER", env)
                self.assertNotIn("KIU_EXPERIMENTAL_AIR", env)
                self.assertNotIn("KIU_EXPERIMENTAL_WIDE", env)
                self.assertEqual(copied.read_bytes(), b"experimental progress")
                with patch.dict(os.environ, {"KIU_NATIVE_DIALOGUE":"inherited", "KIU_GAMEPLAY_CAMERA_SCALE":"0.85", "KIU_SINGLE_SCREEN":"1", "KIU_EXPERIMENTAL_AIR": "1", "KIU_EXPERIMENTAL_WIDE": "1", "KIU_EXPERIMENTAL_HUD": "1", "KIU_TEXTURE_FILTER": "cubic", "KIU_TEXTURE_PACK": "inherited-pack", "KIU_PROJECTION_TRACE": "inherited-trace", "KIU_NATIVE_UI": "inherited", "KIU_UI_CENSUS": "inherited", "KIU_NATIVE_HUD": "0"}):
                    command, env = run()
                self.assertTrue(command[0].endswith("zakuro.exe"))
                self.assertNotIn("KIU_EXPERIMENTAL_AIR", env)
                self.assertNotIn("KIU_EXPERIMENTAL_WIDE", env)
                self.assertNotIn("KIU_EXPERIMENTAL_HUD", env)
                self.assertNotIn("KIU_TEXTURE_FILTER", env)
                self.assertNotIn("KIU_TEXTURE_PACK", env)
                self.assertNotIn("KIU_PROJECTION_TRACE", env)
                self.assertNotIn("KIU_SINGLE_SCREEN", env)
                self.assertNotIn("KIU_NATIVE_DIALOGUE", env)
                self.assertNotIn("KIU_GAMEPLAY_CAMERA_SCALE", env)
                for name in ("KIU_NATIVE_UI", "KIU_UI_CENSUS", "KIU_NATIVE_HUD"):
                    self.assertNotIn(name, env)
                self.assertEqual(original.read_bytes(), b"normal progress")

    def test_profile_is_reversible_and_keeps_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ["tools/zakuro/target/release/zakuro.exe", "Kid Icarus - Uprising (USA) (En,Fr,Es).3ds"]:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch()
            original = root / "build/user-data/roaming/zakuro/settings.toml"
            original.parent.mkdir(parents=True)
            text = 'resolution = 8\nlayout = "stacked"\n[keys]\npc_action = "KeyR"\n'
            original.write_text(text)
            with patch.object(launch, "ROOT", root), patch.object(launch.subprocess, "call", return_value=0) as call:
                with patch("sys.argv", ["launch", "--interpreter", "--display", "1080p"]):
                    self.assertEqual(launch.main(), 0)
                env = call.call_args.kwargs["env"]
                self.assertEqual(env["KIU_PC_DISPLAY"], "1080p")
                profile = Path(env["APPDATA"]) / "zakuro/settings.toml"
                settings = tomllib.loads(profile.read_text())
                self.assertEqual(settings["resolution"], 5)
                self.assertEqual(settings["keys"]["pc_action"], "KeyR")
                self.assertEqual(original.read_text(), text)
                profile.write_text(profile.read_text().replace("resolution = 5", "resolution = 6"))
                with patch("sys.argv", ["launch", "--interpreter", "--display", "1080p"]):
                    launch.main()
                self.assertEqual(tomllib.loads(profile.read_text())["resolution"], 6)
                with patch.dict(os.environ, {"KIU_PC_DISPLAY": "1080p"}), patch("sys.argv", ["launch", "--interpreter"]):
                    launch.main()
                self.assertNotIn("KIU_PC_DISPLAY", call.call_args.kwargs["env"])
                self.assertEqual(Path(call.call_args.kwargs["env"]["APPDATA"]), root / "build/user-data/roaming")
                self.assertEqual(original.read_text(), text)

if __name__ == "__main__":
    unittest.main()
