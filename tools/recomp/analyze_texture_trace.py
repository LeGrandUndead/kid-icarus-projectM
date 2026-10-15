#!/usr/bin/env python3
"""Summarize a KIU/Zakuro --texture-trace CSV without changing project data."""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


def as_int(row: dict[str, str], key: str) -> int:
    value = row.get(key, "0").strip()
    return int(value, 0) if value else 0


def as_float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "0").strip()
    return float(value) if value else 0.0


def summarize(path: Path) -> str:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))

    if not rows:
        return f"{path}\n  no texture states recorded\n"

    mip_requested = [r for r in rows if as_int(r, "requested_max") > 0]
    mip_loaded = [r for r in rows if as_int(r, "loaded_max") > 0]
    mip_linear = [r for r in rows if as_int(r, "mip_linear") != 0]
    split_filter = [r for r in rows if as_int(r, "mag_linear") != as_int(r, "min_linear")]
    biased = [r for r in rows if abs(as_float(r, "lod_bias")) > 1e-9]
    drawn = [r for r in rows if as_int(r, "drawn") != 0]
    legacy = {as_int(r, "legacy_sampling") for r in rows}
    formats = Counter(r.get("format", "?") for r in rows)
    max_requested = max(as_int(r, "requested_max") for r in rows)
    max_loaded = max(as_int(r, "loaded_max") for r in rows)

    lines = [
        str(path),
        f"  unique states                 : {len(rows)}",
        f"  legacy sampling flags         : {sorted(legacy)}",
        f"  requested mip chain           : {len(mip_requested)} ({len(mip_requested)/len(rows):.1%})",
        f"  actually loaded mip chain     : {len(mip_loaded)} ({len(mip_loaded)/len(rows):.1%})",
        f"  mip-linear states             : {len(mip_linear)} ({len(mip_linear)/len(rows):.1%})",
        f"  min filter differs from mag   : {len(split_filter)} ({len(split_filter)/len(rows):.1%})",
        f"  non-zero guest LOD bias       : {len(biased)} ({len(biased)/len(rows):.1%})",
        f"  render-target-backed states   : {len(drawn)} ({len(drawn)/len(rows):.1%})",
        f"  highest requested/loaded mip  : {max_requested} / {max_loaded}",
        "  formats                      : " + ", ".join(f"{name}={count}" for name, count in formats.most_common()),
    ]

    interesting = mip_requested or split_filter or biased
    if interesting:
        lines.append("  sample interesting states:")
        for r in interesting[:12]:
            lines.append(
                "    "
                f"u{r.get('unit')} {r.get('width')}x{r.get('height')} {r.get('format')} "
                f"addr={r.get('address')} mag/min/mip={r.get('mag_linear')}/{r.get('min_linear')}/{r.get('mip_linear')} "
                f"bias={r.get('lod_bias')} req={r.get('requested_min')}..{r.get('requested_max')} "
                f"loaded=0..{r.get('loaded_max')}"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, nargs="+", help="texture-states.csv file(s)")
    parser.add_argument("--output", type=Path, help="also write the summary to this file")
    args = parser.parse_args()

    reports = []
    for path in args.trace:
        if not path.is_file():
            parser.error(f"not a file: {path}")
        reports.append(summarize(path.resolve()))
    text = "\n".join(reports)
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
