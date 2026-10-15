"""Map original KIU menu components for a native presentation adapter.

Reads the user's extracted ROM; never modifies it. Generated definitions contain
game data and belong under ignored build/, not in source control. An asset name
is NOT evidence that a menu is currently active or that an action is available.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools/formats/darc'), str(ROOT / 'tools/formats/pslb')]
from darc_tool_fixed import parse_darc
from pslb_tool import parse_pslb, to_python


def walk(value, path='$'):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, path + '.' + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f'{path}[{index}]')


def describe(definition):
    if not isinstance(definition, dict) or not isinstance(definition.get('menuID_'), str):
        raise ValueError('not a named menu definition')
    bodies = []
    for index, group in enumerate(definition.get('menuParams_', [])):
        params = group.get('params_', [])
        names = [p['bodyName_'] for p in params if isinstance(p.get('bodyName_'), str)]
        functions = {}
        for param in params:
            functions.update(param.get('funcs_', {}))
        bodies.append(dict(index=index, names=names,
                           allocation=group.get('allocateSize_'),
                           channel=group.get('anmChrChannel_'),
                           # Preserve complete original commands, timing and class IDs.
                           parameters=params, functions=sorted(functions)))
    declared = {name for body in bodies for name in body['names']}
    navigation, unresolved, dialogue, sounds = [], [], [], []
    for path, value in walk(definition):
        if not isinstance(value, dict):
            continue
        if 'bodyName_' in value and any(k.endswith('BodyName_') for k in value):
            edges = {k: v for k, v in value.items() if k.endswith('BodyName_')}
            navigation.append(dict(path=path, source=value['bodyName_'], edges=edges))
            for key, target in edges.items():
                if target not in declared:
                    unresolved.append(dict(path=path + '.' + key, target=target))
        if 'talkFace_' in value or 'talkCaption_' in value:
            dialogue.append(dict(path=path, original=value))
        for key, sound in value.items():
            if key.endswith('SE_') or key == 'voiceId_':
                sounds.append(dict(path=path + '.' + key, value=sound))
    return dict(menu_id=definition['menuID_'], bodies=bodies, navigation=navigation,
                unresolved_navigation=unresolved, dialogue=dialogue, sounds=sounds,
                runtime_state_verified=False, actions_enabled=False)


def audit(romfs, output):
    output.mkdir(parents=True, exist_ok=True)
    rows, failures = [], []
    for archive in sorted((romfs / 'us/menu').rglob('json.arc')):
        raw = archive.read_bytes()
        source = archive.relative_to(romfs).as_posix()
        try:
            entries = parse_darc(raw).entries
        except ValueError as error:
            failures.append(dict(source=source, error=str(error)))
            continue
        for entry in entries:
            if entry.is_dir:
                continue
            try:
                data = raw[entry.data_offset:entry.data_offset + entry.size]
                definition = to_python(parse_pslb(data).root)
                description = describe(definition)
                # Archive folder identifies regional/layout variants sharing an ID.
                variant = archive.relative_to(romfs / 'us/menu').parts[0]
                name = f'{variant}-{entry.index:03}-{description["menu_id"]}.json'
                description.update(source=source + '::' + entry.path,
                                   sha256=hashlib.sha256(data).hexdigest(),
                                   original_definition=definition)
                (output / name).write_text(json.dumps(description, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
                rows.append(dict(file=name, source=description['source'],
                                 menu_id=description['menu_id'], sha256=description['sha256'],
                                 bodies=len(description['bodies']),
                                 navigation_nodes=len(description['navigation']),
                                 unresolved_navigation=len(description['unresolved_navigation']),
                                 dialogue_events=len(description['dialogue'])))
            except (ValueError, TypeError, KeyError) as error:
                failures.append(dict(source=source + '::' + entry.path, error=str(error)))
    report = dict(schema=1, definitions=rows, failures=failures,
                  distinct_menus=len({row['menu_id'] for row in rows}),
                  scope='Static menu assets only; not live state, gameplay portraits or permission to invoke actions.',
                  proprietary_data='Local generated output. Do not commit or redistribute.')
    (output / 'index.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--romfs', type=Path, default=ROOT / 'ROM/gameFiles/RomFS')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/native-ui/catalog')
    args = parser.parse_args()
    if not (args.romfs / 'us/menu').is_dir():
        parser.error('extracted USA menu resources are missing')
    report = audit(args.romfs.resolve(), args.output.resolve())
    print(f'{len(report["definitions"])} definitions, {report["distinct_menus"]} distinct menu IDs, {len(report["failures"])} failures')
    return int(bool(report['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
