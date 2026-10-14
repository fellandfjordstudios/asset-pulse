"""Customer presentation only. Packaging and provenance remain in catalog.py."""
import html
import json
from collections import defaultdict
from urllib.parse import urlsplit


def esc(value):
    return html.escape(str(value), quote=True)


def safe_url(value):
    """Links must be relative files or absolute HTTP(S), never executable URLs."""
    if not value or any(c in value for c in '\\<>\r\n'):
        return ''
    parsed = urlsplit(value)
    if parsed.scheme and parsed.scheme not in ('https', 'http'):
        return ''
    if value.startswith('//'):
        return ''
    return value


def name_of(gid):
    return gid.split('/', 1)[-1].replace('_', ' ').replace('-', ' ').capitalize()


def variant_of(key, gid):
    prefix = gid.replace('/', '-') + '-'
    return key[len(prefix):].replace('_', ' ').replace('-', ' ').capitalize() if key.startswith(prefix) else ''


def category_of(gid):
    group = gid.split('/', 1)[0]
    return {'plant': 'Vegetation', 'rock': 'Rocks', 'stone': 'Rocks',
            'built': 'Props', 'animal': 'Animals', 'alga': 'Algae'}.get(group, name_of(group))


def page(title, body, up='', head='', catalog=False):
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · Asset Pulse</title>
<link rel="stylesheet" href="{up}catalog.css"><script src="{up}catalog.js" defer></script>{head}</head>
<body data-view="{'catalog' if catalog else 'detail'}"><a class="btn skip" href="#main">Skip to content</a>
<header><div class="bar"><a class="brand" href="{up}index.html">Fell &amp; Fjord<small>Assets for the worlds you build.</small></a>
<nav aria-label="Main navigation"><a href="{up}index.html" {'aria-current="page"' if catalog else 'data-return-catalog'}>Catalog</a>
<a href="{up}index.html#request">Request an asset ↗</a></nav></div></header><main id="main">{body}</main>
<footer><span>Fell &amp; Fjord Studios · Asset Pulse</span><span>Generated from the asset-generators library</span></footer></body></html>'''


def preview(entry, rel=lambda u: u, detail=False):
    name = entry['name']
    if entry['shots']:
        name = name_of(entry['gid']) + (' (parent default)' if entry['variant'] else '')
        return f'<img src="{esc(rel(entry["shots"][0]))}" alt="{esc(name)} — library render" loading="lazy">'
    if entry['model']:
        return f'<model-viewer src="{esc(rel(entry["model"]))}" alt="{esc(name)} — baked model" camera-controls {"" if detail else "interaction-prompt=none"} shadow-intensity="1" loading="lazy"><span slot="poster" class="noimg">Load 3D preview</span></model-viewer>'
    return '<div class="noimg">Preview unavailable for this build</div>'


def entry_link(entry):
    return f'<a data-catalog-entry="{esc(entry["key"])}" data-downloadable="{str(bool(entry["download"])).lower()}" href="{esc(entry["path"])}">{esc(entry["variant"] or entry["name"])}</a>'


def index(entries, cfg, rev, request, extra=''):
    groups = defaultdict(list)
    for e in entries:
        groups[e['gid']].append(e)
    cards, data = [], []
    for gid, variants in sorted(groups.items(), key=lambda item: name_of(item[0]).lower()):
        default = next((e for e in variants if not e['variant']), variants[0])
        available = any(e['download'] for e in variants)
        category = category_of(gid)
        words = ' '.join(str(v) for e in variants for v in [e['name'], e['variant'], e['key'], *[v for _, v in e['facts']]])
        data.append({'id': gid, 'category': category, 'name': name_of(gid), 'search': words, 'available': available})
        # Mark every baked entry exactly once: the deployment guard still counts
        # variants even though the customer browses one card per parent asset.
        selected = f'<a class="cardlink" data-catalog-entry="{esc(default["key"])}" data-downloadable="{str(bool(default["download"])).lower()}" href="{esc(default["path"])}">'
        summary = ' · '.join(str(v) for k, v in default['facts'] if k in ('class', 'taxon', 'use'))
        cards.append(f'''<article class="card" data-asset="{esc(gid)}">{selected}<div class="art">{preview(default)}</div>
<div class="cardbody"><div class="eyebrow">{esc(category)}</div><h3>{esc(name_of(gid))}</h3><div class="tags">{esc(summary or gid)}</div>
<div class="cardbottom"><span class="pill {'wait' if not available else ''}">{'Download available' if available else 'Preview only'}</span><span class="price">{'Free' if available else '—'}</span></div></div></a>''')
        others = [e for e in variants if e is not default]
        if others:
            cards.append(f'<details class="variants"><summary>{len(others)} other build(s)</summary><ul>' + ''.join(
                f'<li>{entry_link(e)} <span class="muted">· {"Free" if e["download"] else "Preview only"}</span></li>' for e in others) + '</ul></details>')
        cards.append('</article>')
    hero = next((e for e in entries if e['shots']), None)
    art = f'<div class="heroart">{preview(hero)}<span class="caption">Library render · {esc(hero["name"])}</span></div>' if hero else ''
    serialized = json.dumps(data, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    categories = sorted({a['category'] for a in data})
    category_html = '<button type="button" class="category active" data-category="" aria-pressed="true">All assets</button>' + ''.join(
        f'<button type="button" class="category" data-category="{esc(c)}" aria-pressed="false">{esc(c)}</button>' for c in categories)
    offered = sum(bool(e['download']) for e in entries)
    return f'''<section id="catalog"><div class="hero" {'style="grid-template-columns:1fr"' if not art else ''}><div class="herotext"><div class="eyebrow">The asset library</div>
<h1>A world starts<br>with the details.</h1><p>Explore assets for your next game. Inspect the model, understand the package, and find the right fit for your scene.</p>
<a class="btn" href="#search">Find your next asset ↓</a></div>{art}</div>
<div class="cataloghead"><div><div class="eyebrow muted">Browse the collection</div><h2>Find a place for it.</h2>
<p class="muted small">{len(groups)} assets · {len(entries)} builds · {offered} free packages · library {esc(rev)}</p></div><span id="resultCount" class="small muted" aria-live="polite"></span></div>
<div id="discovery" hidden><div class="searchrow"><div class="search"><span aria-hidden="true">⌕</span><input id="search" type="search" aria-label="Search assets" placeholder="Search names, types, uses or taxa…"></div>
<button id="filtersToggle" class="btn filtersToggle" type="button" aria-controls="filters" aria-expanded="false">Filters</button>
<select id="sort" aria-label="Sort assets"><option value="name">Name: A–Z</option><option value="reverse">Name: Z–A</option><option value="available">Downloads first</option></select></div></div>
<div class="layout"><aside class="filters" id="filters" hidden><div class="eyebrow">Categories</div><div id="categories">{category_html}</div>
<label class="check"><input id="available" type="checkbox"><span>Downloadable assets only</span></label><p class="small muted" style="margin-top:15px">Browse all assets and renders, or filter to complete downloads.<br>Credit included with each download.</p><button class="btn" type="button" data-clear-filters>Clear filters</button></aside>
<div><div id="assetGrid" class="grid">{''.join(cards)}</div><div id="empty" class="empty" hidden><h2>No matching assets.</h2><p>Try another search or category, or tell us what your scene needs.</p><button class="btn" type="button" data-clear-filters>Clear filters</button> <a class="btn primary" href="#request">Request an asset</a></div></div></div>
<noscript><p>All builds are listed above. Enable JavaScript for search, filters and guided requests.</p></noscript>
<div class="callout"><div><h3>Something missing from your world?</h3><p class="small muted">Send a reference photo and describe the asset you need.</p></div><a class="btn" href="#request">Request an asset ↗</a></div>
<p class="small muted" style="margin-top:24px">The 1080 bake is a target display profile, not texture resolution. Free at 1080; finer builds {'on itch when offered on an asset page' if cfg.get('itch') else 'soon'}.</p></section>
{request}{extra}<script id="catalogData" type="application/json">{serialized}</script>'''


def detail(entry, siblings, up, licence, itch, dev_line):
    rel = lambda u: u if '://' in u else up + u
    e = entry
    facts = e['facts'][:]
    if e['variant']:
        facts = [(k + ' (parent default)', v) for k, v in facts]
    facts += [('Baked detail levels', len(e.get('models', [])))]
    if e['triangles'] is not None:
        facts.append(('Finest baked mesh', f'{e["triangles"]:,} triangles'))
    if e['contents']:
        facts.append(('Model format', 'GLB (glTF binary)'))
    if e['download']:
        download = f'<a class="btn primary" href="{esc(rel(e["download"]))}" download="{esc(e["slug"])}.zip">Download free 1080 build ↓</a><p class="small muted">ZIP · {(e["bytes"] + 1023) // 1024:,} KiB · {esc(licence or "")}. Attribution required: include the supplied credit lines when using this asset.</p>'
        download += f'<p class="small muted">Download not starting? <a href="{esc(rel(e["download"]))}" target="_blank" rel="noopener" data-open-package>Open the ZIP in a new tab</a> and save it from your browser.</p>'
    else:
        download = f'<p class="status">Download unavailable: {esc("; ".join(e["gaps"]) or "No complete package in this bake")}.</p>'
    paid = f'<a class="btn" href="{esc(itch)}" target="_blank" rel="noopener">Finer builds on itch ↗</a><p class="small muted">Pay what you want; the same attribution applies.</p>' if itch else '<p class="small muted" style="margin-top:12px">Free at 1080; finer builds soon.</p>'
    nav = ''.join(f'<a class="btn" href="{esc(rel(s["path"]))}" {"aria-current=page" if s is e else ""}>{esc(s["variant"] or "Default build")}</a>' for s in siblings) if len(siblings) > 1 else ''
    # Interactive model first on details; actual renders remain the fallback.
    poster = f'poster="{esc(rel(e["shots"][0]))}"' if e["shots"] else ""
    poster_content = f'<img slot="poster" src="{esc(rel(e["shots"][0]))}" alt="{esc(e["name"])} — library render">' if e['shots'] else '<span slot="poster" class="noimg">Loading 3D preview…</span>'
    model = f'<model-viewer src="{esc(rel(e["model"]))}" alt="{esc(e["name"])} — baked model" camera-controls touch-action="pan-y" shadow-intensity="1" loading="eager" {poster}>{poster_content}</model-viewer>' if e['model'] else preview(e, rel, True)
    recovery = f'<div class="preview-recovery"><button class="btn" type="button" id="retryPreview" hidden>Retry 3D preview</button> <a class="small" href="{esc(rel(e["model"]))}" target="_blank" rel="noopener" data-open-model>Open the GLB model</a></div>' if e['model'] else ''
    models = e.get('models', [])
    controls = ''
    if e['model'] and len(models) > 1:
        controls = '<div class="previewbar" role="group" aria-label="Preview detail level">' + ''.join(
            f'<button type="button" data-model-src="{esc(rel(m["url"]))}" data-model-label="{esc(m["name"])}" aria-pressed="{str(m["rung"] == 0).lower()}" class="{"active" if m["rung"] == 0 else ""}">Level {m["rung"]} · {esc(m["name"])}</button>'
            for m in models) + '</div><p id="modelStatus" class="small muted" role="status">Each level shows its actual baked model.</p>'
    numbers = ''
    if e['cost'] is not None:
        error = f'{e["error"][1]:.1f} px (band {e["error"][0]})' if e['error'] and e['error'][1] is not None else 'No band affordable'
        numbers = f'<h3>Measured at the library baseline</h3><div class="facts"><div class="fact"><span>Draw cost at 1080</span><b>{e["cost"]:,}</b></div><div class="fact"><span>Error at finest affordable band</span><b>{esc(error)}</b></div></div>' + ('<p class="small muted">These measurements describe the parent’s default build.</p>' if e['variant'] else '')
    return f'''<section class="detail"><div class="breadcrumbs"><a href="{up}index.html" data-return-catalog>← Back to catalog</a> / {esc(category_of(e['gid']))} / {esc(e['name'])}</div>
<div class="detailgrid"><div><div class="art detailart">{model}</div>{controls}<p class="loading-note" role="status">{'Loading the interactive 3D preview…' if e['model'] else 'Library render shown where available. The interactive model is not ready yet.'}</p>{recovery}{f'<div class="shots">' + ''.join(f'<img src="{esc(rel(s))}" alt="{esc(e["name"])} — library render" loading="lazy">' for s in e['shots']) + '</div>' if e['shots'] else ''}{'<p class="small muted">Still renders show the parent default build; the 3D model shows this variant.</p>' if e['variant'] and e['shots'] else ''}</div>
<div><div class="eyebrow">{esc(category_of(e['gid']))}</div><h1>{esc(e['name'])}</h1><p class="muted">{esc(e['gid'])}{' · ' + esc(e['variant']) if e['variant'] else ''}</p>
<div class="variantnav" aria-label="Asset builds">{nav}</div><div class="downloadbox"><h3>{'Free download' if e['download'] else 'Package in preparation'}</h3>{download}{paid}</div>
<div class="facts">{''.join(f'<div class="fact"><span>{esc(k)}</span><b>{esc(v)}</b></div>' for k, v in facts)}</div></div></div>
<div class="detailsection"><h2>Know what you’re getting.</h2><p class="small muted">The 1080 bake refers to the library’s target display profile, not texture resolution. Dimensions from the committed ladder describe its default build’s extent, not separately measured width, depth and height.</p>
<h3>{'Package contents' if e['download'] else 'Files present in this incomplete bake'}</h3><ul class="package-list">{''.join(f'<li>{esc(f)}</li>' for f in e['contents'])}{''.join(f'<li>{esc(f)}</li>' for f in e['licence_files'])}</ul>
<p class="small muted">GLB is the binary glTF format. Check your importer’s support for these files; engine compatibility has not been verified by this catalog.</p>{numbers}</div>
<div class="detailsection"><h2>Attribution and license</h2><p>Use the credit lines in ATTRIBUTION.txt. Source reference photos are excluded from the package.</p>
<a class="btn" href="{up}attribution/{esc(e['slug'])}.txt" download>Download attribution</a><details style="margin-top:16px"><summary>Read attribution and package record</summary><pre>{esc(e['attribution'])}</pre></details></div>
<p class="small muted" style="margin-top:24px">{esc(dev_line)}</p></section>'''


def request_form(url, sitekey, ready):
    unavailable = '' if ready else '<p class="status" role="status">The request desk is not connected yet. You can prepare your request here, but sending is unavailable. Return when the desk is connected; nothing has been uploaded.</p>'
    return f'''<section id="request"><div class="requestintro"><div class="eyebrow muted">Help shape the library</div><h1>What does your world need?</h1><p>Suggest an asset with a reference photo. A receipt means it entered the review queue, not that it was approved for production.</p>{unavailable}</div>
<noscript><p>Enable JavaScript to prepare, review and submit a request.</p></noscript>
<div class="requestlayout" id="requestFlow" hidden><div class="formbox"><div class="steps" aria-label="Request progress"><span class="step">1 · Asset</span><span class="step">2 · Photo</span><span class="step">3 · Permissions</span><span class="step">4 · Review</span><span class="step">5 · Receipt</span></div>
<form id="requestForm" method="post" enctype="multipart/form-data" action="{esc(url) if ready else ''}" data-ready="{str(ready).lower()}" data-sitekey="{esc(sitekey) if ready else ''}" novalidate>
<div id="formError" class="error" role="alert" hidden></div><p id="submissionStatus" class="status" role="status" hidden></p>
<section data-stage="0"><h2>Describe the asset.</h2><label class="field" for="requestText">What does your scene need?</label><textarea id="requestText" name="text" required maxlength="2000" aria-describedby="textHint textError" placeholder="Describe the object, its shape, materials and how you plan to use it."></textarea><span id="textHint" class="hint">A useful description, up to 2,000 characters.</span><span id="textError" class="field-error"></span></section>
<section data-stage="1" hidden><h2>Add a reference photo.</h2><div class="upload"><label for="photo"><strong>Photo you took</strong></label><span class="hint">One JPEG, PNG or WebP, up to 10 MiB.</span><input id="photo" name="photo" type="file" accept="image/jpeg,image/png,image/webp" required aria-describedby="photoHint photoError"><img id="photoPreview" alt="Your selected reference photo" hidden><span id="photoInfo" class="hint"></span><span id="photoError" class="field-error"></span></div><p id="photoHint" class="small muted">Preview stays on this device until you send. Remove location metadata before submitting; the service rejects photos with GPS metadata or unreadable location metadata.</p></section>
<section data-stage="2" hidden><h2>Contact and photo permissions.</h2><label class="field" for="contact">How can the team reach you? (required)<input id="contact" name="contact" required maxlength="200" autocomplete="email" aria-describedby="contactHint contactError"><span id="contactHint" class="hint">An email address or another contact method. Kept in the private request queue.</span><span id="contactError" class="field-error"></span></label>
<label class="field" for="credit">Credit name (optional)<input id="credit" name="contributed_by" maxlength="80" autocomplete="name" aria-describedby="creditHint creditError"><span id="creditHint" class="hint">Up to 80 characters. Use a name, not an email address. This is the name to use for attribution.</span><span id="creditError" class="field-error"></span></label>
<fieldset class="radios" id="licenceGroup" aria-describedby="licenceError"><legend>Choose your reference photo’s license</legend><label><input type="radio" name="licence" value="CC-BY-4.0" required><span><b>CC BY 4.0 — credit required</b><br>Others may share and adapt the photo with attribution. <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">Read the license ↗</a></span></label><label><input type="radio" name="licence" value="CC0-1.0"><span><b>CC0 — no credit required</b><br>Dedicate the photo to the public domain. <a href="https://creativecommons.org/publicdomain/zero/1.0/" target="_blank" rel="noopener">Read the terms ↗</a></span></label><span id="licenceError" class="field-error"></span></fieldset>
<label class="check"><input id="ownership" type="checkbox" required aria-describedby="ownershipError"><span>I took this photo and can grant the selected permission.</span></label><span id="ownershipError" class="field-error"></span>
<label class="check" style="margin-top:16px"><input id="consent" name="consent" value="yes" type="checkbox" required aria-describedby="consentError"><span>Everyone identifiable in the photo agreed to its use (or it’s me), and no children appear in it.</span></label><span id="consentError" class="field-error"></span></section>
<section data-stage="3" hidden><h2>Review your request.</h2><div id="review"></div><p class="small muted" style="margin-top:20px">Sending uploads your photo, description, contact and permissions to the private request queue. Requests are reviewed by a person. No delivery date or production approval is promised.</p><div id="turnstileWidget"></div><p id="challengeStatus" class="hint" role="status"></p></section>
<div class="formactions"><button id="backStep" class="btn" type="button" hidden>Back</button><button id="nextStep" class="btn primary" type="submit">Continue →</button></div></form></div>
<aside class="sidebar"><h3>A reference, not an instant conversion.</h3><p>Your photo helps describe a proposed asset. Sending it does not instantly turn it into a 3D model.</p><h3>What happens next?</h3><p>Accepted submissions enter the private review queue. Keep your request ID as a receipt. There is no customer status page or automatic email notification.</p></aside></div>
<div id="receipt" class="receipt" hidden><div class="stamp" aria-hidden="true">✓</div><div class="eyebrow muted">Request receipt</div><h2 tabindex="-1" id="receiptTitle">Your request was received.</h2><p>Save this request ID:</p><code id="receiptId"></code><button id="copyReceipt" class="btn" type="button">Copy request ID</button><p id="copyStatus" class="small muted" role="status"></p><div class="toast">Receipt confirms submission, not production approval. No customer tracking page or automatic email notifications are available.</div><a class="btn primary" href="#catalog">Back to catalog</a><button id="newRequest" class="btn" type="button">Start another request</button></div></section>'''
