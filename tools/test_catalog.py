#!/usr/bin/env python3
"""Isolated bakes exercise real catalog packaging and public presentation.

    python3 -m unittest discover -s tools -p 'test_catalog*.py'
"""
import hashlib
import json
import os
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import catalog
import catalog_guard
from PIL import Image


def glb(size=1):
    """A tiny, valid fixture mesh; no expensive registry bake or production photo."""
    geometry = struct.pack('<9f', 0, 0, 0, size, 0, 0, 0, size, 0)
    tree = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
            'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}], 'buffers': [{'byteLength': len(geometry)}],
            'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': len(geometry)}],
            'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3', 'min': [0, 0, 0], 'max': [size, size, 0]}]}
    data = json.dumps(tree).encode(); data += b' ' * (-len(data) % 4)
    return struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(data) + 8 + len(geometry)) + struct.pack('<I4s', len(data), b'JSON') + data + struct.pack('<I4s', len(geometry), b'BIN\0') + geometry


class Fixture:
    def __init__(self, root):
        self.root = Path(root); self.lib = self.root / 'library'; self.run = self.root / 'out' / 'fixture'
        self.run.mkdir(parents=True)
        self.bake = self.lib / 'build' / 'artifacts'; self.bake.mkdir(parents=True)
        self.photos = self.lib / 'plates'; self.photos.mkdir()
        # A reserved source photo must not appear in any public object.
        self.secret = b'PRIVATE SOURCE PHOTO'
        self.digest = hashlib.sha256(self.secret).hexdigest()
        (self.photos / 'manifest.json').write_text(json.dumps({'plates': {self.digest: {'original_name': 'reference.jpg', 'kind': 'photo', 'contributed_by': 'Fixture', 'licence': 'CC-BY-4.0'}}}))
        runtime = self.lib / 'ops' / 'runtime'; runtime.mkdir(parents=True)
        (runtime / 'runtime.toml').write_text('assets_licence="CC-BY-4.0"\n')
        edge = self.lib / 'ops' / 'edge'; edge.mkdir()
        (edge / 'README.md').write_text('| intake (`requests`) | `https://requests.<zone>/v1/requests` | `https://edge-requests.<sub>.workers.dev/v1/requests` | `http://127.0.0.1:8787/v1/requests` | POST |\n')
        licences = self.lib / 'docs' / 'press' / 'licences'; licences.mkdir(parents=True)
        for name in catalog.LICENCE_TEXTS: (licences / name).write_text('fixture licence ' + name)
        self.entries = []
        self.add('plant/rowan', 'plant-rowan', taxon='Sorbus aucuparia', use='Woodland canopy')
        self.add('plant/rowan', 'plant-rowan-autumn')
        self.add('rock/basalt', 'rock-basalt', end='impostor')
        self.add('built/vase', 'built-vase', taxon='</script><img src=x onerror=alert(1)>', use='Interior vessel')
        (self.bake / 'manifest.json').write_text(json.dumps({'entries': self.entries}))
        self.asset_source = catalog.ROOT / 'tools' / 'catalog-assets'
        (self.root / 'tools').mkdir()
        (self.root / 'tools' / 'catalog-assets').symlink_to(self.asset_source, target_is_directory=True)
        cfg = {'title': 'Fixture library'}
        cache = self.root / 'out/viewer-cache'; cache.mkdir(parents=True)
        for setting, data in [('model_viewer', b'// isolated fixture: real WebGL tested separately'),
                              ('model_viewer_license', b'Fixture viewer license')]:
            digest = hashlib.sha256(data).hexdigest()
            (cache / digest).write_bytes(data)
            cfg[setting] = 'https://example.com/' + setting
            cfg[setting + '_sha256'] = digest
        (self.root / 'catalog.json').write_text(json.dumps(cfg))

    def add(self, gid, key, end='mesh', taxon='', use=''):
        group, name = gid.split('/')
        folder = self.lib / 'generators' / group; folder.mkdir(parents=True, exist_ok=True)
        ladder = folder / (name + '.ladder.json'); card = folder / (name + '.card.json')
        if not ladder.exists():
            ladder.write_text(json.dumps({'class': 'tree' if group == 'plant' else 'prop', 'extent_m': 2.25, 'mesh_rungs': 1, 'ladder_end': end}))
            card.write_text(json.dumps({'taxon': taxon, 'use': use, 'provenance': [{'plate': self.digest}]}))
        file = key + '.glb'; (self.bake / file).write_bytes(glb())
        self.entries.append({'key': key, 'generator': gid, 'rungs': [{'rung': 0, 'gltf': file, 'triangles': 1}]})
        shot = self.run / gid.replace('/', '_'); shot.mkdir(exist_ok=True)
        Image.new('RGB', (128, 128), '#b1c398').save(shot / 'fixture-closeup.png')

    def build(self, env=None):
        with patch.object(catalog, 'ROOT', self.root), patch.object(catalog, 'LIB', self.lib), patch.object(catalog, 'scorecard_rows', return_value={}), patch.dict(os.environ, env or {}, clear=True):
            catalog.main(['catalog.py', str(self.run)])
        return self.run / 'catalog'


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.fixture = Fixture(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def test_grouped_entries_stable_paths_and_safe_metadata(self):
        site = self.fixture.build(); index = (site / 'index.html').read_text()
        self.assertEqual(catalog_guard.count(index), 4)
        self.assertEqual(index.count('<article class="card"'), 3)
        self.assertTrue((site / 'subject/plant/rowan/autumn/index.html').exists())
        self.assertIn('other build(s)', index)
        self.assertNotIn('</script><img src=x', index)
        self.assertIn('\\u003c/script', index)
        detail = (site / 'subject/built/vase/index.html').read_text()
        self.assertIn('&lt;/script&gt;', detail)
        self.assertIn('target display profile, not texture resolution', detail)
        self.assertIn('compatibility has not been verified', detail)
        self.assertNotIn('Demo receipt', index)

    def test_zip_contents_and_impostor_guard(self):
        site = self.fixture.build()
        zips = list((site / 'objects').glob('*.zip'))
        self.assertEqual(len(zips), 3)
        for path in zips:
            with zipfile.ZipFile(path) as archive:
                self.assertIn('ATTRIBUTION.txt', archive.namelist())
                for licence in catalog.LICENCE_TEXTS: self.assertIn(licence, archive.namelist())
                for name in archive.namelist(): self.assertNotEqual(archive.read(name), self.fixture.secret)
        basalt = (site / 'subject/rock/basalt/index.html').read_text()
        self.assertIn('lacks an impostor atlas', basalt)
        self.assertNotIn('Download free 1080 build', basalt)
        for path in (site / 'objects').iterdir(): self.assertNotEqual(hashlib.sha256(path.read_bytes()).hexdigest(), self.fixture.digest)

    def test_missing_mesh_or_licence_never_offered(self):
        ladder = self.fixture.lib / 'generators/plant/rowan.ladder.json'
        data = json.loads(ladder.read_text()); data['mesh_rungs'] = 2; ladder.write_text(json.dumps(data))
        site = self.fixture.build()
        self.assertIn('rung 1: absent from this bake', (site / 'subject/plant/rowan/index.html').read_text())
        (self.fixture.lib / 'docs/press/licences/LICENSE-RUNTIME.md').unlink()
        site = self.fixture.build()
        self.assertFalse(list((site / 'objects').glob('*.zip')))

    def test_reserved_mesh_is_refused(self):
        (self.fixture.bake / 'built-vase.glb').write_bytes(self.fixture.secret)
        with self.assertRaisesRegex(SystemExit, "plate's bytes"):
            self.fixture.build()

    def test_pages_file_limit_refuses_large_objects(self):
        with self.assertRaisesRegex(SystemExit, 'Pages file limit'):
            self.fixture.build({'PAGES_MAX_FILE_BYTES': '100'})

    def test_intake_configuration_and_contract(self):
        for env in ({}, {'CATALOG_INTAKE_URL': 'https://edge-requests.<sub>.workers.dev/v1/requests', 'TURNSTILE_SITEKEY': 'production-key'},
                    {'CATALOG_INTAKE_URL': 'http://localhost:8787/v1/requests', 'TURNSTILE_SITEKEY': 'production-key'},
                    {'EDGE_ZONE': 'example.com', 'TURNSTILE_SITEKEY': '1x00000000000000000000AA'}):
            site = self.fixture.build(env); index = (site / 'index.html').read_text()
            self.assertIn('data-ready="false"', index)
            self.assertNotIn('action="https://edge-requests.', index)
        site = self.fixture.build({'EDGE_ZONE': 'example.com', 'TURNSTILE_SITEKEY': 'production-key'})
        index = (site / 'index.html').read_text()
        self.assertIn('action="https://requests.example.com/v1/requests"', index)
        self.assertIn('data-ready="true"', index)
        self.assertIn('name="contact" required maxlength="200"', index)
        self.assertIn('name="contributed_by" maxlength="80"', index)
        self.assertIn('name="consent" value="yes"', index)
        self.assertNotIn('required checked', index)
        site = self.fixture.build({'CATALOG_INTAKE_URL': 'https://intake.example.com/v1/requests', 'EDGE_ZONE': 'other.example', 'TURNSTILE_SITEKEY': 'production-key'})
        self.assertEqual(json.loads((site / 'objects.json').read_text())['edge']['intake'], 'https://intake.example.com/v1/requests')

    def test_old_and_new_guard_count_the_same_unit(self):
        self.assertEqual(catalog_guard.count('<div class=card>' * 4), 4)
        self.assertEqual(catalog_guard.count('<a data-catalog-entry="a"></a><a data-catalog-entry="a"></a><a data-catalog-entry="b"></a>'), 2)

    def test_unbaked_library_subjects_and_variants_remain_discoverable(self):
        card = self.fixture.lib / 'generators/plant/fern.card.json'
        card.write_text(json.dumps({'id': 'plant/fern', 'taxon': 'Dryopteris',
                                    'package_targets': [{'id': 'plant/fern', 'tag': 'small'}]}))
        site = self.fixture.build()
        index = (site / 'index.html').read_text()
        self.assertEqual(catalog_guard.count(index), 6)
        self.assertEqual(catalog_guard.downloads(index), 3)
        self.assertIn('Dryopteris', index)
        for variant in ('', 'small/'):
            detail = (site / ('subject/plant/fern/' + variant) / 'index.html').read_text()
            self.assertIn('The downloadable build is not ready yet', detail)
            self.assertNotIn('Download free 1080 build', detail)
            self.assertNotIn('data-model-src', detail)

    def test_detail_levels_link_to_real_baked_objects(self):
        entry = self.fixture.entries[0]
        entry['rungs'].append({'rung': 1, 'gltf': entry['rungs'][0]['gltf'], 'triangles': 1})
        (self.fixture.bake / 'manifest.json').write_text(json.dumps({'entries': self.fixture.entries}))
        site = self.fixture.build()
        detail = (site / 'subject/plant/rowan/index.html').read_text()
        self.assertEqual(detail.count('data-model-src='), 2)
        self.assertIn('Level 1', detail)
        self.assertIn('Each level shows its actual baked model', detail)

    def test_download_guard_counts_legacy_and_grouped_downloads(self):
        self.assertEqual(catalog_guard.downloads("<a href='objects/a.zip' download='a.zip'>Free</a>"), 1)
        self.assertEqual(catalog_guard.downloads('<a data-catalog-entry="a" data-downloadable="true"></a>'
                                               '<a data-catalog-entry="b" data-downloadable="false"></a>'), 1)

    def test_viewer_is_self_hosted_and_requires_verified_bytes(self):
        site = self.fixture.build()
        detail = (site / 'subject/plant/rowan/index.html').read_text()
        self.assertIn('src="../../../model-viewer.min.js"', detail)
        self.assertNotIn('src="https://', detail)
        self.assertTrue((site / 'model-viewer-LICENSE.txt').is_file())
        cfg = json.loads((self.fixture.root / 'catalog.json').read_text())
        (self.fixture.root / 'out/viewer-cache' / cfg['model_viewer_sha256']).write_bytes(b'corrupt')
        import io
        with patch.object(catalog.urllib.request, 'urlopen', return_value=io.BytesIO(b'wrong download')):
            with self.assertRaisesRegex(SystemExit, 'viewer integrity check failed'):
                self.fixture.build()


if __name__ == '__main__': unittest.main()
