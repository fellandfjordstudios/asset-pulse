'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const storageKey = 'asset-pulse:catalog:' + new URL('index.html', document.baseURI).pathname;
  const readState = () => { try { return JSON.parse(sessionStorage.getItem(storageKey) || '{}'); } catch { return {}; } };
  const writeState = state => { try { sessionStorage.setItem(storageKey, JSON.stringify(state)); } catch { /* URL retains filters when storage is unavailable. */ } };
  if (document.body.dataset.view === 'detail') {
    // Each detail may have several path segments. Use its own stable back link
    // as the base so Pages project paths are preserved.
    const back = document.querySelector('[data-return-catalog]');
    if (back) {
      const base = new URL(back.href);
      const key = 'asset-pulse:catalog:' + base.pathname;
      let state = {};
      try { state = JSON.parse(sessionStorage.getItem(key) || '{}'); } catch {}
      const params = new URLSearchParams(location.search);
      const catalogQuery = params.get('catalog') || state.query || '';
      document.querySelectorAll('[data-return-catalog]').forEach(link => {
        const target = new URL(link.href);
        target.search = catalogQuery;
        link.href = target.href;
      });
      // Preserve the catalog context while switching builds.
      document.querySelectorAll('.variantnav a').forEach(link => {
        if (catalogQuery) { const target = new URL(link.href); target.searchParams.set('catalog', catalogQuery); link.href = target.href; }
      });
    }
    document.querySelectorAll('model-viewer').forEach(model => {
      const note = document.querySelector('.loading-note');
      const retry = $('retryPreview');
      const failed = () => {
        if (note) note.textContent = 'The interactive preview could not load. Retry it, open the GLB directly, or use the still renders below. Your browser needs WebGL for the interactive view.';
        if (retry) retry.hidden = false;
      };
      const loaded = () => {
        if (note) note.textContent = 'Drag to rotate. Scroll or pinch to zoom.';
        if (retry) retry.hidden = true;
      };
      model.addEventListener('error', failed);
      model.addEventListener('load', loaded);
      document.querySelector('[data-model-viewer-module]')?.addEventListener('error', failed);
      const timer = setTimeout(() => { if (!model.loaded) failed(); }, 15000);
      model.addEventListener('load', () => clearTimeout(timer));
      if (model.loaded) { clearTimeout(timer); loaded(); }
      if (retry) retry.addEventListener('click', () => location.reload());
    });
    document.querySelectorAll('[data-model-src]').forEach(button => button.addEventListener('click', () => {
      const model = document.querySelector('.detailart model-viewer');
      if (!model) return;
      // setAttribute also preserves the chosen level while the viewer module loads.
      model.setAttribute('src', button.dataset.modelSrc);
      document.querySelector('[data-open-model]')?.setAttribute('href', button.dataset.modelSrc);
      document.querySelectorAll('[data-model-src]').forEach(choice => {
        choice.classList.toggle('active', choice === button);
        choice.setAttribute('aria-pressed', String(choice === button));
      });
      $('modelStatus').textContent = 'Selected ' + button.textContent + '. Drag to rotate when loaded.';
    }));
    return;
  }

  if ($('catalogData')) {
    const assets = JSON.parse($('catalogData').textContent);
    const cards = new Map([...document.querySelectorAll('[data-asset]')].map(card => [card.dataset.asset, card]));
    const params = new URLSearchParams(location.search);
    const saved = readState();
    let category = params.get('category') || '';
    if (!assets.some(asset => asset.category === category)) category = '';
    $('search').value = params.get('q') || '';
    $('sort').value = ['name', 'reverse', 'available'].includes(params.get('sort')) ? params.get('sort') : 'name';
    $('available').checked = params.get('available') === '1';
    $('discovery').hidden = false;
    $('filters').hidden = false;
    const query = () => {
      const p = new URLSearchParams();
      if ($('search').value) p.set('q', $('search').value);
      if (category) p.set('category', category);
      if ($('sort').value !== 'name') p.set('sort', $('sort').value);
      if ($('available').checked) p.set('available', '1');
      return p.toString();
    };
    const save = () => writeState({ query: query(), y: window.scrollY,
      open: [...document.querySelectorAll('.variants[open]')].map(details => details.closest('[data-asset]').dataset.asset) });
    const render = () => {
      const terms = $('search').value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
      const matching = asset => terms.every(term => asset.search.toLocaleLowerCase().includes(term));
      let shown = assets.filter(asset => (!category || asset.category === category) && (!$('available').checked || asset.available) && matching(asset));
      const order = $('sort').value;
      const compare = (a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id);
      shown.sort((a, b) => order === 'reverse' ? compare(b, a) : order === 'available' ? Number(b.available) - Number(a.available) || compare(a, b) : compare(a, b));
      cards.forEach(card => { card.hidden = true; });
      shown.forEach(asset => { const card = cards.get(asset.id); card.hidden = false; $('assetGrid').append(card); });
      $('resultCount').textContent = shown.length + (shown.length === 1 ? ' asset' : ' assets');
      $('empty').hidden = shown.length !== 0;
      document.querySelectorAll('[data-category]').forEach(button => {
        const selected = category === button.dataset.category;
        button.classList.toggle('active', selected);
        button.setAttribute('aria-pressed', String(selected));
      });
      const q = query();
      history.replaceState(null, '', location.pathname + (q ? '?' + q : '') + location.hash);
      // Each stable subject URL carries the filters even without sessionStorage.
      document.querySelectorAll('[data-catalog-entry]').forEach(link => {
        const target = new URL(link.getAttribute('href'), document.baseURI);
        target.search = '';
        if (q) target.searchParams.set('catalog', q);
        link.href = target.href;
      });
    };
    ['search', 'sort', 'available'].forEach(id => $(id).addEventListener(id === 'search' ? 'input' : 'change', () => { render(); save(); }));
    document.querySelectorAll('[data-category]').forEach(button => button.addEventListener('click', () => { category = button.dataset.category; render(); save(); }));
    document.querySelectorAll('[data-clear-filters]').forEach(button => button.addEventListener('click', () => {
      category = ''; $('search').value = ''; $('available').checked = false; $('sort').value = 'name'; render(); save();
    }));
    $('filtersToggle').addEventListener('click', () => {
      const on = $('filters').classList.toggle('show'); $('filtersToggle').setAttribute('aria-expanded', String(on));
    });
    document.addEventListener('click', event => { if (event.target.closest('[data-catalog-entry]')) save(); });
    window.addEventListener('pagehide', save);
    render();
    for (const id of saved.open || []) { const details = cards.get(id)?.querySelector('details'); if (details) details.open = true; }
    if (!location.hash && saved.query === query() && Number.isFinite(saved.y)) {
      requestAnimationFrame(() => window.scrollTo(0, saved.y));
    }
  }

  const form = $('requestForm');
  if (!form) return;
  $('requestFlow').hidden = false;
  const ready = form.dataset.ready === 'true';
  let step = 0, busy = false, receiptId = '', previewUrl = '', token = '', widget = null;
  const fields = {
    text: ['requestText', 'textError'], photo: ['photo', 'photoError'], contact: ['contact', 'contactError'],
    credit: ['credit', 'creditError'], licence: ['licenceGroup', 'licenceError'], ownership: ['ownership', 'ownershipError'], consent: ['consent', 'consentError']
  };
  const fieldError = (key, message) => {
    const [input, error] = fields[key];
    $(error).textContent = message;
    $(input).setAttribute('aria-invalid', String(Boolean(message)));
  };
  const showError = (message, recovery = '') => {
    $('formError').textContent = message + (recovery ? ' ' + recovery : '');
    $('formError').hidden = false;
  };
  const clearErrors = () => { Object.keys(fields).forEach(key => fieldError(key, '')); $('formError').hidden = true; };
  const clean = value => String(value || '').replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim();
  const validate = stage => {
    let first = null;
    const fail = (key, message) => { fieldError(key, message); first ||= fields[key][0]; };
    if (stage === 0) {
      const text = clean($('requestText').value);
      if (!text) fail('text', 'Describe the asset you need.');
      else if (text.length > 2000) fail('text', 'Keep the description within 2,000 characters.');
    }
    if (stage === 1) {
      const file = $('photo').files[0];
      if (!file) fail('photo', 'Choose a reference photo.');
      else if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) fail('photo', 'Choose a JPEG, PNG or WebP image.');
      else if (file.size === 0) fail('photo', 'The file is empty. Choose another photo.');
      else if (file.size > 10 * 1024 * 1024) fail('photo', 'The photo is larger than 10 MiB. Choose a smaller image.');
    }
    if (stage === 2) {
      const contact = clean($('contact').value), credit = clean($('credit').value);
      if (!contact) fail('contact', 'Enter an email address or another contact method.');
      else if (contact.length > 200) fail('contact', 'Keep contact details within 200 characters.');
      if (credit.length > 80 || credit.includes('@')) fail('credit', 'Use a credit name of up to 80 characters, without an email address.');
      if (!form.querySelector('input[name=licence]:checked')) fail('licence', 'Choose a license for the reference photo.');
      if (!$('ownership').checked) fail('ownership', 'Confirm that you took the photo and can grant permission.');
      if (!$('consent').checked) fail('consent', 'Confirm everyone identifiable agreed, and no children appear.');
    }
    return first;
  };
  const review = () => {
    $('review').replaceChildren();
    const values = [['Asset description', $('requestText').value], ['Reference photo', $('photo').files[0]?.name || ''],
      ['Contact (private)', $('contact').value], ['Credit name', $('credit').value || 'Not provided'],
      ['Photo license', form.querySelector('input[name=licence]:checked')?.value || ''], ['Permissions', 'Photo ownership and identifiable-person consent confirmed; no children appear.']];
    for (const [label, value] of values) {
      const row = document.createElement('div'); row.className = 'reviewrow';
      const key = document.createElement('b'); key.textContent = label;
      const text = document.createElement('span'); text.textContent = value;
      row.append(key, text); $('review').append(row);
    }
  };
  const updateSubmit = () => { $('nextStep').disabled = busy || (step === 3 && (!ready || !token)); };
  const challengeFailed = () => {
    token = ''; $('challengeStatus').textContent = 'The bot check could not load. Check your connection or content blocker, then retry the bot check. Your inputs are kept.';
    $('retryChallenge').hidden = false; updateSubmit();
  };
  const mountChallenge = () => {
    if (!ready || widget !== null) return;
    if (!window.turnstile) { $('challengeStatus').textContent = 'Loading the bot check…'; return; }
    try {
      widget = window.turnstile.render($('turnstileWidget'), {
        sitekey: form.dataset.sitekey,
        callback: value => { token = value; $('challengeStatus').textContent = 'Bot check complete.'; $('retryChallenge').hidden = true; updateSubmit(); },
        'expired-callback': () => { token = ''; $('challengeStatus').textContent = 'Bot check expired. Complete it again before sending.'; $('retryChallenge').hidden = false; updateSubmit(); },
        'error-callback': () => { challengeFailed(); return true; }
      });
    } catch { challengeFailed(); }
  };
  const retry = document.createElement('button'); retry.id = 'retryChallenge'; retry.type = 'button'; retry.className = 'btn'; retry.textContent = 'Retry bot check'; retry.hidden = true;
  $('turnstileWidget').after(retry);
  let challengeScript;
  const loadChallenge = () => {
    if (window.turnstile) { mountChallenge(); return; }
    if (challengeScript) challengeScript.remove();
    challengeScript = document.createElement('script');
    challengeScript.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    challengeScript.async = true;
    const loadingTimeout = setTimeout(() => { if (!window.turnstile) challengeFailed(); }, 15000);
    challengeScript.onload = () => { clearTimeout(loadingTimeout); mountChallenge(); };
    challengeScript.onerror = () => { clearTimeout(loadingTimeout); challengeFailed(); };
    document.head.append(challengeScript);
  };
  retry.addEventListener('click', () => {
    if (window.turnstile && widget !== null) { window.turnstile.reset(widget); token = ''; $('challengeStatus').textContent = 'Complete the bot check again.'; updateSubmit(); }
    else loadChallenge();
  });
  const resetChallenge = () => {
    token = ''; updateSubmit();
    if (window.turnstile && widget !== null) {
      try { window.turnstile.reset(widget); } catch { challengeFailed(); }
    }
    if (ready) { $('challengeStatus').textContent = 'Complete the bot check again before retrying.'; retry.hidden = false; }
  };
  const setStep = (next, focus = true) => {
    step = next;
    document.querySelectorAll('[data-stage]').forEach(stage => { stage.hidden = Number(stage.dataset.stage) !== step; });
    document.querySelectorAll('.step').forEach((label, i) => {
      label.classList.toggle('active', i === step);
      if (i === step) label.setAttribute('aria-current', 'step'); else label.removeAttribute('aria-current');
    });
    $('backStep').hidden = step === 0;
    $('nextStep').textContent = step === 3 ? (ready ? 'Send request →' : 'Sending unavailable') : 'Continue →';
    if (step === 3) { review(); if (ready) loadChallenge(); else $('challengeStatus').textContent = 'The request desk is not configured. Nothing can be submitted yet.'; }
    updateSubmit();
    if (focus) {
      const heading = document.querySelector(`[data-stage="${step}"] h2`); heading.tabIndex = -1; heading.focus();
    }
  };
  $('backStep').addEventListener('click', () => { if (!busy) { clearErrors(); setStep(Math.max(0, step - 1)); } });
  $('photo').addEventListener('change', () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = ''; $('photoPreview').hidden = true; $('photoPreview').removeAttribute('src'); $('photoInfo').textContent = '';
    fieldError('photo', '');
    if (validate(1)) return;
    const file = $('photo').files[0];
    previewUrl = URL.createObjectURL(file); $('photoPreview').src = previewUrl; $('photoPreview').hidden = false;
    $('photoInfo').textContent = file.name + ' · ' + (file.size / 1024 / 1024).toFixed(2) + ' MiB';
  });
  const fallback = (body, status) => {
    const messages = {
      'photo-has-gps': ['The photo contains location metadata.', 'Remove location metadata and choose the cleaned photo.'],
      'photo-metadata-unreadable': ['The photo’s metadata could not be checked.', 'Export a new copy without location metadata and choose it again.'],
      'photo-too-large': ['The photo is too large.', 'Choose a JPEG, PNG or WebP up to 10 MiB.'],
      'photo-empty': ['The photo is empty.', 'Choose another photo.'],
      'photo-type-not-allowed': ['This image format is not accepted.', 'Choose a JPEG, PNG or WebP.'],
      'contact-missing': ['Contact details are required.', 'Go back to permissions and enter a way to reach you.'],
      'contributed-by-not-a-name': ['The credit name is not accepted.', 'Use up to 80 characters and put email addresses in the contact field.'],
      'turnstile-failed': ['The bot check was not accepted.', 'Complete a fresh bot check and try again.']
    };
    return messages[body.reason] || (status === 503 ? ['The request desk is temporarily unavailable.', 'Your inputs are kept. Try again later.'] : ['The request could not be accepted.', 'Your inputs are kept. Review them and try again.']);
  };
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (busy) return;
    clearErrors();
    if (step < 3) {
      const invalid = validate(step);
      if (invalid) { ($(invalid).querySelector('input') || $(invalid)).focus(); return; }
      setStep(step + 1); return;
    }
    // Recheck all stages in case browser automation or autofill changed a field.
    for (let i = 0; i < 3; i++) {
      const invalid = validate(i);
      if (invalid) { setStep(i); ($(invalid).querySelector('input') || $(invalid)).focus(); return; }
    }
    if (!ready || !token) { showError('Complete the bot check before sending.'); return; }
    busy = true; updateSubmit(); $('backStep').disabled = true; form.setAttribute('aria-busy', 'true');
    $('submissionStatus').hidden = false; $('submissionStatus').textContent = 'Sending your photo and request. Keep this page open…';
    const data = new FormData(form); data.set('cf-turnstile-response', token);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    try {
      const response = await fetch(form.action, { method: 'POST', body: data, signal: controller.signal, credentials: 'omit' });
      let body = {};
      try { body = await response.json(); } catch { /* Explain malformed responses without displaying raw server content. */ }
      if (response.status === 201 && typeof body.id === 'string' && body.id.trim()) {
        receiptId = body.id;
        $('receiptId').textContent = receiptId; $('requestFlow').hidden = true; $('receipt').hidden = false;
        document.querySelectorAll('.step').forEach((label, i) => { label.classList.toggle('active', i === 4); });
        $('receiptTitle').focus();
        // Clear private form data after success; retain only the real receipt in
        // this document. Never persist contact, description or photo to storage.
        form.reset(); if (previewUrl) URL.revokeObjectURL(previewUrl); previewUrl = '';
        $('photoPreview').removeAttribute('src'); $('photoPreview').hidden = true; $('photoInfo').textContent = ''; $('review').replaceChildren();
      } else if (response.ok) {
        showError('The desk replied without a request ID, so receipt cannot be confirmed.', 'Keep your inputs. Retrying may create a duplicate if the first request reached the queue.');
        resetChallenge();
      } else {
        const [say, recovery] = fallback(body, response.status);
        showError(typeof body.say === 'string' && body.say ? body.say : say, typeof body.recovery === 'string' && body.recovery ? body.recovery : recovery);
        resetChallenge();
      }
    } catch (error) {
      showError(error.name === 'AbortError' ? 'The request took too long to confirm.' : 'The connection failed before a receipt could be confirmed.',
        'Your inputs are kept. Check your connection and complete a fresh bot check before retrying. If the request reached the queue, retrying may create a duplicate.');
      resetChallenge();
    } finally {
      clearTimeout(timeout); busy = false; form.removeAttribute('aria-busy'); $('backStep').disabled = false;
      $('submissionStatus').hidden = true; updateSubmit();
    }
  });
  $('copyReceipt').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(receiptId); $('copyStatus').textContent = 'Request ID copied.'; }
    catch { $('copyStatus').textContent = 'Select and copy the request ID shown above.'; }
  });
  $('newRequest').addEventListener('click', () => {
    receiptId = ''; $('receiptId').textContent = ''; $('copyStatus').textContent = ''; $('receipt').hidden = true; $('requestFlow').hidden = false;
    clearErrors(); resetChallenge(); setStep(0);
  });
  setStep(0, false);
})();
