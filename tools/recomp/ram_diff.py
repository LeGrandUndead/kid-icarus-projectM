"""Compare RAM snapshots saved with F7 (launch.py --ram-snapshots).

Finds the addresses whose value matches a sequence you observed in game, for
example a power's remaining uses going 4 -> 3 -> 2 across three snapshots:

    python ram_diff.py s1.bin s2.bin s3.bin --values 4 3 2
    python ram_diff.py s1.bin s2.bin --values 0 1 --width 4

--width is the value size in bytes (1, 2 or 4). Use "*" in --values for
"any value", and --changed / --same to require the value to differ or stay
equal between all snapshots. Prints at most --limit matches.
"""
import argparse
import struct

PAGE = 4096


def load(path):
    """Returns {page address: page bytes} for one snapshot."""
    pages = {}
    with open(path, "rb") as f:
        if f.read(8) != b"KIURAM1\0":
            raise SystemExit(f"{path}: not a KIU RAM snapshot")
        f.read(8)  # frame number
        while True:
            head = f.read(4)
            if len(head) < 4:
                break
            address = struct.unpack("<I", head)[0]
            pages[address] = f.read(PAGE)
    return pages


def value(pages, address, width):
    page = pages.get(address - address % PAGE)
    if page is None:
        return 0  # pages that were all zero are not stored
    offset = address % PAGE
    return int.from_bytes(page[offset:offset + width], "little")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("snapshots", nargs="+")
    ap.add_argument("--values", nargs="+", help="expected value in each snapshot, or *")
    ap.add_argument("--width", type=int, default=1, choices=(1, 2, 4))
    ap.add_argument("--changed", action="store_true", help="value differs between every pair of neighbours")
    ap.add_argument("--same", action="store_true", help="value is equal in all snapshots")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()
    if args.values and len(args.values) != len(args.snapshots):
        raise SystemExit("give one --values entry per snapshot")

    snapshots = [load(path) for path in args.snapshots]
    wanted = [None if v == "*" else int(v, 0) for v in (args.values or ["*"] * len(snapshots))]
    common = set(snapshots[0])
    for pages in snapshots[1:]:
        common |= set(pages)

    found = 0
    for page_address in sorted(common):
        for offset in range(0, PAGE, args.width):
            address = page_address + offset
            seen = [value(pages, address, args.width) for pages in snapshots]
            if any(w is not None and w != v for w, v in zip(wanted, seen)):
                continue
            if args.changed and any(a == b for a, b in zip(seen, seen[1:])):
                continue
            if args.same and len(set(seen)) != 1:
                continue
            print(f"0x{address:08X}  " + "  ".join(str(v) for v in seen))
            found += 1
            if found >= args.limit:
                print(f"... stopped at {args.limit} matches (use --limit)")
                return
    print(f"{found} matches")


if __name__ == "__main__":
    main()
