from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import argparse
import csv
import re
import sys


DIRECT_KEYS = {
    "motionName_": 50,
    "motifModelName_": 45,
    "modelName": 40,
}

LOGICAL_OBJECT_KEYS = {
    "sModelName_",
}


SCOPE_PATTERNS = [
    re.compile(r"^us/(demo)/([^/]+)"),
    re.compile(r"^us/(doll)/([^/]+)"),
    re.compile(r"^us/(stage)/([^/]+)"),
    re.compile(r"^us/(player)/([^/]+)"),
    re.compile(r"^us/(npc)/([^/]+)"),
    re.compile(r"^us/(menu)/([^/]+)"),
]


def normalize(path: str) -> str:
    return path.replace("\\", "/")


def outer_path(path: str) -> str:
    return normalize(path).split("::", 1)[0]


def scope(path: str):
    p = normalize(path)
    for rx in SCOPE_PATTERNS:
        m = rx.match(p)
        if m:
            return (m.group(1), m.group(2))

    outer = outer_path(p)
    parts = outer.split("/")
    if len(parts) >= 2:
        return ("outer", "/".join(parts[:2]))
    return ("outer", outer)


def common_prefix_segments(a: str, b: str) -> int:
    aa = normalize(a).split("::", 1)[0].split("/")
    bb = normalize(b).split("::", 1)[0].split("/")

    n = 0
    for x, y in zip(aa, bb):
        if x != y:
            break
        n += 1
    return n


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Refine KIU PSLB->CGFX string matches into higher-confidence "
            "resource edges using exact key semantics and path locality."
        )
    )
    ap.add_argument("edges_csv", type=Path)
    ap.add_argument("string_refs_csv", type=Path)
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("RESOURCE_GRAPH_REFINED"),
    )
    args = ap.parse_args()

    if not args.edges_csv.is_file():
        print(f"ERROR: missing {args.edges_csv}", file=sys.stderr)
        return 1
    if not args.string_refs_csv.is_file():
        print(f"ERROR: missing {args.string_refs_csv}", file=sys.stderr)
        return 1

    out = args.output
    out.mkdir(parents=True, exist_ok=True)

    edge_rows = read_csv(args.edges_csv)
    string_rows = read_csv(args.string_refs_csv)

    # How many distinct CGFX candidates exist globally for each matched name?
    value_candidates = defaultdict(set)
    for row in edge_rows:
        value_candidates[row["value"]].add(
            (row["cgfx_virtual_path"], row["cgfx_sha1"])
        )

    # Group candidate edges by one exact PSLB reference occurrence.
    grouped = defaultdict(list)

    for row in edge_rows:
        key = row["pslb_key"]
        if key not in DIRECT_KEYS:
            continue

        ref_id = (
            row["pslb_virtual_path"],
            row["pslb_sha1"],
            row["json_path"],
            key,
            row["value"],
        )
        grouped[ref_id].append(row)

    resolved_rows = []
    ambiguous_rows = []

    for ref_id, candidates in grouped.items():
        (
            pslb_virtual_path,
            pslb_sha1,
            json_path,
            pslb_key,
            value,
        ) = ref_id

        pscope = scope(pslb_virtual_path)
        p_outer = outer_path(pslb_virtual_path)
        global_candidate_count = len(value_candidates[value])

        scored = []
        seen = set()

        for row in candidates:
            candidate_id = (
                row["cgfx_virtual_path"],
                row["cgfx_sha1"],
            )
            if candidate_id in seen:
                continue
            seen.add(candidate_id)

            cgfx_path = row["cgfx_virtual_path"]
            cscope = scope(cgfx_path)
            c_outer = outer_path(cgfx_path)

            score = DIRECT_KEYS[pslb_key]
            reasons = [f"key:{pslb_key}"]

            if cscope == pscope:
                score += 100
                reasons.append("same-scope")

            if c_outer == p_outer:
                score += 120
                reasons.append("same-outer-container")

            prefix = common_prefix_segments(pslb_virtual_path, cgfx_path)
            if prefix:
                score += prefix * 5
                reasons.append(f"common-prefix:{prefix}")

            if global_candidate_count == 1:
                score += 40
                reasons.append("globally-unique-name-hit")

            scored.append(
                (
                    score,
                    row,
                    ";".join(reasons),
                )
            )

        scored.sort(
            key=lambda x: (
                -x[0],
                x[1]["cgfx_virtual_path"],
                x[1]["cgfx_sha1"],
            )
        )

        if not scored:
            continue

        top_score = scored[0][0]
        second_score = scored[1][0] if len(scored) > 1 else None
        top_ties = [x for x in scored if x[0] == top_score]
        gap = top_score - second_score if second_score is not None else None

        # High confidence if:
        # - only one candidate and it is a strong exact-key match, or
        # - path locality clearly separates the winner.
        if len(scored) == 1:
            confidence = "high"
        elif len(top_ties) == 1 and gap is not None and gap >= 40:
            confidence = "high"
        elif len(top_ties) == 1 and gap is not None and gap >= 15:
            confidence = "medium"
        else:
            confidence = "ambiguous"

        for rank, (score, row, reasons) in enumerate(scored, 1):
            output_row = {
                "pslb_virtual_path": pslb_virtual_path,
                "pslb_sha1": pslb_sha1,
                "json_path": json_path,
                "pslb_key": pslb_key,
                "value": value,
                "candidate_rank": rank,
                "candidate_count": len(scored),
                "global_name_hit_count": global_candidate_count,
                "score": score,
                "top_score_gap": "" if gap is None else gap,
                "confidence": confidence if rank == 1 else "alternate",
                "reasons": reasons,
                "cgfx_virtual_path": row["cgfx_virtual_path"],
                "cgfx_sha1": row["cgfx_sha1"],
                "cgfx_size": row["cgfx_size"],
            }

            if confidence == "ambiguous":
                ambiguous_rows.append(output_row)
            else:
                resolved_rows.append(output_row)

    # sModelName_ behaves very differently: the cross-reference run showed
    # it often names a logical scene/model object ("Pit", "StageModel", etc.)
    # rather than a direct CGFX asset. Preserve it as a separate relation.
    logical_rows = []
    seen_logical = set()

    for row in string_rows:
        if row.get("key") not in LOGICAL_OBJECT_KEYS:
            continue

        key = (
            row.get("sha1", ""),
            row.get("json_path", ""),
            row.get("key", ""),
            row.get("value", ""),
        )
        if key in seen_logical:
            continue
        seen_logical.add(key)

        logical_rows.append({
            "pslb_sha1": row.get("sha1", ""),
            "json_path": row.get("json_path", ""),
            "key": row.get("key", ""),
            "logical_object_name": row.get("value", ""),
        })

    fields = [
        "pslb_virtual_path",
        "pslb_sha1",
        "json_path",
        "pslb_key",
        "value",
        "candidate_rank",
        "candidate_count",
        "global_name_hit_count",
        "score",
        "top_score_gap",
        "confidence",
        "reasons",
        "cgfx_virtual_path",
        "cgfx_sha1",
        "cgfx_size",
    ]

    resolved_csv = out / "direct_graphics_edges_ranked.csv"
    ambiguous_csv = out / "ambiguous_graphics_edges.csv"
    logical_csv = out / "logical_object_refs.csv"

    write_csv(resolved_csv, fields, resolved_rows)
    write_csv(ambiguous_csv, fields, ambiguous_rows)
    write_csv(
        logical_csv,
        ["pslb_sha1", "json_path", "key", "logical_object_name"],
        logical_rows,
    )

    top_resolved = [r for r in resolved_rows if r["candidate_rank"] == 1]
    high = [r for r in top_resolved if r["confidence"] == "high"]
    medium = [r for r in top_resolved if r["confidence"] == "medium"]

    # Count distinct exact reference occurrences in ambiguous group.
    ambiguous_refs = {
        (
            r["pslb_virtual_path"],
            r["pslb_sha1"],
            r["json_path"],
            r["pslb_key"],
            r["value"],
        )
        for r in ambiguous_rows
    }

    by_key = defaultdict(lambda: {"high": 0, "medium": 0, "ambiguous": 0})
    for r in high:
        by_key[r["pslb_key"]]["high"] += 1
    for r in medium:
        by_key[r["pslb_key"]]["medium"] += 1
    for ref in ambiguous_refs:
        by_key[ref[3]]["ambiguous"] += 1

    summary = out / "refined_graph_summary.txt"
    with summary.open("w", encoding="utf-8") as f:
        f.write("=" * 88 + "\n")
        f.write("KIU REFINED PSLB -> CGFX GRAPH\n")
        f.write("=" * 88 + "\n\n")

        f.write(
            "Direct asset keys used: motionName_, motifModelName_, modelName\n"
        )
        f.write(
            "sModelName_ is separated as a logical-object relation because "
            "its CGFX hit rate is low and values often name scene objects.\n\n"
        )

        f.write(f"Direct reference groups : {len(grouped)}\n")
        f.write(f"High-confidence winners : {len(high)}\n")
        f.write(f"Medium-confidence       : {len(medium)}\n")
        f.write(f"Ambiguous references    : {len(ambiguous_refs)}\n")
        f.write(f"Logical sModel refs     : {len(logical_rows)}\n\n")

        f.write("BY KEY\n")
        f.write("-" * 88 + "\n")
        for key in sorted(by_key):
            s = by_key[key]
            f.write(
                f"{key:20s} high={s['high']:6d} "
                f"medium={s['medium']:6d} ambiguous={s['ambiguous']:6d}\n"
            )

        f.write("\nSAMPLE HIGH-CONFIDENCE EDGES\n")
        f.write("-" * 88 + "\n")
        for r in high[:100]:
            f.write(
                f"{r['pslb_virtual_path']}\n"
                f"  {r['json_path']} | {r['pslb_key']}={r['value']}\n"
                f"  -> {r['cgfx_virtual_path']}\n"
                f"  score={r['score']} reasons={r['reasons']}\n\n"
            )

        f.write("\nSAMPLE AMBIGUOUS REFERENCES\n")
        f.write("-" * 88 + "\n")
        shown = set()
        count = 0
        for r in ambiguous_rows:
            ref = (
                r["pslb_virtual_path"],
                r["json_path"],
                r["pslb_key"],
                r["value"],
            )
            if ref in shown:
                continue
            shown.add(ref)
            f.write(
                f"{r['pslb_virtual_path']}\n"
                f"  {r['json_path']} | {r['pslb_key']}={r['value']}\n"
                f"  candidates={r['candidate_count']} top_score={r['score']}\n\n"
            )
            count += 1
            if count >= 50:
                break

    print("=" * 72)
    print("REFINED RESOURCE GRAPH COMPLETE")
    print("=" * 72)
    print(f"Direct reference groups : {len(grouped)}")
    print(f"High confidence         : {len(high)}")
    print(f"Medium confidence       : {len(medium)}")
    print(f"Ambiguous               : {len(ambiguous_refs)}")
    print(f"Logical sModel refs     : {len(logical_rows)}")
    print()
    print(f"Summary   : {summary}")
    print(f"Ranked    : {resolved_csv}")
    print(f"Ambiguous : {ambiguous_csv}")
    print(f"Logical   : {logical_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
