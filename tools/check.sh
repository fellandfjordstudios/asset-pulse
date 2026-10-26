#!/usr/bin/env bash
# Isolated local checks: no run, pin bump, publication or backlog work.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
[ "$(git config --get core.hooksPath)" = "$PWD/.githooks" ] || { echo 'check: run tools/setup.sh first' >&2; exit 1; }
[ "$(git var GIT_AUTHOR_IDENT | cut -d '>' -f 1)" = 'Fell & Fjord <fellandfjord@gmail.com' ] || { echo 'check: studio author required; run setup and remove local identity overrides' >&2; exit 1; }
case "$(godot --headless --version)" in
  4.7.2.stable.*) ;;
  *) echo 'check: Godot 4.7.2 required; run tools/setup.sh' >&2; exit 1 ;;
esac
tools/sync-library.sh --verify
python3 -m unittest discover -s tools -p 'test_setup.py'
python3 -m unittest discover -s tools -p 'test_catalog.py'
python3 tools/test_catalog_guard.py
python3 tools/test_store_prune.py
python3 tools/test_bake_ledger.py
python3 -m unittest discover -s tools -p 'test_catalog_impostors.py'
node --check tools/catalog-assets/catalog.js
bash -n tools/setup.sh tools/check.sh daily.sh tools/publish.sh .githooks/pre-push .githooks/commit-msg
