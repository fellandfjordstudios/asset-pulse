import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import catalog_impostors as repair


class ImpostorRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lib = Path(self.tmp.name)
        self.artifacts = self.lib / 'build/artifacts'
        self.artifacts.mkdir(parents=True)
        self.staged = self.lib / 'build/impostor-repair'
        self.staged.mkdir()
        self.ladder = self.lib / 'generators/plant/fern.ladder.json'
        self.ladder.parent.mkdir(parents=True)
        self.ladder.write_text(json.dumps({'mesh_rungs': 2, 'ladder_end': 'impostor'}))
        self.entry = {'key': 'plant-fern', 'generator': 'plant/fern', 'rungs': [
            {'rung': n, 'gltf': f'plant-fern-r{n}.glb'} for n in range(2)]}
        for row in self.entry['rungs']:
            (self.artifacts / row['gltf']).write_bytes(b'existing mesh bytes')
        (self.artifacts / 'plant-fern-impostor.png').write_bytes(b'existing atlas')
        self.row = {'rung': 2, 'gltf': 'plant-fern-r2.glb', 'scene': 'plant-fern-r2.scn',
                    'impostor': {'tiles': 36}, 'atlas_file': 'plant-fern-impostor.png'}
        payload = b'{"meshes":[{}]}'
        payload += b' ' * (-len(payload) % 4)
        glb = b'glTF' + (2).to_bytes(4, 'little') + (20 + len(payload)).to_bytes(4, 'little')
        glb += len(payload).to_bytes(4, 'little') + b'JSON' + payload
        (self.staged / self.row['gltf']).write_bytes(glb)
        (self.staged / self.row['scene']).write_bytes(b'scene verified by library')

    def test_complete_meshes_get_one_terminal_row_without_changing_meshes(self):
        before = {p.name: p.read_bytes() for p in self.artifacts.iterdir()}
        self.assertEqual(repair.expected_end(self.entry, self.lib), 2)
        repair.accept_row(self.entry, self.row, 2, self.artifacts, self.staged)
        self.assertEqual(len(self.entry['rungs']), 3)
        self.assertIsNone(repair.expected_end(self.entry, self.lib))
        for name, content in before.items():
            self.assertEqual((self.artifacts / name).read_bytes(), content)

    def test_missing_mesh_cannot_be_replaced_with_an_impostor(self):
        self.entry['rungs'].pop()
        self.assertIsNone(repair.expected_end(self.entry, self.lib))

    def test_missing_mesh_file_blocks_repair(self):
        (self.artifacts / 'plant-fern-r0.glb').unlink()
        self.assertIsNone(repair.expected_end(self.entry, self.lib))

    def test_missing_atlas_or_declaration_blocks_repair(self):
        (self.artifacts / 'plant-fern-impostor.png').unlink()
        self.assertIsNone(repair.expected_end(self.entry, self.lib))
        self.ladder.unlink()
        self.assertIsNone(repair.expected_end(self.entry, self.lib))

    def test_conflicting_end_and_foreign_atlas_are_rejected(self):
        for bad in ({**self.row, 'rung': 1}, {**self.row, 'atlas_file': 'other.png'},
                    {**self.row, 'gltf': '../elsewhere.glb'}):
            with self.assertRaises(ValueError):
                repair.accept_row(self.entry, bad, 2, self.artifacts, self.staged)
        self.assertEqual(len(self.entry['rungs']), 2)

    def test_truncated_export_is_rejected(self):
        (self.staged / self.row['gltf']).write_bytes(b'glTF')
        with self.assertRaises(ValueError):
            repair.accept_row(self.entry, self.row, 2, self.artifacts, self.staged)
        self.assertFalse((self.artifacts / self.row['scene']).exists())

    def test_stale_success_is_not_reused_after_export_failure(self):
        manifest = self.artifacts / 'manifest.json'
        before = json.dumps({'entries': [self.entry]})
        manifest.write_text(before)
        (self.staged / 'plant-fern.json').write_text(json.dumps(self.row))
        with patch.object(repair.subprocess, 'run', side_effect=OSError('export failed')):
            result = repair.repair(self.lib, self.lib)
        self.assertEqual(result[0]['status'], 'blocked')
        self.assertFalse((self.staged / 'plant-fern.json').exists())
        self.assertEqual(manifest.read_text(), before)


if __name__ == '__main__':
    unittest.main()
