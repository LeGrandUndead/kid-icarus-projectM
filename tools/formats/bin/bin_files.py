from pathlib import Path
import shutil

# CHANGE THESE TWO PATHS
SOURCE = Path(r"D:\Games\Kid icarus\ROM\gameFiles\RomFS")
OUTPUT = Path(r"D:\Games\Kid icarus\ROM\all_bin_files")

OUTPUT.mkdir(parents=True, exist_ok=True)

bin_files = list(SOURCE.rglob("*.bin"))

print(f"Found {len(bin_files)} .bin files.\n")

for i, src in enumerate(bin_files, 1):
    # Get relative path
    relative = src.relative_to(SOURCE)

    # Example:
    # us\player\m000\character\eff_00.bin
    #
    # becomes:
    # us__player__m000__character__eff_00.bin

    new_name = "__".join(relative.parts)

    dst = OUTPUT / new_name

    shutil.copy2(src, dst)

    print(f"[{i}/{len(bin_files)}] {relative} -> {new_name}")

print()
print("Done!")
print(f"Copied {len(bin_files)} files to:")
print(OUTPUT)