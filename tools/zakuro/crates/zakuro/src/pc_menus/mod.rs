//! The menus the PC draws itself, over the game's own (whose lower screen is
//! not shown): the game's art, laid out for a 16:9 window, driven by the
//! game's own state. The game keeps deciding what happens; the PC draws,
//! and turns the player's pointing and clicking into the game's input.
//!
//! - `screens`: which screens are redrawn, as data (buttons, touches, the
//!   game's navigation map);
//! - `picture`, `art`: the buttons cut from the game's sheets, with their
//!   glows and pointer masks, prepared off the game's thread;
//! - `buttons`: drawing a screen's buttons and vine, pointing, clicking,
//!   dragging; `motion` (their springs and sway), `vine` (its shape);
//! - `cursor`: walking the game's own cursor to what the pointer points at;
//! - `scene`: the main menu's animated scene behind the buttons (its own
//!   pack of pictures and character frames, made by tools/idols).
//!
//! Everything is read from the menu art pack on the player's machine
//! (`menu_art_pack`); nothing from the game is in this code but
//! coordinates and texture fingerprints.

pub mod art;
pub mod buttons;
pub mod cursor;
pub mod motion;
pub mod picture;
pub mod scene;
pub mod screens;
pub mod vine;
mod state;

pub use state::PcMenus;

use std::path::PathBuf;
use std::sync::OnceLock;

/// The menu art pack (`KIU_MENU_PACK`, set by the launcher): the game's menu
/// art rebuilt from the player's ROM, and the main menu scene's pack in its
/// `scene-040` folder. Read once.
pub fn menu_art_pack() -> Option<PathBuf> {
    static PACK: OnceLock<Option<PathBuf>> = OnceLock::new();
    PACK.get_or_init(|| std::env::var_os("KIU_MENU_PACK").map(PathBuf::from).filter(|p| p.is_dir())).clone()
}
