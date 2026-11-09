//! Kid Icarus: Uprising's own launcher: the game started by double-clicking
//! one program, `Kid Icarus Uprising.exe`.
//!
//! It sets up, inside the program, what `Launch-KIU.cmd` asked
//! `tools/recomp/launch.py` for (`--pc-interface --display 1080p`): the
//! single-screen PC interface, the PC controls, the 16:9 view, and the
//! profile the saves and settings live in. Python is not needed, no console
//! window opens, and what is missing is said in a message box. The research
//! switches stay with `launch.py`.
//!
//! The game's folder is the nearest folder above the program that holds the
//! game library (`build/kiu-aot-o2`). The game itself is the player's own
//! copy: the `.3ds` in that folder, or one chosen the first time and
//! remembered in the profile.

use std::io::Read;
use std::path::{Path, PathBuf};

/// the release the game library is built from: the USA one.
const TITLE: u64 = 0x0004_0000_0003_0100;
const LIBRARY: &str = "build/kiu-aot-o2/0004000000030100.dll";
/// where saves and PC settings have lived since the single-screen interface.
const PROFILE: &str = "build/user-data/gameplay-preview";
const ROM_NAME: &str = "Kid Icarus - Uprising (USA) (En,Fr,Es).3ds";
const NAME: &str = "Kid Icarus: Uprising";

/// the command line for the game, with the environment prepared for it, or
/// what is missing.
pub fn prepare() -> Result<Vec<String>, String> {
    let program = std::env::current_exe().map_err(|error| format!("Could not find the program's own folder ({error})."))?;
    let root = root_above(&program)
        .ok_or("The game library was not found.\n\nKeep this program inside the game's folder (the one with the 'build' folder), or rebuild the library with Rebuild-Library.cmd.")?;
    let profile = root.join(PROFILE);
    let roaming = profile.join("roaming");
    let local = profile.join("local");
    for folder in [&roaming.join("zakuro"), &local, &profile.join("kiu")] {
        std::fs::create_dir_all(folder).map_err(|error| format!("Could not create {} ({error}).", folder.display()))?;
    }
    let settings = roaming.join("zakuro/settings.toml");
    if !settings.exists() {
        // a first run draws at 5x (2000x1200) until Settings says otherwise
        let _ = std::fs::write(&settings, "resolution = 5\n");
    }
    let rom = rom(&root, &roaming.join("zakuro/kiu-rom.txt"))?;

    let sources = root.join("build/native-ui/ui-sources.tsv");
    if !sources.is_file() {
        return Err(format!(
            "The interface catalog made from your game is missing:\n{}\n\nMake it with: python tools\\recomp\\prepare_native_ui_sources.py",
            sources.display()
        ));
    }
    let mut set: Vec<(&str, std::ffi::OsString)> = vec![
        ("APPDATA", roaming.into()),
        ("LOCALAPPDATA", local.into()),
        ("KIU_NATIVE_UI", sources.into()),
        ("KIU_SINGLE_SCREEN", "1".into()),
        ("KIU_PC_DISPLAY", "1080p".into()),
        ("KIU_PC_CONTROLS", "1".into()),
        ("KIU_RELATIVE_CAMERA", "1".into()),
        ("KIU_EXPERIMENTAL_HUD", "1".into()),
        ("KIU_EXPERIMENTAL_WIDE", "1".into()),
        ("KIU_EXPERIMENTAL_AIR", "1".into()),
    ];
    // the HUD atlases rebuilt from the ROM, when they have been
    let hud = root.join("build/texture-work/hud-pc");
    if hud.is_dir() {
        set.push(("KIU_HUD_PACK", hud.into()));
    }
    // the menus' art rebuilt sharper from the ROM, when it has been
    let menu_art = root.join("build/texture-work/menu-pc");
    if menu_art.is_dir() {
        set.push(("KIU_MENU_PACK", menu_art.into()));
    }
    // every menu on one screen: the game's own menu laid over its scene
    let layouts = root.join("tools/recomp/menu_layouts.toml");
    if layouts.is_file() {
        set.push(("KIU_MENU_LAYOUTS", layouts.into()));
    }
    // the game library's own runtime libraries
    let mut path = std::ffi::OsString::from(root.join("tools/toolchains/winlibs/mingw64/bin"));
    if let Some(old) = std::env::var_os("PATH") {
        path.push(if cfg!(windows) { ";" } else { ":" });
        path.push(old);
    }
    set.push(("PATH", path));
    for (name, value) in set {
        std::env::set_var(name, value);
    }
    // research switches of a terminal the game was started from stay out
    for name in ["KIU_NATIVE_HUD", "KIU_NATIVE_DIALOGUE", "KIU_GAMEPLAY_CAMERA_SCALE", "KIU_TEXTURE_FILTER", "KIU_TEXTURE_PACK", "KIU_60FPS", "KIU_MENU_CAPTURE"] {
        std::env::remove_var(name);
    }
    // paths the runtime takes from the working folder (the shared font,
    // build/diagnostics) are the game folder's
    let _ = std::env::set_current_dir(&root);

    let text = |path: PathBuf| path.to_string_lossy().into_owned();
    let mut arguments = vec![text(rom), "--data".to_owned(), text(profile.join("kiu")), "--recompiled".to_owned(), text(root.join(LIBRARY))];
    // anything given to the program goes on to the runtime (--resolution 6)
    arguments.extend(std::env::args().skip(1));
    Ok(arguments)
}

/// the nearest folder at or above the program's that holds the game library.
fn root_above(program: &Path) -> Option<PathBuf> {
    program.ancestors().skip(1).find(|folder| folder.join(LIBRARY).is_file()).map(Path::to_path_buf)
}

/// the player's copy of the game: in the game's folder, remembered from an
/// earlier choice, or chosen now.
fn rom(root: &Path, remembered: &Path) -> Result<PathBuf, String> {
    let named = root.join(ROM_NAME);
    if named.is_file() {
        return check(named);
    }
    if let Ok(entries) = std::fs::read_dir(root) {
        let found = entries.flatten().map(|entry| entry.path()).find(|path| {
            path.extension().is_some_and(|e| e.eq_ignore_ascii_case("3ds") || e.eq_ignore_ascii_case("cci")) && is_the_game(path) == Some(true)
        });
        if let Some(found) = found {
            return Ok(found);
        }
    }
    if let Some(saved) = std::fs::read_to_string(remembered).ok().map(|text| PathBuf::from(text.trim())).filter(|path| path.is_file()) {
        return check(saved);
    }
    rfd::MessageDialog::new()
        .set_title(NAME)
        .set_description("This needs your own copy of Kid Icarus: Uprising (USA), as a .3ds file.\n\nChoose it now; it is remembered for next time.")
        .set_buttons(rfd::MessageButtons::Ok)
        .show();
    let chosen = rfd::FileDialog::new()
        .set_title("Your copy of Kid Icarus: Uprising (USA)")
        .add_filter("Nintendo 3DS game", &["3ds", "cci"])
        .pick_file()
        .ok_or("No game was chosen.")?;
    let chosen = check(chosen)?;
    let _ = std::fs::write(remembered, chosen.to_string_lossy().as_bytes());
    Ok(chosen)
}

fn check(rom: PathBuf) -> Result<PathBuf, String> {
    match is_the_game(&rom) {
        Some(true) => Ok(rom),
        Some(false) => Err(format!("{}\n\nis not the USA release of Kid Icarus: Uprising, which this version is built from.", rom.display())),
        None => Err(format!("{}\n\ncould not be read as a 3DS game card image (.3ds).", rom.display())),
    }
}

/// whether a card image is the release the library is built from, none when
/// it is not a card image at all.
fn is_the_game(rom: &Path) -> Option<bool> {
    let mut header = [0; 0x110];
    std::fs::File::open(rom).ok()?.read_exact(&mut header).ok()?;
    media_id(&header).map(|id| id == TITLE)
}

/// a card image's (NCSD) media id: "NCSD" at 0x100, the id at 0x108.
fn media_id(header: &[u8]) -> Option<u64> {
    (header.get(0x100..0x104)? == b"NCSD").then_some(())?;
    Some(u64::from_le_bytes(header.get(0x108..0x110)?.try_into().ok()?))
}

/// says what stopped the game from starting, and stops.
pub fn fail(message: &str) -> ! {
    log::error!("{message}");
    rfd::MessageDialog::new()
        .set_title(NAME)
        .set_level(rfd::MessageLevel::Error)
        .set_description(message)
        .set_buttons(rfd::MessageButtons::Ok)
        .show();
    std::process::exit(1);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_usa_card_is_known_by_its_media_id() {
        let mut header = vec![0; 0x110];
        assert_eq!(media_id(&header), None);
        header[0x100..0x104].copy_from_slice(b"NCSD");
        header[0x108..0x110].copy_from_slice(&TITLE.to_le_bytes());
        assert_eq!(media_id(&header), Some(TITLE));
        header[0x108] = 0x01; // another release
        assert_ne!(media_id(&header), Some(TITLE));
        assert_eq!(media_id(&header[..0x10C]), None);
    }

    #[test]
    fn the_game_folder_is_the_nearest_one_above_with_the_library() {
        let base = std::env::temp_dir().join(format!("kiu-launcher-test-{}", std::process::id()));
        let library = base.join("game").join(LIBRARY);
        std::fs::create_dir_all(library.parent().unwrap()).unwrap();
        std::fs::write(&library, b"").unwrap();
        let deep = base.join("game/tools/zakuro/target/release/kid-icarus-uprising.exe");
        assert_eq!(root_above(&deep), Some(base.join("game")));
        assert_eq!(root_above(&base.join("game/Kid Icarus Uprising.exe")), Some(base.join("game")));
        assert_eq!(root_above(&base.join("elsewhere/program.exe")), None);
        let _ = std::fs::remove_dir_all(&base);
    }
}
