#!/bin/bash
# PUBLISH ONE RUN (the plan's step 3): the private pulse behind Access, the
# public catalog on the explorer's existing Pages hostname, the catalog's
# objects to the `catalog` R2 bucket by hash.
#
#   tools/publish.sh out/<date>
#
# Reads, from the environment (never a file in this repository):
#   CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID   Pages, R2 and Access scope
#   EDGE_ZONE             the owner's domain: the intake's public URL and pulse.<zone>
#   CATALOG_PUBLIC_BASE   the catalog bucket's public URL, ending in /
#   ITCH_URL              optional: the finer builds' itch page, which does not
#                         exist until stage 1 (the pages read "free at 1080;
#                         finer builds soon" without it)
# Until every required one is set it stops before deploying anything, names what is
# missing and exits 3: those values are the owner's to give (2026-10-03), and
# this step never works around them. The catalog's hostname is the one the
# explorer's Pages config names (explorer/wrangler.toml, `# hostname:`).
#
# With them, it refuses before uploading when no Access application covers
# pulse.<zone> (the pulse is private or it is not published: the plan's step 3
# ablation) or when the catalog's request form still points at a local URL.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="${1:?usage: tools/publish.sh out/<date>}"
RUN="$(cd "$RUN" && pwd)"
say() { echo "publish: $*"; }
missing=()
for v in CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID EDGE_ZONE CATALOG_PUBLIC_BASE; do
  [ -n "${!v:-}" ] || missing+=("$v")
done
if [ "${#missing[@]}" -gt 0 ]; then
  say "stopped before deploying: the environment has no ${missing[*]} -- nothing published; both sites are built in $RUN (site/, catalog/)"
  exit 3
fi
CFG="$ROOT/catalog.json"
val() { python3 -c "import json,sys;d=json.load(open(sys.argv[1]))
for k in sys.argv[2].split('.'): d=d[k]
print(d)" "$CFG" "$1"; }
BUCKET="$(val bucket)"; PULSE_PROJECT="$(val pages.pulse)"; CATALOG_PROJECT="$(val pages.catalog)"
WRANGLER="${WRANGLER:-npx --yes wrangler@3}"
API="https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID"
auth=(-H "Authorization: Bearer $CLOUDFLARE_API_TOKEN")
PULSE_HOSTNAME="pulse.$EDGE_ZONE"
CATALOG_HOSTNAME="$(sed -n 's/^# hostname: //p' "$ROOT/explorer/wrangler.toml" 2>/dev/null | sed "s/<zone>/$EDGE_ZONE/")"
[ -n "$CATALOG_HOSTNAME" ] || { say "REFUSED: no '# hostname:' in explorer/wrangler.toml (tools/bake.sh checks out the explorer pin)"; exit 1; }

# 1. THE PULSE IS PRIVATE OR IT IS NOT PUBLISHED.
apps="$(curl -fsS "${auth[@]}" "$API/access/apps?per_page=100")" || { say "REFUSED: cannot read the Access applications"; exit 1; }
python3 - "$PULSE_HOSTNAME" "$apps" <<'PY' || { say "REFUSED: no Access application covers $PULSE_HOSTNAME -- the pulse would be public"; exit 1; }
import json, sys
host, apps = sys.argv[1], json.loads(sys.argv[2]).get("result", [])
doms = [d for a in apps for d in ([a.get("domain", "")] + [s.get("uri", "") for s in a.get("destinations", []) or []])]
sys.exit(0 if any(d.split("/")[0] in (host, "*." + host.split(".", 1)[-1]) for d in doms) else 1)
PY

# 2. THE CATALOG, rebuilt against the bucket, the public intake and the itch page.
python3 "$ROOT/tools/catalog.py" "$RUN" || { say "REFUSED: the catalog did not build"; exit 1; }
python3 - "$RUN/catalog/objects.json" <<'PY' || { say "REFUSED: the catalog's request form points at a local URL"; exit 1; }
import json, sys
edge = json.load(open(sys.argv[1]))["edge"]
# An unconfigured request desk is explicitly unavailable, never a broken
# customer form. Enabled desks must pass the generator's URL and key checks.
u = edge.get("intake", "")
sys.exit(1 if edge.get("ready") and (not u.startswith("https://") or "<" in u or "localhost" in u or "127.0.0.1" in u) else 0)
PY

# 3. THE OBJECTS, by hash: a name is its content, so a put is idempotent.
n=0
for f in "$RUN"/catalog/objects/*; do
  $WRANGLER r2 object put "$BUCKET/$(basename "$f")" --file "$f" --remote >/dev/null || { say "upload failed: $(basename "$f")"; exit 1; }
  n=$((n+1))
done
say "$n object(s) in the $BUCKET bucket"

# 4. THE TWO SITES. The catalog's pages only (its objects are in the bucket).
STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
( cd "$RUN/catalog" && tar --exclude=./objects --exclude=./objects.json -cf - . ) | ( cd "$STAGE" && tar -xf - )
$WRANGLER pages deploy "$STAGE" --project-name "$CATALOG_PROJECT" --branch main --commit-dirty=true || { say "the catalog deploy failed"; exit 1; }
$WRANGLER pages deploy "$RUN/site" --project-name "$PULSE_PROJECT" --branch main --commit-dirty=true || { say "the pulse deploy failed"; exit 1; }
# The pulse's hostname on its project; the catalog's is the project's own
# pages.dev name and needs none (a custom one, if the config ever names it, is
# attached the same way). An existing domain answers 409.
for pair in "$PULSE_PROJECT=$PULSE_HOSTNAME" "$CATALOG_PROJECT=$CATALOG_HOSTNAME"; do
  proj="${pair%%=*}"; host="${pair#*=}"
  case "$host" in *.pages.dev) continue ;; esac
  code="$(curl -s -o /dev/null -w '%{http_code}' "${auth[@]}" -H 'Content-Type: application/json' \
    -X POST "$API/pages/projects/$proj/domains" --data "{\"name\":\"$host\"}")"
  case "$code" in 200|409) say "$host -> $proj" ;; *) say "could not point $host at $proj (HTTP $code)"; exit 1 ;; esac
done

# 5. THE GATE, from outside: the pulse asks for a login.
code="$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "https://$PULSE_HOSTNAME/")"
case "$code" in
  30[0-9]*cloudflareaccess.com*) say "the pulse at https://$PULSE_HOSTNAME/ asks for a login" ;;
  *) say "WARNING: https://$PULSE_HOSTNAME/ answered '$code' without Access in front"; exit 1 ;;
esac
say "published: the pulse at https://$PULSE_HOSTNAME/ (Access) and the catalog at https://$CATALOG_HOSTNAME/"
