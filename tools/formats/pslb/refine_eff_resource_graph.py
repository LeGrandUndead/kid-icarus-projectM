from __future__ import annotations

from collections import defaultdict, Counter
from pathlib import Path
import argparse
import csv
import sys


DIRECT_FIELDS = {
    "particle_name",
    "model_name",
}

ATTACHMENT_FIELDS = {
    "particle_node",
}

INTERNAL_FIELDS = {
    "trigger_target_section",
}


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def resource_scope(path: str) -> str:
    """
    Compare the physical asset folder that owns an EFF file with the outer
    CGFX resource location.

    Examples:
      us/demo/003/demo/eff_00.bin
      us/demo/003/demo/effect.bcres
         -> same scope: us/demo/003/demo

      us/player/a0/character/eff_00.bin
      us/player/a0/character/effect.bcres
         -> same scope: us/player/a0/character
    """
    outer = path.replace("\\", "/").split("::", 1)[0]
    parts = outer.split("/")
    if len(parts) <= 1:
        return outer
    return "/".join(parts[:-1])


def category(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    if len(parts) >= 2 and parts[0] == "us":
        return parts[1]
    return "(other)"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Refine KIU EFF->CGFX string matches into strong local asset edges, "
            "global/shared candidates, attachment-node relations, and internal "
            "EFF trigger-section relations."
        )
    )
    ap.add_argument("matches_csv", type=Path)
    ap.add_argument("refs_csv", type=Path)
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("EFF_GRAPH_REFINED"),
    )
    args = ap.parse_args()

    if not args.matches_csv.is_file():
        print(f"ERROR: missing {args.matches_csv}", file=sys.stderr)
        return 1
    if not args.refs_csv.is_file():
        print(f"ERROR: missing {args.refs_csv}", file=sys.stderr)
        return 1

    out = args.output
    out.mkdir(parents=True, exist_ok=True)

    matches = read_csv(args.matches_csv)
    refs = read_csv(args.refs_csv)

    # ------------------------------------------------------------
    # Build CGFX candidates for each exact EFF reference occurrence
    # ------------------------------------------------------------

    grouped = defaultdict(list)
    global_candidates = defaultdict(set)

    for row in matches:
        field = row["field"]
        if field not in DIRECT_FIELDS:
            continue

        ref_id = (
            row["eff_path"],
            row["section"],
            row["record_kind"],
            row["record_index"],
            field,
            row["value"],
        )

        grouped[ref_id].append(row)
        global_candidates[row["value"]].add(
            (row["cgfx_virtual_path"], row["cgfx_sha1"])
        )

    strong_local = []
    shared_global = []
    ambiguous = []

    for ref_id, candidates in grouped.items():
        (
            eff_path,
            section,
            record_kind,
            record_index,
            field,
            value,
        ) = ref_id

        eff_scope = resource_scope(eff_path)

        # De-duplicate repeated candidate rows.
        unique = {}
        for row in candidates:
            key = (row["cgfx_virtual_path"], row["cgfx_sha1"])
            unique[key] = row

        candidates = list(unique.values())

        local = [
            row
            for row in candidates
            if resource_scope(row["cgfx_virtual_path"]) == eff_scope
        ]

        base = {
            "eff_path": eff_path,
            "eff_category": category(eff_path),
            "section": section,
            "record_kind": record_kind,
            "record_index": record_index,
            "field": field,
            "value": value,
            "candidate_count": len(candidates),
            "local_candidate_count": len(local),
            "global_name_hit_count": len(global_candidates[value]),
        }

        if len(local) == 1:
            row = local[0]
            strong_local.append({
                **base,
                "relation": "direct-local",
                "confidence": "high",
                "reason": "exact structured EFF name + exactly one CGFX candidate in same asset folder",
                "cgfx_virtual_path": row["cgfx_virtual_path"],
                "cgfx_sha1": row["cgfx_sha1"],
                "cgfx_size": row["cgfx_size"],
            })
            continue

        # If no local copy exists but the name appears in exactly one CGFX
        # resource across the whole ROM, preserve it as a useful shared/global
        # candidate instead of pretending it is a local edge.
        if len(local) == 0 and len(global_candidates[value]) == 1:
            row = candidates[0]
            shared_global.append({
                **base,
                "relation": "shared-global-candidate",
                "confidence": "medium",
                "reason": "no same-folder CGFX; exact name occurs in only one CGFX resource globally",
                "cgfx_virtual_path": row["cgfx_virtual_path"],
                "cgfx_sha1": row["cgfx_sha1"],
                "cgfx_size": row["cgfx_size"],
            })
            continue

        # Everything else remains ambiguous/shared.
        for rank, row in enumerate(
            sorted(
                candidates,
                key=lambda r: (
                    resource_scope(r["cgfx_virtual_path"]) != eff_scope,
                    r["cgfx_virtual_path"],
                    r["cgfx_sha1"],
                ),
            ),
            1,
        ):
            ambiguous.append({
                **base,
                "relation": "ambiguous",
                "confidence": "ambiguous",
                "reason": (
                    "multiple local candidates"
                    if len(local) > 1
                    else "no unique local/global candidate"
                ),
                "candidate_rank": rank,
                "cgfx_virtual_path": row["cgfx_virtual_path"],
                "cgfx_sha1": row["cgfx_sha1"],
                "cgfx_size": row["cgfx_size"],
            })

    # ------------------------------------------------------------
    # Preserve node attachments and trigger-section edges separately
    # ------------------------------------------------------------

    attachment_rows = []
    internal_rows = []
    metadata_rows = []

    seen_attachment = set()
    seen_internal = set()
    seen_metadata = set()

    for row in refs:
        field = row["field"]

        if field in ATTACHMENT_FIELDS:
            value = row["value"]
            if value == "none":
                continue

            key = (
                row["eff_path"],
                row["section"],
                row["record_kind"],
                row["record_index"],
                field,
                value,
            )
            if key in seen_attachment:
                continue
            seen_attachment.add(key)

            attachment_rows.append({
                "eff_path": row["eff_path"],
                "section": row["section"],
                "record_kind": row["record_kind"],
                "record_index": row["record_index"],
                "field": field,
                "node_name": value,
                "relation": "particle-attaches-to-node",
            })

        elif field in INTERNAL_FIELDS:
            key = (
                row["eff_path"],
                row["section"],
                row["record_kind"],
                row["record_index"],
                field,
                row["value"],
            )
            if key in seen_internal:
                continue
            seen_internal.add(key)

            internal_rows.append({
                "eff_path": row["eff_path"],
                "section": row["section"],
                "record_kind": row["record_kind"],
                "record_index": row["record_index"],
                "field": field,
                "target_section": row["value"],
                "relation": "trigger-targets-eff-section",
            })

        elif field not in DIRECT_FIELDS:
            # Keep non-direct textual fields available without mixing them into
            # the asset graph.
            key = (
                row["eff_path"],
                row["section"],
                row["record_kind"],
                row["record_index"],
                field,
                row["value"],
            )
            if key in seen_metadata:
                continue
            seen_metadata.add(key)

            metadata_rows.append({
                "eff_path": row["eff_path"],
                "section": row["section"],
                "record_kind": row["record_kind"],
                "record_index": row["record_index"],
                "field": field,
                "value": row["value"],
            })

    # ------------------------------------------------------------
    # Output
    # ------------------------------------------------------------

    direct_fields = [
        "eff_path",
        "eff_category",
        "section",
        "record_kind",
        "record_index",
        "field",
        "value",
        "candidate_count",
        "local_candidate_count",
        "global_name_hit_count",
        "relation",
        "confidence",
        "reason",
        "cgfx_virtual_path",
        "cgfx_sha1",
        "cgfx_size",
    ]

    write_csv(
        out / "strong_local_eff_to_cgfx_edges.csv",
        direct_fields,
        strong_local,
    )
    write_csv(
        out / "shared_global_eff_to_cgfx_candidates.csv",
        direct_fields,
        shared_global,
    )

    ambiguous_fields = direct_fields[:-3] + [
        "candidate_rank",
        "cgfx_virtual_path",
        "cgfx_sha1",
        "cgfx_size",
    ]
    write_csv(
        out / "ambiguous_eff_to_cgfx_candidates.csv",
        ambiguous_fields,
        ambiguous,
    )

    write_csv(
        out / "particle_node_relations.csv",
        [
            "eff_path",
            "section",
            "record_kind",
            "record_index",
            "field",
            "node_name",
            "relation",
        ],
        attachment_rows,
    )

    write_csv(
        out / "trigger_section_relations.csv",
        [
            "eff_path",
            "section",
            "record_kind",
            "record_index",
            "field",
            "target_section",
            "relation",
        ],
        internal_rows,
    )

    write_csv(
        out / "eff_text_metadata.csv",
        [
            "eff_path",
            "section",
            "record_kind",
            "record_index",
            "field",
            "value",
        ],
        metadata_rows,
    )

    # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------

    by_field = defaultdict(Counter)
    by_category = defaultdict(Counter)

    for row in strong_local:
        by_field[row["field"]]["strong_local"] += 1
        by_category[(row["eff_category"], row["field"])]["strong_local"] += 1

    for row in shared_global:
        by_field[row["field"]]["shared_global"] += 1
        by_category[(row["eff_category"], row["field"])]["shared_global"] += 1

    ambiguous_refs = {
        (
            row["eff_path"],
            row["section"],
            row["record_kind"],
            row["record_index"],
            row["field"],
            row["value"],
        )
        for row in ambiguous
    }

    for ref in ambiguous_refs:
        eff_path, _, _, _, field, _ = ref
        by_field[field]["ambiguous"] += 1
        by_category[(category(eff_path), field)]["ambiguous"] += 1

    summary = out / "eff_refined_graph_summary.txt"
    with summary.open("w", encoding="utf-8") as f:
        f.write("=" * 92 + "\n")
        f.write("KIU REFINED EFF -> CGFX RESOURCE GRAPH\n")
        f.write("=" * 92 + "\n\n")

        f.write("Semantic treatment\n")
        f.write("------------------\n")
        f.write("particle_name       -> direct CGFX particle/emitter identifier candidate\n")
        f.write("model_name          -> direct CGFX effect-model identifier candidate\n")
        f.write("particle_node       -> attachment/bone/node relation, NOT asset identity\n")
        f.write("trigger_target_section -> internal EFF section relation, NOT CGFX identity\n")
        f.write("model_s* / particle_mode -> metadata/control fields, kept outside asset graph\n\n")

        f.write(f"Exact direct reference groups : {len(grouped)}\n")
        f.write(f"Strong same-folder edges      : {len(strong_local)}\n")
        f.write(f"Unique shared/global candidates: {len(shared_global)}\n")
        f.write(f"Ambiguous direct references   : {len(ambiguous_refs)}\n")
        f.write(f"Particle node relations       : {len(attachment_rows)}\n")
        f.write(f"Trigger->section relations    : {len(internal_rows)}\n\n")

        f.write("BY DIRECT FIELD\n")
        f.write("-" * 92 + "\n")
        for field in sorted(by_field):
            s = by_field[field]
            f.write(
                f"{field:20s} "
                f"local={s['strong_local']:7d} "
                f"global={s['shared_global']:7d} "
                f"ambiguous={s['ambiguous']:7d}\n"
            )

        f.write("\nBY CATEGORY / FIELD\n")
        f.write("-" * 92 + "\n")
        for (cat, field) in sorted(by_category):
            s = by_category[(cat, field)]
            f.write(
                f"{cat:12s} {field:18s} "
                f"local={s['strong_local']:7d} "
                f"global={s['shared_global']:7d} "
                f"ambiguous={s['ambiguous']:7d}\n"
            )

        f.write("\nSAMPLE STRONG LOCAL EDGES\n")
        f.write("-" * 92 + "\n")
        for row in strong_local[:120]:
            f.write(
                f"{row['eff_path']}\n"
                f"  {row['section']}[{row['record_index']}] "
                f"{row['field']}={row['value']}\n"
                f"  -> {row['cgfx_virtual_path']}\n\n"
            )

        f.write("\nSAMPLE SHARED/GLOBAL CANDIDATES\n")
        f.write("-" * 92 + "\n")
        for row in shared_global[:80]:
            f.write(
                f"{row['eff_path']}\n"
                f"  {row['field']}={row['value']}\n"
                f"  -> {row['cgfx_virtual_path']}\n\n"
            )

    print("=" * 72)
    print("REFINED EFF RESOURCE GRAPH COMPLETE")
    print("=" * 72)
    print(f"Direct reference groups : {len(grouped)}")
    print(f"Strong local edges      : {len(strong_local)}")
    print(f"Shared/global candidates: {len(shared_global)}")
    print(f"Ambiguous references    : {len(ambiguous_refs)}")
    print(f"Particle node relations : {len(attachment_rows)}")
    print(f"Trigger relations       : {len(internal_rows)}")
    print()
    print(f"Summary : {summary}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
