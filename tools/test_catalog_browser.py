#!/usr/bin/env python3
"""Browser regressions with local fixtures and intercepted intake/Turnstile.

No requests or photos are submitted to a production service.
Run: python3 tools/test_catalog_browser.py
Requires Pillow, Playwright, and `python3 -m playwright install chromium`.
"""
import functools
import http.server
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright
from test_catalog import Fixture

TURNSTILE = '''window.turnstile = {
 render(el, options) { window.challengeOptions = options; setTimeout(() => options.callback('fixture-token'), 10); return 'fixture-widget'; },
 reset(id) { setTimeout(() => window.challengeOptions.callback('fresh-fixture-token'), 10); }
};'''


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args): pass


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.fixture = Fixture(cls.temp.name)
        # Different bytes and URLs prove the level switch loads another model.
        entry = cls.fixture.entries[0]
        from test_catalog import glb
        (cls.fixture.bake / 'rowan-level1.glb').write_bytes(glb(0.5))
        entry['rungs'].append({'rung': 1, 'gltf': 'rowan-level1.glb', 'triangles': 1})
        (cls.fixture.bake / 'manifest.json').write_text(json.dumps({'entries': cls.fixture.entries}))
        cls.site = cls.fixture.build({'CATALOG_INTAKE_URL': 'https://intake.example.com/v1/requests', 'TURNSTILE_SITEKEY': 'production-fixture-key'})
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(cls.site)))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/index.html'
        cls.playwright = sync_playwright().start(); cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.playwright.stop(); cls.server.shutdown(); cls.server.server_close(); cls.temp.cleanup()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 800})
        self.page = self.context.new_page(); self.page.set_default_timeout(5000); self.errors = []; self.calls = []; self.response = (422, {'say': 'Fixture refusal <img src=x>', 'recovery': 'Choose a cleaned photo.'})
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        def route(request):
            url = request.request.url
            if url.startswith(self.url.rsplit('/', 1)[0]): request.continue_()
            elif 'challenges.cloudflare.com/turnstile' in url: request.fulfill(status=200, content_type='application/javascript', body=TURNSTILE)
            elif url == 'https://intake.example.com/v1/requests':
                if request.request.method == 'OPTIONS':
                    request.fulfill(status=204, headers={'access-control-allow-origin': '*', 'access-control-allow-methods': 'POST', 'access-control-allow-headers': 'content-type'})
                    return
                self.calls.append(request.request.post_data_buffer)
                status, body = self.response
                if status == -1: request.abort('failed')
                else: request.fulfill(status=status, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(body))
            else: request.abort()  # No other external services in regression tests.
        self.page.route('**/*', route)
        self.page.goto(self.url)

    def tearDown(self):
        self.assertEqual(self.errors, []); self.context.close()

    def shown(self): return self.page.locator('[data-asset]:visible').count()
    def advance(self): self.page.locator('#nextStep').click()

    def test_catalog_opens_with_all_assets_and_optional_download_filter(self):
        self.assertFalse(self.page.locator('#available').is_checked())
        self.assertEqual(self.shown(), 3)
        self.page.locator('#available').check()
        self.assertEqual(self.shown(), 2)
        self.assertIn('available=1', self.page.url)
        self.page.reload()
        self.assertEqual(self.shown(), 2)
        self.page.locator('[data-clear-filters]').first.click()
        self.assertFalse(self.page.locator('#available').is_checked())
        self.assertEqual(self.shown(), 3)

    def fill_request(self, wait_for_bot=True):
        self.page.locator('#requestText').fill('<script>window.injected=true</script> A coastal prop')
        self.advance()
        self.page.locator('#photo').set_input_files({'name': 'reference.png', 'mimeType': 'image/png', 'buffer': b'\x89PNG\r\n\x1a\nfixture-only'})
        self.advance(); self.page.locator('#contact').fill('person@example.com'); self.page.locator('#credit').fill('Fixture Author')
        self.page.locator('[name=licence][value="CC-BY-4.0"]').check(); self.page.locator('#ownership').check(); self.page.locator('#consent').check(); self.advance()
        if wait_for_bot: self.page.wait_for_function("!document.getElementById('nextStep').disabled")

    def test_discovery_sorting_variants_and_return_state(self):
        self.assertEqual(self.shown(), 3)
        self.page.locator('#search').fill('sorbus woodland'); self.assertEqual(self.shown(), 1)
        self.page.locator('#search').fill('autumn'); self.assertEqual(self.shown(), 1)
        self.page.locator('.variants summary').click(); self.page.locator('.variants a').click()
        self.assertIn('/subject/plant/rowan/autumn/', self.page.url)
        self.page.locator('[data-return-catalog]').last.click()
        self.assertEqual(self.page.locator('#search').input_value(), 'autumn'); self.assertEqual(self.shown(), 1)
        self.assertTrue(self.page.locator('.variants').evaluate('(el) => el.open'))
        self.page.locator('[data-clear-filters]').first.click(); self.page.locator('#available').check(); self.assertEqual(self.shown(), 2)
        self.page.locator('[data-category="Rocks"]').click(); self.assertEqual(self.shown(), 0)
        self.assertTrue(self.page.locator('#empty').is_visible())
        self.page.locator('[data-clear-filters]').first.click(); self.page.locator('#sort').select_option('reverse')
        self.assertEqual(self.page.locator('[data-asset]:visible').first.get_attribute('data-asset'), 'built/vase')
        self.page.locator('#search').fill('vessel'); self.assertEqual(self.shown(), 1)

    def test_back_link_and_browser_back_preserve_scroll(self):
        self.page.locator('#sort').select_option('reverse')
        self.page.evaluate('window.scrollTo(0, 500)')
        self.page.locator('[data-catalog-entry="built-vase"]').click()
        self.page.locator('[data-return-catalog]').last.click()
        self.page.wait_for_function('window.scrollY > 300')
        self.assertEqual(self.page.locator('#sort').input_value(), 'reverse')
        self.page.locator('[data-catalog-entry="built-vase"]').click(); self.page.go_back()
        self.assertEqual(self.page.locator('#sort').input_value(), 'reverse')
        self.page.wait_for_function('window.scrollY > 300')

    def test_detail_level_controls_select_baked_models(self):
        self.page.locator('[data-catalog-entry="plant-rowan"]').click()
        buttons = self.page.locator('[data-model-src]')
        self.assertEqual(buttons.count(), 2)
        target = buttons.nth(1).get_attribute('data-model-src')
        self.assertNotEqual(target, buttons.nth(0).get_attribute('data-model-src'))
        buttons.nth(1).click()
        self.assertEqual(self.page.locator('model-viewer').get_attribute('src'), target)
        self.assertEqual(buttons.nth(1).get_attribute('aria-pressed'), 'true')
        self.assertEqual(buttons.nth(0).get_attribute('aria-pressed'), 'false')
        self.assertIn('Level 1', self.page.locator('#modelStatus').inner_text())
        self.assertEqual(self.page.locator('[data-open-model]').get_attribute('href'), target)

    def test_download_click_returns_a_complete_zip_and_has_direct_fallback(self):
        self.page.locator('[data-catalog-entry="plant-rowan"]').click()
        link = self.page.get_by_role('link', name='Download free 1080 build')
        with self.page.expect_download() as pending:
            link.click()
        download = pending.value
        self.assertIsNone(download.failure())
        with zipfile.ZipFile(download.path()) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn('ATTRIBUTION.txt', archive.namelist())
            self.assertIn('plant-rowan/rung0.glb', archive.namelist())
        fallback = self.page.locator('[data-open-package]')
        self.assertEqual(fallback.get_attribute('href'), link.get_attribute('href'))
        self.assertEqual(fallback.get_attribute('target'), '_blank')
        self.assertIsNone(fallback.get_attribute('download'))

    def test_viewer_failure_is_actionable_and_a_late_load_recovers(self):
        self.page.locator('[data-catalog-entry="plant-rowan"]').click()
        self.page.locator('model-viewer').dispatch_event('error')
        self.assertTrue(self.page.locator('#retryPreview').is_visible())
        self.assertIn('could not load', self.page.locator('.loading-note').inner_text())
        self.assertTrue(self.page.locator('[data-open-model]').is_visible())
        self.page.locator('model-viewer').dispatch_event('load')
        self.assertFalse(self.page.locator('#retryPreview').is_visible())
        self.assertIn('Drag to rotate', self.page.locator('.loading-note').inner_text())

    def test_missing_viewer_module_does_not_leave_an_endless_loading_message(self):
        self.page.route('**/model-viewer.min.js', lambda route: route.abort())
        self.page.clock.install()
        self.page.locator('[data-catalog-entry="plant-rowan"]').click()
        self.page.clock.fast_forward(16000)
        self.assertTrue(self.page.locator('#retryPreview').is_visible())
        self.assertIn('could not load', self.page.locator('.loading-note').inner_text())
        self.assertTrue(self.page.get_by_role('link', name='Download free 1080 build').is_visible())
        self.assertTrue(self.page.locator('model-viewer img[slot="poster"]').is_visible())

    def test_validation_preview_and_safe_review(self):
        self.advance(); self.assertIn('Describe', self.page.locator('#textError').inner_text())
        self.page.locator('#requestText').fill('A useful prop'); self.advance(); self.advance()
        self.assertIn('Choose', self.page.locator('#photoError').inner_text())
        self.page.locator('#photo').set_input_files({'name': 'bad.gif', 'mimeType': 'image/gif', 'buffer': b'GIF89a'})
        self.assertIn('JPEG', self.page.locator('#photoError').inner_text())
        large = Path(self.temp.name) / 'large.png'
        large.write_bytes(b'x' * (10 * 1024 * 1024 + 1))
        self.page.locator('#photo').set_input_files(str(large), timeout=15000)
        self.assertIn('10 MiB', self.page.locator('#photoError').inner_text())
        self.page.locator('#photo').set_input_files({'name': 'empty.png', 'mimeType': 'image/png', 'buffer': b''})
        self.assertIn('empty', self.page.locator('#photoError').inner_text())
        self.page.locator('#photo').set_input_files({'name': 'valid.png', 'mimeType': 'image/png', 'buffer': b'\x89PNG\r\n\x1a\nfixture'})
        self.assertTrue(self.page.locator('#photoPreview').get_attribute('src').startswith('blob:'))
        self.assertEqual(self.calls, []); self.advance(); self.advance()
        self.assertIn('contact', self.page.locator('#contactError').inner_text())
        self.assertIn('license', self.page.locator('#licenceError').inner_text())
        self.assertIn('children', self.page.locator('#consentError').inner_text())
        self.page.locator('#contact').fill('person@example.com'); self.page.locator('#credit').fill('wrong@example.com'); self.advance()
        self.assertIn('credit name', self.page.locator('#creditError').inner_text())
        self.page.locator('#credit').fill('Name'); self.page.locator('[name=licence]').first.check(); self.page.locator('#ownership').check(); self.page.locator('#consent').check(); self.advance()
        self.assertIn('person@example.com', self.page.locator('#review').inner_text())

    def test_failure_recovery_multipart_progress_and_real_receipt(self):
        self.fill_request()
        self.assertEqual(self.page.locator('#review script').count(), 0)
        self.assertIsNone(self.page.evaluate('window.injected'))
        self.advance(); self.page.wait_for_function("!document.getElementById('formError').hidden")
        self.assertIn('Fixture refusal <img src=x>', self.page.locator('#formError').inner_text())
        self.assertIn('Choose a cleaned photo', self.page.locator('#formError').inner_text())
        self.assertEqual(self.page.locator('#formError img').count(), 0)
        for field in [b'name="photo"', b'name="text"', b'name="contact"', b'name="consent"', b'name="licence"', b'name="contributed_by"', b'name="cf-turnstile-response"']:
            self.assertIn(field, self.calls[0])
        self.assertIn(b'fixture-token', self.calls[0]); self.assertIn(b'yes', self.calls[0])
        self.page.locator('#backStep').click(); self.assertEqual(self.page.locator('#contact').input_value(), 'person@example.com')
        self.page.locator('#backStep').click(); self.assertEqual(self.page.locator('#photo').evaluate('(el) => el.files.length'), 1)
        self.advance(); self.advance(); self.page.wait_for_function("!document.getElementById('nextStep').disabled")
        self.response = (-1, {})
        self.advance(); self.page.wait_for_function("document.getElementById('formError').textContent.includes('connection failed')")
        self.assertIn('duplicate', self.page.locator('#formError').inner_text())
        self.page.wait_for_function("!document.getElementById('nextStep').disabled")
        self.response = (201, {})
        self.advance(); self.page.wait_for_function("document.getElementById('formError').textContent.includes('without a request ID')")
        self.assertFalse(self.page.locator('#receipt').is_visible())
        self.page.wait_for_function("!document.getElementById('nextStep').disabled")
        self.response = (503, {'reason': 'moderation-not-configured'})
        self.advance(); self.page.wait_for_function("document.getElementById('formError').textContent.includes('temporarily unavailable')")
        self.assertNotIn('moderation-not-configured', self.page.locator('#formError').inner_text())
        self.page.wait_for_function("!document.getElementById('nextStep').disabled")
        self.response = (201, {'id': 'f34f2089-d43f-4c04-858a-f00d18efdfbd'})
        self.advance(); self.page.locator('#receipt').wait_for(state='visible')
        self.assertEqual(self.page.locator('#receiptId').inner_text(), self.response[1]['id'])
        self.assertIn('not production approval', self.page.locator('#receipt').inner_text())
        self.assertEqual(self.page.locator('#contact').input_value(), '')
        self.assertNotIn('person@example.com', self.page.evaluate('JSON.stringify(sessionStorage)'))
        self.page.locator('#newRequest').click(); self.assertTrue(self.page.locator('[data-stage="0"]').is_visible())

    def test_submission_progress_duplicate_prevention_and_bot_expiry(self):
        self.fill_request()
        self.page.evaluate("window.challengeOptions['expired-callback']()")
        self.assertTrue(self.page.locator('#nextStep').is_disabled())
        self.assertIn('expired', self.page.locator('#challengeStatus').inner_text())
        self.page.locator('#retryChallenge').click()
        self.page.wait_for_function("!document.getElementById('nextStep').disabled")
        pending = []
        self.page.route('https://intake.example.com/v1/requests', lambda route: pending.append(route))
        self.advance()
        self.page.wait_for_function("document.getElementById('requestForm').getAttribute('aria-busy') === 'true'")
        self.assertTrue(self.page.locator('#nextStep').is_disabled())
        self.assertTrue(self.page.locator('#backStep').is_disabled())
        self.assertTrue(self.page.locator('#submissionStatus').is_visible())
        self.page.locator('#requestForm').evaluate("form => form.dispatchEvent(new Event('submit', {bubbles:true, cancelable:true}))")
        self.assertEqual(len(pending), 1)
        pending[0].fulfill(status=201, content_type='application/json', headers={'access-control-allow-origin':'*'}, body=json.dumps({'id': 'fixture-progress-id'}))
        self.page.locator('#receipt').wait_for(state='visible')
        self.assertEqual(self.page.locator('#receiptId').inner_text(), 'fixture-progress-id')

    def test_bot_script_failure_can_be_retried(self):
        pattern = 'https://challenges.cloudflare.com/turnstile/**'
        self.page.route(pattern, lambda route: route.abort())
        self.fill_request(wait_for_bot=False)
        self.page.locator('#retryChallenge').wait_for(state='visible')
        self.assertTrue(self.page.locator('#nextStep').is_disabled())
        self.assertIn('could not load', self.page.locator('#challengeStatus').inner_text())
        self.page.unroute(pattern)
        self.page.locator('#retryChallenge').click()
        self.page.wait_for_function("!document.getElementById('nextStep').disabled")
        self.assertEqual(self.page.locator('#contact').input_value(), 'person@example.com')
        self.assertEqual(self.page.locator('#photo').evaluate('(el) => el.files.length'), 1)

    def test_unconfigured_desk_cannot_submit(self):
        try:
            self.fixture.build({})
            self.page.reload()
            self.fill_request(wait_for_bot=False)
            self.assertTrue(self.page.locator('#nextStep').is_disabled())
            self.assertIn('not configured', self.page.locator('#challengeStatus').inner_text())
            self.page.locator('#requestForm').evaluate("form => form.dispatchEvent(new Event('submit', {bubbles:true, cancelable:true}))")
            self.assertEqual(self.calls, [])
        finally:
            self.fixture.build({'CATALOG_INTAKE_URL': 'https://intake.example.com/v1/requests', 'TURNSTILE_SITEKEY': 'production-fixture-key'})

    def test_mobile_layout(self):
        for width in [320, 390, 700, 1024, 1280]:
            self.page.set_viewport_size({'width': width, 'height': 800})
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'overflow at {width}')
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.locator('#filtersToggle').click(); self.assertTrue(self.page.locator('#filters').is_visible())
        self.assertEqual(self.page.locator('#filtersToggle').get_attribute('aria-expanded'), 'true')
        self.fill_request()
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        self.page.screenshot(path='/tmp/asset-pulse-mobile-review.png', full_page=True)


if __name__ == '__main__': unittest.main(verbosity=2)
