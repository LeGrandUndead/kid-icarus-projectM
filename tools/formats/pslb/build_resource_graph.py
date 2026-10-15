"""Package existing resource evidence; does not infer any new resource semantics.

Raw EFF files supply complete trigger-to-record links: the older relation CSV
does not include target indices. Only local matches of the three selected
PSLB class/key pairs are promoted, still explicitly labelled heuristic.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from test_eff_roundtrip import parse_eff, serialize_eff

TRUSTED = {('nID_', 0x2925C86E), ('nID_', 0x53FF32B1), ('effectID_', 0x08B0A34A)}


def rows(path):
    with path.open(newline='', encoding='utf-8-sig') as stream:
        yield from csv.DictReader(stream)


def write_csv(path, fields, values):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(values)


def build(graphics: Path, eff_graphics: Path, contexts: Path, romfs: Path, out: Path):
    nodes, edges, candidates = {}, set(), []
    records, triggers = {}, {}

    def node(kind, path, locator=''):
        identity = json.dumps([kind, path, locator], ensure_ascii=True, separators=(',', ':'))
        key = hashlib.sha256(identity.encode()).hexdigest()
        nodes[key] = dict(id=key, kind=kind, path=path, locator=locator)
        return key

    def edge(source, target, relation, confidence, evidence):
        edges.add((source, target, relation, confidence, evidence))

    for path in sorted(romfs.rglob('eff_00.bin')):
        blob = path.read_bytes()
        eff = parse_eff(blob)
        if serialize_eff(eff) != blob:
            raise ValueError(f'EFF roundtrip mismatch: {path}')
        relative = path.relative_to(romfs).as_posix()
        sections = {s.name.removesuffix('.gd'): s for s in eff.sections}
        for section in eff.sections:
            for index, record in enumerate(section.records):
                locator = f'{section.name}[{index}]'
                kind = 'eff_trigger' if section.name.startswith('effectTriggerData_') else 'eff_record'
                records[(relative, section.name, index)] = node(kind, relative, locator)
        for section in eff.sections:
            if not section.name.startswith('effectTriggerData_'):
                continue
            for index, record in enumerate(section.records):
                trigger_id = struct.unpack_from('<I', record, 0)[0]
                target_type = struct.unpack_from('<I', record, 0x28)[0]
                target_name = record[0x2C:0x4C].split(b'\0', 1)[0].decode('ascii')
                target_index = record[0x4F]
                target = sections[target_name]
                expected_prefix = {0: 'effectParticleData_', 1: 'effectModelData_'}[target_type]
                if not target.name.startswith(expected_prefix) or target_index >= len(target.records):
                    raise ValueError(f'Invalid trigger target: {relative}:{index}')
                source = records[(relative, section.name, index)]
                destination = records[(relative, target.name, target_index)]
                triggers[(relative, section.name, index)] = (source, trigger_id, target_name, target_index, target_type)
                edge(source, destination, 'eff_trigger_to_record', 'structural', 'raw EFF section/type/index validated')

    for row in rows(graphics):
        if row['confidence'] != 'high' or row['candidate_rank'] != '1':
            continue
        if row['pslb_key'] not in {'modelName', 'motifModelName_', 'motionName_'}:
            continue
        source = node('pslb_reference', row['pslb_virtual_path'], row['json_path'])
        target = node('cgfx', row['cgfx_virtual_path'])
        edge(source, target, 'pslb_to_cgfx', 'heuristic-high', row['reasons'])

    for row in rows(eff_graphics):
        source = records[(row['eff_path'], row['section'], int(row['record_index']))]
        target = node('cgfx', row['cgfx_virtual_path'])
        edge(source, target, 'eff_record_to_cgfx', 'heuristic-high', row['reason'])

    for row in rows(contexts):
        cls = int(row['class_value']) & 0xFFFFFFFF if row['class_value'] else None
        if row['local_match'] != '1':
            continue
        if (row['target_key'], cls) not in TRUSTED:
            candidates.append(row)
            continue
        key = (row['eff_path'], row['trigger_section'], int(row['trigger_index']))
        target, trigger_id, section, index, kind = triggers[key]
        if (trigger_id, section, index, kind) != (int(row['value']), row['target_section'],
                                                 int(row['target_index']), int(row['target_type'])):
            raise ValueError(f'Context CSV no longer matches raw EFF: {key}')
        source = node('pslb_reference', row['pslb_virtual_path'], row['json_path'] + '.' + row['target_key'])
        edge(source, target, 'pslb_to_eff_trigger', 'heuristic-high',
             f"same-folder match; class=0x{cls:08X}; key={row['target_key']}")

    if any(source not in nodes or target not in nodes for source, target, *_ in edges):
        raise ValueError('Dangling edge')
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / 'nodes.csv', ['id', 'kind', 'path', 'locator'], (nodes[k] for k in sorted(nodes)))
    fields = ['source', 'target', 'relation', 'confidence', 'evidence']
    write_csv(out / 'edges.csv', fields, (dict(zip(fields, e)) for e in sorted(edges)))
    context_fields = list(next(rows(contexts)))
    write_csv(out / 'candidate_pslb_to_eff_edges.csv', context_fields, candidates)
    summary = dict(nodes=len(nodes), edges=len(edges), relations=dict(Counter(e[2] for e in edges)),
                   candidate_local_rows=len(candidates), validated_eff_triggers=len(triggers),
                   dangling_edges=0,
                   caution='Cross-format edges are heuristics, not proven engine lookup behavior.',
                   inputs={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (graphics, eff_graphics, contexts)})
    text = json.dumps(summary, indent=2) + '\n'
    (out / 'resource_graph_summary.txt').write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graphics', type=Path)
    parser.add_argument('eff_graphics', type=Path)
    parser.add_argument('contexts', type=Path)
    parser.add_argument('--romfs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.graphics, args.eff_graphics, args.contexts, args.romfs, args.output)
