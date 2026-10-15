# Working from another PC (laptop)

This repository holds only code and documentation. The game and everything
made from it stay on your own machines and are never committed.

## First time

1. `git clone https://github.com/LeGrandUndead/kid-icarus-projectM.git "Kid icarus"`
2. Copy these local-only items from the main PC once (USB drive or your own
   private cloud). They are ignored by Git on purpose:
   - `Kid Icarus - Uprising (USA) (En,Fr,Es).3ds` and `ROM\` (your game)
   - `build\` (recompiled game library, generated code, UI catalog, saves)
   - `tools\toolchains\` (portable Rust/MinGW), `tools\3dsrecomp\`,
     `tools\python-libs\`
   - optional: `tools\zakuro\target\release\*.exe` to skip the first build
3. Install Python 3.11+.
4. Build the runtime: `powershell -File tools\zakuro\Build-KIU-Runtime.ps1`
   (or copy the executables, see above).

## Every time

- `git pull` to get the latest code, then use the usual launchers
  (`Launch-KIU-PC-Interface.cmd`, ...).
- Saves are per machine (inside `build\user-data`); copy that folder if you
  want the same progress on both.

## Never commit

The `.gitignore` already excludes the ROM, `build\`, `archive\`, toolchains,
`mocks\` (PDFs with game art) and tool caches. Before pushing, a quick check:
`git diff --cached --name-only` must not list `.3ds`, `.bcres`, `.arc`,
`.dll`, `.exe`, images of the game or anything under `ROM\` or `build\`.
