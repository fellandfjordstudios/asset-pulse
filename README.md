# asset-pulse

The owner's daily read of the asset library: every generator, its scorecard
row, and (step 1) its bands rendered, on one private page, with a history so
the page shows a direction and not a snapshot.

This repository is a CONSUMER of `codestiff/asset-generators`, pinned by commit
in `library.lock`, exactly as `transect` is. It calls the library's tools and
decides nothing itself about scoring or rendering, so it cannot drift from the
library: a change there moves the pulse at the next bump and nowhere else. The
plan it executes is the library's
`fable-plans/active/the-pulse-is-a-consumer`.

## Run

    ./daily.sh                        THE DAILY RUN: everything below, then commit,
                                      push and print a report -- what a session runs

    ./run.sh                          sync to the pin, scorecard, history row, renders, page
    ./run.sh --bump                   first move the pin to the library's main
    ./run.sh --no-render              the scorecard and the row only
    PULSE_BACKLOG=0 ./run.sh          skip the derivation backlog (a quick look)
    PULSE_RESUME=1 ./run.sh           resume a run cut short (a restart, a time limit): subjects
                                      already rendered at the same pin are not rendered again, and
                                      the bake (tools/bake.sh) skips the atlases and every subject
                                      already baked at the same library and explorer pins
    PULSE_DERIVE=none ./run.sh        drawn today only: no derived column
    PULSE_ONLY="built/vase" ./run.sh  render one subject, for a manual look

Output lands in `out/<date>/` (gitignored): `scorecard.txt`, `manifest.json`,
one directory per subject (the library's sheet pages, `sheet-bands.json`, the
close-up) and `site/` -- `index.html` and one page per subject, static, images
under 100 KB. `history.csv` is the only generated file committed: one row per
run, the day's totals, and `failed:<step>` when a run did not finish.

The derivation search is the slow part and runs once, in the backlog step
(hours on a full backlog, little on a quiet day); the sheets then read its
goal table and take seconds each. Each subject's renders are capped by the run
(`PULSE_CAP_S`, 1800).

## Rules

- The library is never edited from here, with one exception: the derivation
  backlog (`tools/backlog.sh`). The pulse runs the library's own expensive
  job once a day (the owner, 2026-10-02: pay for it once) and pushes exactly
  the files that job writes -- the derivation tables and records -- through the
  library's gate, or to `run/derive-backlog-<date>` when the gate refuses. A
  gap goes to the library's `feedback/`.
- No images and no generated geometry in git, here or in the library. Images
  go to the object store (step 3).
- The pulse reports; it is not a gate on anything.
- The page is private: the owner's login only (step 3). The public face of the
  library is `asset-explorer`, which hands people assets without the code.

## Steps (the plan's, and the release plan's agent D)

0. the pin, the sync, the scorecard, the first history row -- done
1. the renders: the library's per-band sheet and close-up for every subject --
   verified by one full run 2026-10-02 (pin 93fed38, 37 min, 54 subjects; 17
   fail in the library's tools, filed in its feedback/)
2. the page: one per subject (scorecard row, band sheet, history) and an index
   with the totals and their trend -- `tools/site.py`, checked at 390 px
3. the catalog, the pulse's public half: `tools/bake.sh` (asset-explorer's
   bake, pinned in `explorer.lock`, run as its refresh.sh ran it), then
   `tools/catalog.py`: one static page per subject from the library's committed
   JSON (class, size, rungs, ladder end, taxon, use), its close-ups and a
   `<model-viewer>` of rung 0; two numbers from the scorecard (draw cost at the
   1080 baseline, error at the finest affordable band); the 1080 bake free as
   a zip of every rung's glTF, the impostor and its atlas when the ladder ends
   in one, `ATTRIBUTION.txt` (the card's plates, contributor and licence, in
   the library's own form) and the runtime's open LICENSE. A subject whose
   ladder ends in an impostor is offered only when its bake carries the
   impostor: the ladder end is part of the asset (the owner, 2026-10-03).
   Finer builds will be pay-what-you-want on itch, the only store, from stage 1
   (`ITCH_URL`); until then the pages read "free at 1080; finer builds soon"
   and the free 1080 download is the whole offer. The request form
   posts to agent A's intake. Every subject page has a stable URL,
   `/subject/<id>/` (the generator's id, e.g. `/subject/plant/rowan/`; a variant
   the library bakes beside it at `/subject/<id>/<variant>/`), for the game's
   inspect to link to. Under the downloads, here and on the index page only:

   > In the game, tap the build number on the start card seven times to turn on developer mode: inspect any subject and download it from there.

   Objects are named by content hash for the
   `catalog` bucket. Verified locally 2026-10-03 at library 552e8ca.
4. publishing: `tools/publish.sh` -- objects to R2, the pulse to Pages behind
   Access on `pulse.<zone>`, the catalog to the `asset-explorer` Pages project
   on its existing hostname (`asset-explorer.pages.dev`, from the explorer's
   `wrangler.toml`, the only file of the retired app this touches). It reads
   CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, EDGE_ZONE and
   CATALOG_PUBLIC_BASE from the environment (ITCH_URL optional) and, until
   they are set, stops before deploying with a message naming the missing
   ones (exit 3).
5. the schedule: `.github/workflows/pulse.yml`, the daily run on GitHub
   Actions (cron 05:37 UTC and by hand), deploying the catalog to GitHub Pages
   at `https://codestiff.github.io/asset-pulse/` once it can run; until then a
   daily Routine runs `./daily.sh` in a cloud session.

## The coffee and the priority rule (the-library-as-a-commons step 5)

The catalog's index, and nowhere else, carries a coffee link to GitHub
Sponsors, read from one value (`sponsors_url` in `catalog.json`) and hidden
while it is empty. Beside it, one of two lines:

- while the library's `tools/commission-cost.py` prints "falsifier holds" (a
  coffee pays for a commission): "A sponsor's request is authored first:
  requests from sponsors go to the front of the queue. What is made from them
  is still free for everyone, with its attribution file."
- until then (on 2026-10-03 it printed "$187.75 per held commission, against
  the plan's $100 -- falsifier FIRES"): "A coffee is a thank-you and buys
  nothing: every subject here stays free, and requests are authored in the
  order the library can afford them."

The rule switches by itself on the run after the library's measure changes;
nothing here has to be edited.

## The pulse plan, closed (fable-plans/active/the-pulse-is-a-consumer)

Landed as built, by the owner's decision of 2026-10-03: the public half is a
catalog on GitHub Pages, deployed by a GitHub Actions workflow
(`.github/workflows/pulse.yml`), not R2 behind Access. Its findings:

- **Step 0, the pin and the scorecard:** landed 2026-10-01; the library's own
  `tools/scorecard.py` replaced the prototype on 2026-10-03 and the row reads
  both.
- **Step 1, the renders:** verified on a fresh checkout 2026-10-03 (the
  session hook, the import before the first sheet, 54 subjects, 40 min). The
  failures are the library's, filed in its feedback/: subjects with no ladder,
  close-ups that find no surface at their default height.
- **Step 2, the private page:** one page per subject (scorecard line, band
  sheet, history) and an index with the totals and their trend. Built every
  run; not deployed anywhere (it carries the cost rows and the sheets).
- **Step 3, publishing:** the catalog, public on GitHub Pages: one page per
  subject at `/subject/<id>/`, two numbers from the scorecard, the 1080 bake
  free (CC BY 4.0, ATTRIBUTION.txt and the licence texts in every zip), no
  plate's bytes ever. 14 of 69 entries wait on the library's bake carrying the
  impostor end (filed). The Cloudflare path (`tools/publish.sh`) stays for
  later and stops without its values.
- **Step 4, the schedule:** the workflow runs daily at 05:37 UTC; a cloud
  Routine runs `./daily.sh` until the workflow's first green run.
- **Step 5, the per-band sheet:** in use since 2026-10-02 (the library's
  `tools/rung-sheet.py`).
- **The address:** `https://codestiff.github.io/asset-pulse/` once the two
  steps below are done.

### The owner's two steps, on a phone

1. **Give the workflow a key to the library.**
   - On github.com, tap your picture, then **Settings**, then **Developer
     settings** (at the bottom), then **Personal access tokens**, then
     **Fine-grained tokens**, then **Generate new token**.
   - Name it `asset-pulse library`. Under **Repository access** pick **Only
     select repositories** and choose **asset-generators** and
     **asset-explorer**.
   - Under **Permissions**, **Repository permissions**, set **Contents** to
     **Read-only**. Nothing else.
   - Tap **Generate token** and copy it.
   - Open the **asset-pulse** repository, then **Settings**, **Secrets and
     variables**, **Actions**, **New repository secret**. Name: `LIBRARY_TOKEN`.
     Paste the token. **Add secret**.
2. **Turn on the public page.**
   - In the **asset-pulse** repository: **Settings**, then **Pages**.
   - Under **Build and deployment**, set **Source** to **GitHub Actions**.
   - (The repository is private: GitHub serves Pages from a private
     repository only on a paid plan. If the Source menu is missing, that is
     why.)

Then, in the repository's **Actions** tab, open **pulse** and tap **Run
workflow**, or wait for 05:37 UTC. The run takes about an hour; the address
above then shows the catalog.

## Calls made here (the plan lives in the library, which this repository never edits)

- 2026-10-03, the owner's five decisions (relayed by Fable) applied in f63acca.
- A subject whose committed ladder ends in an impostor has no download until
  the bake carries the impostor rung and its atlas, rather than a download
  without its end (decision 1). Filed: `the-bake-stops-at-the-last-mesh-rung-4bdef5cf`.
- "Error at the finest affordable band" is the scorecard's `error_px` on the
  lowest-numbered band it marks `covered`; "cost at the 1080 baseline" is its
  `src_cost`. A variant shows its generator's default numbers and says so.
- Plate licences are printed as the manifest's `licence` field holds them; all
  123 still read "all rights reserved". Filed:
  `every-plates-licence-still-reads-all-rights-reserved-94e1e0e6`.
- The download's licence is the baked assets' (`assets_licence`, CC BY 4.0);
  each zip carries the library's licence texts as they stand at the pin
  (since fe6330c9: the interface MIT, the generators all rights reserved).
- The band sheets are private (decision 2: two numbers only on public pages).
- The baked-channel bake falls back to the library's default when it refuses
  (filed: `three-flat-baked-channels-refuse-the-whole-transfer-bake-b6c7043d`).
- 2026-10-03, the plan's revision (itch is the only store, from stage 1):
  ITCH_URL is optional; empty, the paid-build link reads "free at 1080;
  finer builds soon", and publish no longer waits on it.

- 2026-10-03, going public (the owner: "If we don't have a license issue, sure,
  go public"): there is none -- the baked assets are CC BY 4.0 (`assets_licence`
  in ops/runtime/runtime.toml), each download carries ATTRIBUTION.txt and the
  studio's LICENSE-PLATES.md, LICENSE-RUNTIME.md and PLATES-CC-BY-4.0.txt, and
  the owner's reserved plates never ship as bytes (the catalog refuses to write
  any file whose sha256 is a plate's).
- The catalog goes to GitHub Pages as a workflow artifact, not as committed
  files: CLAUDE.md keeps images and geometry out of git, and an artifact serves
  the same site. Only history.csv and the pin are committed by the workflow.
- The workflow needs the LIBRARY_TOKEN secret (read on the private library and
  explorer) and Pages on with "GitHub Actions" as its source; run #1
  (2026-10-03, by hand) stopped at the token with its message. The cloud
  Routine stays on until the workflow's first green run, so no day goes
  without a row; then the Routine is disabled.
- The Pages URL is recorded here, not in the library's pulse plan: this
  repository never edits the library.
- 2026-10-03, the subject URL pattern `/subject/<id>/` (variants
  `/subject/<id>/<variant>/`) is recorded here for the game's inspect, not in
  the library's pulse plan, which this repository never edits.
- 2026-10-03, the commons' step 5: built, with the priority line gated on the
  library's own measure (`tools/commission-cost.py`), because the plan says
  step 5 waits while that measure fires and the dispatch asked for it now.
  The link is empty, so nothing shows yet.

## Licence

The catalog and the plates are CC BY 4.0, the code MIT: see LICENSE.md.
- 2026-10-03 23:57 UTC, workflow run #4 green (70 min, library bdc29a71, 90 subjects, 70 downloads): the cloud Routine "asset-pulse daily run" is disabled; the workflow is the daily run from here.

## Customer catalog redesign

`tools/catalog.py` builds the customer catalog; `tools/catalog_ui.py` and
`tools/catalog-assets/` provide its presentation. `tools/site.py` remains the
private owner scorecard. The customer UI follows the approved
[prototype](https://codestiff.github.io/scratchpad/mockups/asset-catalog-v1/),
using library metadata, actual close-up renders and baked GLB previews. None
of the prototype's sample specifications or vector artwork are asset data.
Variants sit under their parent asset, retain their stable subject URLs, and
count individually in the deployment guard. Search covers readable names,
generator/build IDs, class, taxon, use and other displayed library facts.
Filters and sorting are carried in the URL; session storage remembers catalog
position and expanded variants. Contact details and photos are never stored
in browser storage. Still renders and committed dimensions describe the
parent default; a variant's 3D preview is its own baked model.

### Connect the request desk

The Pages workflow reads these **repository Actions variables**. The same
names are environment variables for local builds and `tools/publish.sh`:

- `CATALOG_INTAKE_URL`: the deployed HTTPS endpoint ending in `/v1/requests`.
  This overrides `EDGE_ZONE`; without it, `EDGE_ZONE` fills the library's
  documented `https://requests.<zone>/v1/requests` URL. For workers.dev,
  supply the actual URL explicitly, including the account subdomain.
- `TURNSTILE_SITEKEY`: the public production widget key. Configure that widget
  to allow `codestiff.github.io` and any catalog custom hostname. The matching
  **secret** remains in the intake Worker as `TURNSTILE_SECRET`, never here.
- `ITCH_URL`: optional finer-build offer; without it, the free 1080 build is
  the offer and finer builds are described as coming soon.

Sending is enabled only with a usable HTTPS endpoint and a non-test widget
key. Missing settings, local URLs and unresolved placeholders produce a visible
unavailable desk; visitors can prepare a request but cannot submit it. The
frontend waits for a real Turnstile token, handles widget errors/expiry, and
requires a fresh check after a failed submission. Inputs and the selected photo
remain in the current page after failure. A successful HTTP 201 must carry an
ID before the UI shows a receipt; it displays and can copy that exact ID.

The multipart fields match the intake contract: `photo`, `text`, `licence`,
required `contact`, required `consent=yes`, optional `contributed_by` (80
characters, no `@`), and `cf-turnstile-response`. License and consent are
explicit choices. Photo ownership is also confirmed in the UI. JPEG/PNG/WebP
photos are limited to 10 MiB; remove GPS metadata before sending. The Worker
is authoritative for image content, metadata and moderation checks. Its `say`
and `recovery` text is displayed safely; otherwise the UI explains the failure
without exposing reason codes. Receipts do not promise production approval,
customer tracking or automatic notification.

On 2026-10-11, read-only inspection found the live form still used the literal
workers.dev `<sub>` placeholder and had no Turnstile site key. The documented
`https://edge-requests.johnnyillinois.workers.dev/v1/requests` answered a CORS
OPTIONS check with HTTP 204 and allowed POST. That confirms reachability and
CORS, **not** matching Turnstile configuration or successful intake. This
session could not read Actions variables (GitHub returned 403). Set/verify the
public variables and matching Worker/widget configuration before enabling
customer submissions. No production photos were submitted during validation.

### Catalog discovery and presentation refresh

The catalog lists the pinned library's committed subject cards and tagged
package targets, including builds a budgeted bake has not reached. These pages
use available library renders and committed facts; a download is offered only
after the existing completeness and licensing checks pass. `stone` subjects
appear under Rocks. Detail-level controls load each actual baked GLB; they do
not resize a single illustration to simulate different levels.

For a presentation-only rebuild, run the **pulse** workflow with
`refresh_catalog=true`. It retains the committed library and explorer pins,
requires matching render/bake caches, and skips rendering, baking, pin updates
and history commits. Set `publish=false` first to review the `github-pages`
artifact without deploying; publish the reviewed revision with `publish=true`.
Only the customer catalog is uploaded. The private scorecard stays private.
If matching caches are absent, the refresh fails and requires a normal pulse.
The deployment guard checks both total entries and available downloads, so
adding preview-only entries cannot hide a decrease in downloadable packages.

### Validate locally

The viewer module and its upstream license are copied into the static site at
build time, checked against the SHA256 pins in `catalog.json`. Browsers load
the renderer from the same host as the catalog. A failed fetch or checksum
stops the build. Viewer failures retain the library renders, show retry controls
and offer a direct GLB link. Download pages also expose an ordinary ZIP link for
browsers that do not handle the download attribute.
The catalog opens with all assets and their available renders, including builds
still in preparation. Select "Downloadable assets only" to show complete packages;
`?available=1` preserves that filter in links and on return from a detail page.

    python3 -m pip install -r tools/catalog-test-requirements.txt
    python3 -m playwright install chromium
    python3 -m unittest discover -s tools -p 'test_catalog.py'
    python3 tools/test_catalog_guard.py
    python3 tools/test_catalog_browser.py
    python3 tools/test_catalog_viewer.py
    # With Playwright WebKit and its OS dependencies installed:
    CATALOG_BROWSER=webkit python3 tools/test_catalog_viewer.py
    node --check tools/catalog-assets/catalog.js

The packaging tests require Pillow; browser tests additionally require
Playwright and Chromium. The pinned test dependencies above are also used by
`.github/workflows/catalog-tests.yml` on relevant pull requests; that workflow
uses isolated fixtures and cannot deploy. Browser tests serve isolated bakes
locally and intercept every external request, including Turnstile and intake.
They cover discovery, variant navigation, filter/scroll restoration, inline
validation, upload limits, safe review rendering, multipart fields, failures,
real receipt IDs, progress, duplicate prevention and layouts from 320 to 1280
pixels. Generated fixture files stay in temporary directories; no photos,
geometry or library copies belong in git.

### Completing terminal impostors

`tools/bake.sh` now runs `tools/catalog_impostors.py` after the registry bake.
The pinned library exports regular mesh rungs but can omit its separately
specified terminal impostor. The completion step asks the library's own
`AgImpostorRung` and `AgBaker` APIs to generate and verify that end; it does not
change geometry, quality settings, or generator source.

Repair requires every committed mesh rung and its GLB, an existing atlas, and
an exported end whose index matches the committed ladder. Missing or conflicting
ladder declarations remain blocked. Existing mesh files are preserved. Failed
exports leave that entry unchanged and are named in the gitignored
`library/build/impostor-repair/report.json`. Repeated runs skip completed ends.
Both library and explorer checkouts must match their lock files and be clean.
Outputs baked at older pins must not be relabeled as current builds.

To complete an existing bake at the current pins:

    python3 tools/catalog_impostors.py
    python3 -m unittest discover -s tools -p 'test_catalog_impostors.py'
