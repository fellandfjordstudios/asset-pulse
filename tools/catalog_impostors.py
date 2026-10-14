#!/usr/bin/env python3
"""Complete terminal impostors without rebaking meshes or relaxing ladder checks."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def local_file(folder, name):
    if not isinstance(name, str) or not name or Path(name).name != name or name in ('.', '..'):
        raise ValueError('artifact must be a local filename')
    return folder / name


def expected_end(entry, library):
    """Only repair an end after every committed mesh rung already exists."""
    gid = entry['generator']
    parts = gid.split('/')
    if len(parts) != 2 or any(p in ('', '.', '..') for p in parts):
        raise ValueError('invalid generator id')
    ladder = library / 'generators' / parts[0] / (parts[1].replace('-', '_') + '.ladder.json')
    if not ladder.exists():
        return None  # No declaration means no basis for inventing an end.
    declared = json.loads(ladder.read_text())
    if declared.get('ladder_end') != 'impostor':
        return None
    count = int(declared['mesh_rungs'])
    rows = entry.get('rungs', [])
    if count < 1 or any(r.get('impostor') for r in rows):
        return None
    if {int(r['rung']) for r in rows} != set(range(count)):
        return None
    artifacts = library / 'build/artifacts'
    if any(not local_file(artifacts, r.get('gltf')).is_file() for r in rows):
        return None
    if not local_file(artifacts, entry['key'] + '-impostor.png').is_file():
        return None
    return count


def accept_row(entry, row, expected, artifacts, staged):
    if int(row['rung']) != expected or not row.get('impostor'):
        raise ValueError('library end disagrees with committed ladder')
    atlas = row.get('atlas_file')
    if atlas != entry['key'] + '-impostor.png' or not local_file(artifacts, atlas).is_file():
        raise ValueError('missing or mismatched atlas')
    claimed = {r.get(k) for r in entry['rungs'] for k in ('gltf', 'scene')}
    for field, suffix in (('gltf', '.glb'), ('scene', '.scn')):
        name = row[field]
        if name != f"{entry['key']}-r{expected}{suffix}" or name in claimed:
            raise ValueError('refusing to replace an existing mesh')
        source = local_file(staged, name)
        if not source.is_file() or not source.stat().st_size:
            raise ValueError('missing exported artifact')
        if field == 'gltf':
            data = source.read_bytes()
            if data[:8] != b'glTF\x02\x00\x00\x00' or int.from_bytes(data[8:12], 'little') != len(data):
                raise ValueError('invalid GLB')
            size = int.from_bytes(data[12:16], 'little')
            if data[16:20] != b'JSON' or 20 + size > len(data) or not json.loads(data[20:20 + size]).get('meshes'):
                raise ValueError('GLB has no valid mesh document')
    for field in ('gltf', 'scene'):
        destination = local_file(artifacts, row[field])
        temporary = destination.with_suffix(destination.suffix + '.tmp')
        shutil.copyfile(local_file(staged, row[field]), temporary)
        os.replace(temporary, destination)
    entry['rungs'].append(row)


def repair(library, explorer, godot='godot', timeout=300):
    artifacts = library / 'build/artifacts'
    path = artifacts / 'manifest.json'
    manifest = json.loads(path.read_text())
    results = []
    logs = library / 'build/impostor-repair'
    logs.mkdir(parents=True, exist_ok=True)
    for entry in manifest['entries']:
        expected = expected_end(entry, library)
        if expected is None:
            continue
        stem = entry['key']
        try:
            row_path = local_file(logs, stem + '.json')
            row_path.unlink(missing_ok=True)  # Never accept a stale successful row.
            with local_file(logs, stem + '.log').open('w') as log:
                subprocess.run([godot, '--headless', '--path', str(library), '--script',
                                str(ROOT / 'tools/catalog_impostor.gd'), '--', stem, str(explorer)],
                               stdout=log, stderr=subprocess.STDOUT, check=True, timeout=timeout)
            row = json.loads(row_path.read_text())
            accept_row(entry, row, expected, artifacts, logs)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(manifest, indent=2))
            os.replace(temporary, path)
            results.append({'key': stem, 'status': 'repaired'})
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            results.append({'key': stem, 'status': 'blocked', 'reason': str(error)})
        print('impostor repair:', results[-1])
    (logs / 'report.json').write_text(json.dumps(results, indent=2))
    return results


def verify_pin(folder, lock):
    expected = next(line.split('=', 1)[1] for line in lock.read_text().splitlines() if line.startswith('commit='))
    actual = subprocess.check_output(['git', '-C', str(folder), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != expected:
        raise ValueError(f'{folder.name} does not match {lock.name}; refusing stale artifacts')
    if subprocess.check_output(['git', '-C', str(folder), 'status', '--porcelain'], text=True).strip():
        raise ValueError(f'{folder.name} has source changes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=ROOT / 'library')
    parser.add_argument('--explorer', type=Path, default=ROOT / 'explorer')
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    verify_pin(args.library, ROOT / 'library.lock')
    verify_pin(args.explorer, ROOT / 'explorer.lock')
    repair(args.library.resolve(), args.explorer.resolve(), timeout=args.timeout)
