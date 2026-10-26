#!/usr/bin/env python3
"""Bootstrap boundaries in disposable fixtures; never run a daily job."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'tools').mkdir()
        (self.root / '.githooks').mkdir()
        for path in ['tools/setup.sh', 'tools/check.sh', 'tools/publish.sh', 'daily.sh', '.githooks/pre-push', '.githooks/commit-msg']:
            shutil.copy2(ROOT / path, self.root / path)
        self.home = self.root / 'home'
        self.bin = self.home / '.local/bin'
        self.bin.mkdir(parents=True)
        self.log = self.root / 'calls'
        self.env = dict(os.environ, HOME=str(self.home), PATH=f'{self.bin}:/usr/bin:/bin',
                        CALLS=str(self.log), ENGINE='4.7.2.stable.fixture', HOOK_PATH=str(self.root / '.githooks'),
                        AUTHOR='Fell & Fjord <fellandfjord@gmail.com> 1 +0000', SYNC_EXIT='0')
        self.script(self.bin / 'godot', 'echo "$ENGINE"')
        self.script(self.bin / 'git', 'case "$1" in config) echo "$HOOK_PATH";; var) echo "$AUTHOR";; esac')
        self.script(self.bin / 'python3', 'echo "test $*" >> "$CALLS"')
        self.script(self.bin / 'node', 'echo syntax >> "$CALLS"')
        self.script(self.root / 'tools/sync-library.sh', 'echo "sync $*" >> "$CALLS"; exit "$SYNC_EXIT"')

    def script(self, path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#!/bin/bash\nset -eu\n' + body + '\n')
        path.chmod(0o755)

    def run_script(self, path, data=''):
        return subprocess.run(['bash', path], cwd=self.root, env=self.env, input=data,
                              text=True, capture_output=True)

    def calls(self):
        return self.log.read_text() if self.log.exists() else ''

    def test_wrong_engine_refuses_before_tests(self):
        self.env['ENGINE'] = '4.5.stable.fixture'
        result = self.run_script('tools/check.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Godot 4.7.2 required', result.stderr)
        self.assertEqual(self.calls(), '')

    def test_wrong_author_refuses(self):
        self.env['AUTHOR'] = 'asset-pulse <old@example.test> 1 +0000'
        self.assertNotEqual(self.run_script('tools/check.sh').returncode, 0)
        self.assertEqual(self.calls(), '')

    def test_missing_hook_configuration_refuses(self):
        self.env['HOOK_PATH'] = '/other/hooks'
        self.assertNotEqual(self.run_script('tools/check.sh').returncode, 0)
        self.assertEqual(self.calls(), '')

    def test_dirty_or_wrong_library_refuses(self):
        self.env['SYNC_EXIT'] = '1'
        self.assertNotEqual(self.run_script('tools/check.sh').returncode, 0)
        self.assertEqual(self.calls(), 'sync --verify\n')

    def test_valid_check_runs_existing_isolated_suites(self):
        result = self.run_script('tools/check.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('test_catalog.py', self.calls())
        self.assertIn('test_setup.py', self.calls())
        self.assertNotIn('--bump', self.calls())

    def test_push_preserves_input_and_refuses_before_checks(self):
        self.script(self.home / '.config/fellandfjord/hooks/pre-push',
                    'cat > "$CALLS"; exit 7')
        self.script(self.root / 'tools/check.sh', 'echo local-check >> "$CALLS"')
        result = self.run_script('.githooks/pre-push', 'refs/heads/main abc refs/heads/main def\n')
        self.assertEqual(result.returncode, 7)
        self.assertEqual(self.calls(), 'refs/heads/main abc refs/heads/main def\n')

    def test_push_runs_checks_after_shared_hook(self):
        self.script(self.home / '.config/fellandfjord/hooks/pre-push', 'cat > /dev/null; echo shared >> "$CALLS"')
        self.script(self.root / 'tools/check.sh', 'echo local-check >> "$CALLS"')
        self.assertEqual(self.run_script('.githooks/pre-push').returncode, 0)
        self.assertEqual(self.calls(), 'shared\nlocal-check\n')

    def test_missing_shared_hook_fails_closed(self):
        self.assertNotEqual(self.run_script('.githooks/pre-push').returncode, 0)
        self.assertEqual(self.calls(), '')


if __name__ == '__main__':
    unittest.main()
