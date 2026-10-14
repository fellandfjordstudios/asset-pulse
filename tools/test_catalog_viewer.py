#!/usr/bin/env python3
"""Exercise the actual bundled renderer and ZIP downloads without runtime CDNs.

The build fetches checksum-pinned viewer bytes; the browser may access only the
local test server. Run with CATALOG_BROWSER=webkit for Safari's browser engine.
"""
import functools
import http.server
import json
import os
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from test_catalog import Fixture, catalog


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class ViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.fixture = Fixture(cls.temp.name)
        cfg = json.loads((Path(__file__).resolve().parent.parent / 'catalog.json').read_text())
        (cls.fixture.root / 'catalog.json').write_text(json.dumps(cfg))
        # Keep the runtime's network/proxy configuration for dependency fetches;
        # Fixture.build deliberately clears product configuration variables.
        with patch.object(catalog, 'ROOT', cls.fixture.root):
            catalog.viewer_module(cfg, cls.fixture.run)
        cls.site = cls.fixture.build()
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(cls.site)))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}/'
        cls.playwright = sync_playwright().start()
        browser = os.environ.get('CATALOG_BROWSER', 'chromium')
        options = {'args': ['--enable-unsafe-swiftshader']} if browser == 'chromium' else {}
        cls.browser = getattr(cls.playwright, browser).launch(**options)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.temp.cleanup()

    def test_renderer_rotates_and_downloads_with_no_external_browser_requests(self):
        for mobile in (False, True):
            with self.subTest(mobile=mobile):
                options = self.playwright.devices['iPhone 13'] if mobile else {'viewport': {'width': 1280, 'height': 900}}
                context = self.browser.new_context(**options)
                page = context.new_page()
                external = []
                def route(request):
                    if request.request.url.startswith(self.base):
                        request.continue_()
                    else:
                        external.append(request.request.url)
                        request.abort()
                page.route('**/*', route)
                page.goto(self.base + 'subject/plant/rowan/')
                page.wait_for_function('document.querySelector("model-viewer").loaded === true && document.querySelector("model-viewer").modelIsVisible === true', timeout=30000)
                model = page.locator('model-viewer')
                before = model.evaluate('(el) => el.getCameraOrbit().theta')
                box = model.bounding_box()
                page.mouse.move(box['x'] + box['width'] * .4, box['y'] + box['height'] * .4)
                page.mouse.down()
                page.mouse.move(box['x'] + box['width'] * .7, box['y'] + box['height'] * .5, steps=10)
                page.mouse.up()
                page.wait_for_function('(before) => Math.abs(document.querySelector("model-viewer").getCameraOrbit().theta - before) > .01', arg=before)
                with page.expect_download() as pending:
                    page.get_by_role('link', name='Download free 1080 build').click()
                download = pending.value
                self.assertIsNone(download.failure())
                with zipfile.ZipFile(download.path()) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertIn('ATTRIBUTION.txt', archive.namelist())
                    self.assertIn('plant-rowan/rung0.glb', archive.namelist())
                self.assertEqual(external, [])
                context.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
