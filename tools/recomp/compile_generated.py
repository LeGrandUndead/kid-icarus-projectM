"""Incremental, bounded-parallel C build for an evaluated recompilation backend.

This is our build driver, not an ARM translator. It can reuse 3dsrecomp's local
generated C without repeating discovery/code generation after every failure.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_all(source: Path, output: Path, compiler: Path, jobs: int, optimization: str) -> int:
    source, output, compiler = source.resolve(), output.resolve(), compiler.resolve()
    sources = sorted(source.glob('*.c'))
    if not sources or not (source / 'entries.c').is_file() or not (source / 'recomp.h').is_file():
        raise ValueError('Expected a generated source directory with entries.c and recomp.h')
    output.mkdir(parents=True, exist_ok=True)
    version = subprocess.check_output([str(compiler), '--version'], text=True)
    flags = [optimization, '-ffp-contract=off', '-fno-math-errno', '-w', '-I', str(source)]
    common = dict(compiler=str(compiler), compiler_sha256=digest(compiler), version=version,
                  flags=flags, headers={p.name: digest(p) for p in sorted(source.glob('*.h'))})
    common_hash = hashlib.sha256(json.dumps(common, sort_keys=True).encode()).hexdigest()
    manifest_path = output / 'compile-manifest.json'
    old = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    records = {}
    started = time.monotonic()

    def compile_one(path):
        identity = hashlib.sha256((common_hash + digest(path)).encode()).hexdigest()
        obj = output / (path.stem + '.o')
        prior = old.get('objects', {}).get(path.name, {})
        if (prior.get('identity') == identity and obj.is_file() and
                prior.get('object_sha256') == digest(obj)):
            return path.name, dict(identity=identity, object_sha256=prior['object_sha256']), True
        log = output / (path.stem + '.log')
        temporary = output / (path.stem + '.pending.o')
        with log.open('w') as stream:
            result = subprocess.run([str(compiler), *flags, '-c', str(path), '-o', str(temporary)],
                                    stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f'{path.name} failed; see {log}')
        temporary.replace(obj)
        return path.name, dict(identity=identity, object_sha256=digest(obj)), False

    # Write a manifest after each successful object; interrupted builds resume.
    def save_manifest():
        document = dict(schema=1, source=str(source), configuration=common,
                        objects={**old.get('objects', {}), **records})
        temporary = manifest_path.with_suffix('.pending.json')
        temporary.write_text(json.dumps(document, indent=2) + '\n')
        temporary.replace(manifest_path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(compile_one, p) for p in sources]
        for completed, future in enumerate(concurrent.futures.as_completed(futures), 1):
            name, record, cached = future.result()
            records[name] = record
            save_manifest()
            print(f'{completed}/{len(sources)} {name} {"cached" if cached else "compiled"}', flush=True)
    # GCC response files avoid Windows command-line length limits.
    response = output / 'objects.rsp'
    response.write_text('\n'.join('"' + str(output / (p.stem + '.o')).replace('\\', '/') + '"'
                                   for p in sources) + '\n')
    library = output / '0004000000030100.dll'
    temporary_library = output / '0004000000030100.pending.dll'
    with (output / 'link.log').open('w') as stream:
        result = subprocess.run([str(compiler), '-shared', '-static-libgcc', '-o', str(temporary_library),
                                 '@' + str(response)], stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'Link failed; see {output / "link.log"}')
    temporary_library.replace(library)
    (output / 'build-result.json').write_text(json.dumps(dict(library=str(library), sha256=digest(library),
        source_files=len(sources), elapsed_seconds=time.monotonic() - started,
        optimization=optimization, translation_backend='3dsrecomp; unchanged generated C'), indent=2) + '\n')
    print(f'Built {library} in {time.monotonic() - started:.1f}s', flush=True)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--compiler', type=Path, default=Path(os.environ.get('CC', 'gcc')))
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--optimization', choices=['0', '1', '2'], default='0')
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    raise SystemExit(compile_all(args.source, args.output, args.compiler, args.jobs, '-O' + args.optimization))
