#!/usr/bin/env python3
"""THE CATALOG, the pulse's public half (the-release-infrastructure-this-week,
"The explorer, re-read"): one static page per subject, from the library's
committed JSON and this run's renders, with the 1080 bake as a free download --
the whole offer until itch, the only store, exists for the finer builds.

    tools/catalog.py out/<date>      # writes out/<date>/catalog/

Environment (all optional to build; tools/publish.sh needs them to deploy):
    CATALOG_PUBLIC_BASE  where the objects are served from, ending in / (default
                         `objects/`, beside the pages)
    CATALOG_INTAKE_URL   deployed HTTPS /v1/requests URL; takes precedence
    EDGE_ZONE            the owner's domain: the request form posts to agent A's
                         public intake on it (its local URL until then)
    ITCH_URL             the pay-what-you-want page for the finer builds; empty
                         until the store exists (stage 1), and the pages then
                         read "free at 1080; finer builds soon"
    TURNSTILE_SITEKEY    public production widget key; required to enable sending

What it reads, and decides nothing about (the owner's decisions, 2026-10-03):
  - the bake (asset-explorer's tools/bake-library.gd via tools/bake.sh): every
    rung's glTF and, when the bake carries it, the impostor end and its atlas.
    The ladder end is part of the asset: a subject whose committed ladder ends
    in an impostor is offered for download only when its bake carries that rung
    and its atlas, never as an asset missing its end;
  - the library's scorecard (`tools/scorecard.py --json`), for the two numbers
    a public page shows: the draw cost at the 1080 baseline (`src_cost`) and the
    error at the finest band the scorecard counts as covered (`error_px`);
  - the committed JSON: each subject's ladder and card (class, size, rungs, how
    the ladder ends, taxon, use, and `provenance`: plate, contributor, licence),
    `plates/manifest.json` (each plate's name, kind and `licence`), and the
    runtime's licence (`ops/runtime/runtime.toml`, its LICENSE);
  - the run's close-ups (the library's tools/closeup.sh), as the renders.

What it writes: objects/<sha256[:16]>.<ext> (every glTF, atlas, render, zip:
named by content, so an unchanged byte is never uploaded twice), one page per
subject and an index, attribution/<subject>.txt (the file each download carries,
on its own for the itch builds to carry too), and objects.json for publish.
"""
import hashlib
import html
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tomllib
import zipfile
import io
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
import catalog_ui as ui

# Only the image encoder is shared with the private scorecard (loaded by
# path: `site` is also the name of a standard-library module).
_spec = importlib.util.spec_from_file_location("pulse_site", Path(__file__).resolve().parent / "site.py")
_site = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_site)
small_jpeg = _site.small_jpeg

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "library"
ZIP_DATE = (1980, 1, 1, 0, 0, 0)

class Objects:
    """Content-addressed files: the name is the first 16 hex of the sha256."""

    def __init__(self, folder, base):
        self.folder, self.base, self.listed = folder, base, {}
        folder.mkdir(parents=True, exist_ok=True)

    def put(self, data, ext, kind):
        name = "%s%s" % (hashlib.sha256(data).hexdigest()[:16], ext)
        path = self.folder / name
        if not path.exists():
            path.write_bytes(data)
        self.listed[name] = {"bytes": len(data), "kind": kind}
        return self.base + name


def viewer_module(cfg, site):
    """Ship the pinned viewer with the site; visitors need no script CDN.

    Verify downloads and cached bytes. If the module cannot be obtained, fail
    the build rather than publishing detail pages with a broken viewer.
    """
    cache = ROOT / 'out' / 'viewer-cache'
    cache.mkdir(parents=True, exist_ok=True)
    for setting, filename in (('model_viewer', 'model-viewer.min.js'),
                              ('model_viewer_license', 'model-viewer-LICENSE.txt')):
        expected = cfg.get(setting + '_sha256', '')
        url = cfg.get(setting, '')
        if len(expected) != 64 or not url.startswith('https://'):
            sys.exit('catalog: pinned viewer URL and SHA256 are required for ' + setting)
        path = cache / expected
        data = path.read_bytes() if path.exists() else b''
        if hashlib.sha256(data).hexdigest() != expected:
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != expected:
                sys.exit('catalog: viewer integrity check failed for ' + setting)
            path.write_bytes(data)
        (site / filename).write_bytes(data)
    return 'model-viewer.min.js'


def edge_urls():
    """Explicit deployed URL wins; the library's zone URL is the only fallback.

    workers.dev placeholders and local dev endpoints are never customer actions.
    The library table now has four URL/method columns; do not mistake the
    workers.dev template for a local or deployed endpoint.
    """
    url = os.environ.get("CATALOG_INTAKE_URL", "").strip()
    source = "CATALOG_INTAKE_URL" if url else "not configured"
    zone = os.environ.get("EDGE_ZONE", "").strip()
    readme = LIB / "ops" / "edge" / "README.md"
    if not url and zone and readme.exists():
        for line in readme.read_text().splitlines():
            cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[0].lower().startswith("intake"):
                url = cells[1].replace("<zone>", zone)
                source = "ops/edge/README.md with EDGE_ZONE"
                break
    parsed = urlsplit(url)
    valid = (parsed.scheme == "https" and bool(parsed.hostname)
             and parsed.hostname not in ("localhost", "127.0.0.1", "::1")
             and not any(c in url for c in "<>\\\r\n")
             and not parsed.username and not parsed.password
             and parsed.path == "/v1/requests" and not parsed.query and not parsed.fragment)
    key = os.environ.get("TURNSTILE_SITEKEY", "").strip()
    # Cloudflare's public test keys must never enable a production form.
    test_key = key.startswith(("1x", "2x", "3x"))
    ready = bool(valid and key and not test_key)
    return {"intake": url if valid else "", "from": source,
            "ready": ready, "unavailable": "" if ready else "Set a deployed HTTPS CATALOG_INTAKE_URL (or EDGE_ZONE) and a production TURNSTILE_SITEKEY"}


# The one place this is written (the principal session, 2026-10-03): under the
# downloads, here and in the README.
DEV_MODE_LINE = ("In the game, tap the build number on the start card seven times to turn on "
                 "developer mode: inspect any subject and download it from there.")

# THE COFFEE AND THE PRIORITY RULE (the-library-as-a-commons step 5), on the
# catalog's index and nowhere else. The link is one config value, hidden while
# empty. The rule sells priority, so it is shown only while the library's own
# measure says a coffee pays for a commission (`tools/commission-cost.py`
# prints "falsifier holds"); until then a set link is a thank-you that buys
# nothing, as the plan has it.
PRIORITY_LINE = ("A sponsor's request is authored first: requests from sponsors go to the front of the "
                 "queue. What is made from them is still free for everyone, with its attribution file.")
THANKS_LINE = ("A coffee is a thank-you and buys nothing: every subject here stays free, and requests "
               "are authored in the order the library can afford them.")


def coffee_gate():
    """True when the library's commission cost lets a coffee buy priority."""
    tool = LIB / "tools" / "commission-cost.py"
    if not tool.exists():
        return False
    r = subprocess.run([sys.executable, str(tool)], cwd=LIB, capture_output=True, text=True)
    return "falsifier holds" in r.stdout


LICENCE_TEXTS = ("LICENSE-PLATES.md", "LICENSE-RUNTIME.md", "PLATES-CC-BY-4.0.txt")
SPDX_NAMES = {"CC-BY-4.0": "Creative Commons Attribution 4.0 International (CC BY 4.0)", "MIT": "MIT"}


def download_licence():
    """The baked assets' licence as the library names it (`assets_licence` in
    ops/runtime/runtime.toml) and the licence texts the studio drafted under
    docs/press/licences/ (attribution for plates and assets, open for the
    runtime). Every download carries all of them; with any missing, nothing is
    offered (the owner's condition for going public, 2026-10-03)."""
    toml = LIB / "ops" / "runtime" / "runtime.toml"
    cfg = tomllib.loads(toml.read_text()) if toml.exists() else {}
    folder = LIB / "docs" / "press" / "licences"
    texts = [(n, (folder / n).read_text()) for n in LICENCE_TEXTS if (folder / n).exists()]
    if not cfg.get("assets_licence") or len(texts) != len(LICENCE_TEXTS):
        return None, []
    return cfg["assets_licence"], texts


def plate_hashes():
    """Every plate's sha256: no file the catalog writes may be one of them --
    only generated output of the library is published, never a source plate or
    a requester's photo."""
    return set(json.loads((LIB / "plates" / "manifest.json").read_text()).get("plates", {}).keys())


def committed(gid):
    """A subject's committed ladder and card, by its generator id."""
    group, name = gid.split("/", 1)
    base = LIB / "generators" / group / name.replace("-", "_")
    load = lambda p: json.loads(p.read_text()) if p.exists() else {}
    return load(Path(str(base) + ".ladder.json")), load(Path(str(base) + ".card.json"))


def facts_of(L, C):
    rows = [("class", L.get("class")), ("Default extent", "%.2f m" % L["extent_m"] if L.get("extent_m") else None),
            ("rungs", L.get("mesh_rungs")), ("ladder ends", L.get("ladder_end")),
            ("taxon", C.get("taxon")), ("use", C.get("use"))]
    return [(k, v) for k, v in rows if v not in (None, "")]


def two_numbers(row):
    """The draw cost at the 1080 baseline and the error at the finest band the
    scorecard counts as covered: the library's numbers, picked, never computed."""
    if not row:
        return None, None
    covered = [b for b in row.get("bands", []) if b.get("covered")]
    finest = min(covered, key=lambda b: b["band"]) if covered else None
    return row.get("src_cost"), (finest["band"], finest.get("error_px")) if finest else None


def attribution(key, gid, rev, licence, C, plates, files):
    """ATTRIBUTION.txt in the library's own form (tools/attribution.gd): the
    plates the subject's card cites, each with its name, kind, contributor and
    licence from plates/manifest.json."""
    out = ["ATTRIBUTION -- %s, from the asset-generators library" % key,
           "",
           "Generated by asset-pulse from the library's provenance at commit %s." % rev,
           "Never edited by hand: regenerate it.",
           "",
           "The assets in this download are licensed under %s:" % SPDX_NAMES.get(licence or "", licence or "?"),
           "https://creativecommons.org/licenses/by/4.0/ -- you may use, change and sell",
           "them, in games and anywhere else, as long as you credit them with the lines",
           "below. LICENSE-PLATES.md and PLATES-CC-BY-4.0.txt are the licence and its",
           "legal code; LICENSE-RUNTIME.md says what of the library's code is open (its",
           "interface, MIT) and what is not (the generators, all rights reserved).",
           "",
           "%s rests on the plates listed below: photographs, drawings and traced" % gid,
           "outlines the library measured. No plate's bytes are in this download; each",
           "is cited by sha256. Credit the contributors under each plate's licence.",
           ""]
    rows = C.get("provenance") or []
    if not rows:
        out.append("  no plate cited")
    for row in sorted(rows, key=lambda r: r.get("plate", "")):
        h = row.get("plate", "")
        p = plates.get(h, {})
        out.append("  plate %s  %s  %s  contributed by %s  licence: %s" % (
            h[:12], p.get("original_name") or "?", p.get("kind") or "?",
            row.get("contributed_by") or p.get("contributed_by") or "?",
            p.get("licence") or row.get("licence") or "?"))
    out += ["", "Files in this download:"] + ["  %s" % f for f in files]
    return "\n".join(out) + "\n"


def deterministic_zip(members):
    """Fixed dates and order: the same bytes give the same zip and hash."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(members):
            info = zipfile.ZipInfo(name, ZIP_DATE)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    return buf.getvalue()


def renders_of(run, gid):
    d = run / gid.replace("/", "_")
    return sorted(d.glob("*closeup*.png")) if d.exists() else []


def catalog_entries(bake):
    """Discovery comes from committed cards; only the bake supplies files.

    Package targets are library-owned metadata. Keep their tagged variants
    visible even when a budgeted bake has not reached them yet.
    """
    entries = {}
    for path in sorted((LIB / "generators").glob("*/*.card.json")):
        card = json.loads(path.read_text())
        gid = card.get("id")
        if not gid:
            continue
        key = gid.replace("/", "-")
        entries[key] = {"key": key, "generator": gid, "rungs": []}
        for target in card.get("package_targets", []):
            target_gid = target.get("id", gid)
            tag = target.get("tag", "")
            target_key = target_gid.replace("/", "-") + ("-" + tag if tag else "")
            entries[target_key] = {"key": target_key, "generator": target_gid, "rungs": []}
    entries.update((e["key"], e) for e in bake.get("entries", []))
    return sorted(entries.values(), key=lambda e: e["key"])


def scorecard_rows():
    r = subprocess.run([sys.executable, "tools/scorecard.py", "--json"], cwd=LIB, capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip().startswith("{"):
        return {}
    d = json.loads(r.stdout)
    return {s["id"]: s for s in d.get("subjects", [])} if isinstance(d.get("subjects"), list) else {}


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    run = Path(argv[1]).resolve()
    cfg = json.loads((ROOT / "catalog.json").read_text())
    bake_dir = LIB / "build" / "artifacts"
    if not (bake_dir / "manifest.json").exists():
        sys.exit("catalog: no bake at %s -- run tools/bake.sh" % bake_dir)
    bake = json.loads((bake_dir / "manifest.json").read_text())
    plates = json.loads((LIB / "plates" / "manifest.json").read_text()).get("plates", {})
    rev = subprocess.run(["git", "-C", str(LIB), "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip() or "?"
    licence, licence_texts = download_licence()
    reserved = plate_hashes()
    max_file = int(os.environ.get("PAGES_MAX_FILE_BYTES", str(100 * 1000 * 1000)))
    scores = scorecard_rows()
    urls = edge_urls()
    itch = os.environ.get("ITCH_URL", "")
    site = run / "catalog"
    shutil.rmtree(site, ignore_errors=True)   # a rebuild publishes only what this build wrote
    (site / "subject").mkdir(parents=True, exist_ok=True)
    (site / "attribution").mkdir(exist_ok=True)
    objs = Objects(site / "objects", os.environ.get("CATALOG_PUBLIC_BASE", "objects/"))
    model_viewer = viewer_module(cfg, site)

    def subject_path(key, gid):
        """THE STABLE URL, /subject/<id>/ (the game's inspect links to it): the
        generator's own id for its default build, and /subject/<id>/<variant>/
        for a variant the library bakes beside it."""
        default = gid.replace("/", "-")
        variant = key[len(default) + 1:] if key.startswith(default + "-") else ""
        return "subject/%s/%s" % (gid, (variant + "/") if variant else "")

    entries, gaps_all = [], []
    for asset in (ROOT / "tools" / "catalog-assets").iterdir():
        if asset.suffix in (".css", ".js"):
            shutil.copyfile(asset, site / asset.name)
    for e in catalog_entries(bake):
        key, gid = e["key"], e.get("generator", e["key"])
        slug = key.replace("/", "_")
        path = subject_path(key, gid)
        L, C = committed(gid)
        rungs = sorted(e.get("rungs", []), key=lambda r: int(r.get("rung", 0)))
        members, listed, rung0, gaps, no_atlas, models = [], [], None, [], [], []
        if not rungs:
            gaps.append("The downloadable build is not ready yet")
        for r in rungs:
            g = r.get("gltf") or r.get("file")
            if not g or not (bake_dir / g).exists():
                gaps.append("rung %s: no glTF in this bake" % r.get("rung"))
                continue
            data = (bake_dir / g).read_bytes()
            name = "%s/rung%d.glb" % (slug, int(r["rung"]))
            members.append((name, data))
            listed.append("%s  (%s triangles%s)" % (name, r.get("triangles", "?"), ", the impostor" if r.get("impostor") else ""))
            model_url = objs.put(data, ".glb", "gltf")
            rung = int(r["rung"])
            names = C.get("rung_names", [])
            models.append({"url": model_url, "rung": rung,
                           "name": names[rung] if rung < len(names) else ("Impostor" if r.get("impostor") else "Level %d" % rung),
                           "triangles": r.get("triangles")})
            if rung == 0:
                rung0 = model_url
            if r.get("impostor"):
                atlas = r.get("atlas_file")
                if atlas and (bake_dir / atlas).exists():
                    members.append(("%s/%s" % (slug, Path(atlas).name), (bake_dir / atlas).read_bytes()))
                    listed.append("%s/%s  (the impostor's atlas)" % (slug, Path(atlas).name))
                else:
                    no_atlas.append(int(r.get("rung", 0)))
        # A package must carry every declared mesh rung as well as its end.
        expected = int(L.get("mesh_rungs") or 0)
        present = {int(r.get("rung", 0)) for r in rungs}
        for missing in sorted(set(range(expected)) - present) if rungs else []:
            gaps.append("rung %d: absent from this bake" % missing)
        # THE LADDER END IS PART OF THE ASSET (the owner, 2026-10-03): name the
        # rung that lacks its impostor atlas, the last rung of the committed
        # ladder when the bake does not carry it at all.
        if rungs and L.get("ladder_end") == "impostor" and not any(
                r.get("impostor") and r.get("atlas_file") for r in rungs):
            end = L.get("mesh_rungs", len(rungs))
            if end not in no_atlas:
                no_atlas.append(int(end))
        for k in sorted(no_atlas):
            gaps.append("rung %d, its impostor, lacks an impostor atlas in this bake" % k)
        if not licence_texts:
            gaps.append("the library's licence texts (docs/press/licences/) are not at this pin")
        offered = bool(members) and not gaps
        text = attribution(key, gid, rev, licence, C, plates,
                           [m.split("  ")[0] for m in listed] + ["ATTRIBUTION.txt"] + [n for n, _ in licence_texts])
        (site / "attribution" / ("%s.txt" % slug)).write_text(text)
        zip_url, zipped = None, b""
        if offered:
            members.append(("ATTRIBUTION.txt", text.encode()))
            members += [(n, t.encode()) for n, t in licence_texts]
            leaked = [n for n, d in members if hashlib.sha256(d).hexdigest() in reserved]
            if leaked:
                sys.exit("catalog: REFUSED -- %s would publish a plate's bytes: %s" % (key, leaked))
            zipped = deterministic_zip(members)
            if len(zipped) > max_file:
                gaps.append("its zip is %d MB, over the Pages file limit; it waits for R2" % (len(zipped) // 1000000))
                gaps_all.append("%s: zip over the Pages file limit" % key)
            else:
                zip_url = objs.put(zipped, ".zip", "zip")
        else:
            gaps_all += ["%s: %s" % (key, g) for g in gaps]

        shots = []
        for png in renders_of(run, gid):
            tmp = site / ".shot.jpg"
            small_jpeg(png, tmp)
            shots.append(objs.put(tmp.read_bytes(), ".jpg", "render"))
            tmp.unlink()
        variant = ui.variant_of(key, gid)
        cost, err = two_numbers(scores.get(gid))
        e = {"key": key, "gid": gid, "slug": slug, "path": path,
             "name": ui.name_of(gid) + (" · " + variant if variant else ""),
             "variant": variant, "facts": facts_of(L, C), "shots": shots,
             "model": rung0, "models": models, "download": zip_url, "bytes": len(zipped),
             "levels": len(rungs), "triangles": next((r.get("triangles") for r in rungs if int(r.get("rung", 0)) == 0), None),
             "contents": listed, "licence_files": ["ATTRIBUTION.txt"] + [n for n, _ in licence_texts],
             "attribution": text, "gaps": gaps, "cost": cost, "error": err}
        entries.append(e)

    itch = ui.safe_url(itch)
    cfg["itch"] = itch
    for e in entries:
        path = e["path"]
        up = "../" * (path.rstrip("/").count("/") + 1)
        siblings = [s for s in entries if s["gid"] == e["gid"]]
        body = ui.detail(e, siblings, up, licence, itch, DEV_MODE_LINE)
        (site / path).mkdir(parents=True, exist_ok=True)
        head = ('<script type="module" src="%s" data-model-viewer-module></script>' % html.escape(up + model_viewer, quote=True)) if e['model'] else ''
        (site / path / "index.html").write_text(ui.page(e["name"], body, up, head))

    sitekey = os.environ.get("TURNSTILE_SITEKEY", "").strip()
    request = ui.request_form(urls["intake"], sitekey, urls["ready"])
    head_index = ('<script type="module" src="%s" data-model-viewer-module></script>' % html.escape(model_viewer, quote=True)) if any(e['model'] and not e['shots'] for e in entries) else ''
    offered = sum(bool(e["download"]) for e in entries)
    extra = "<p class=\"small muted\">%s</p>" % html.escape(DEV_MODE_LINE)
    sponsors = ui.safe_url(cfg.get("sponsors_url", ""))
    if sponsors:
        extra += ("<div class=callout><div><h2>Buy the library a coffee</h2><p>%s</p></div>"
                  "<a class=btn href='%s' rel=noopener target=_blank>Sponsor on GitHub</a></div>" % (
                      html.escape(PRIORITY_LINE if coffee_gate() else THANKS_LINE), html.escape(sponsors, quote=True)))
    body = ui.index(entries, cfg, rev, request, extra)
    (site / "index.html").write_text(ui.page(cfg["title"], body, head=head_index, catalog=True))
    if not urls["ready"]:
        print("catalog: request desk unavailable -- " + urls["unavailable"])
    (site / "objects.json").write_text(json.dumps({"library": rev, "base": objs.base, "edge": urls, "itch": itch,
                                                   "objects": objs.listed}, indent=1, sort_keys=True))
    for f in (site / "objects").iterdir():
        if hashlib.sha256(f.read_bytes()).hexdigest() in reserved:
            sys.exit("catalog: REFUSED -- %s is a plate's bytes" % f.name)
    big = [f.name for f in (site / "objects").iterdir() if f.stat().st_size > max_file]
    if big:
        sys.exit("catalog: REFUSED -- over the Pages file limit: %s" % big)
    for g in gaps_all:
        print("catalog: GAP %s" % g)
    print("catalog: %d subject(s), %d with a download, %d object(s) (%d KB) in %s; intake from %s; itch %s" % (
        len(entries), offered, len(objs.listed), sum(o["bytes"] for o in objs.listed.values()) // 1024, site,
        urls["from"], "set" if itch else "unset"))


if __name__ == "__main__":
    main(sys.argv)
