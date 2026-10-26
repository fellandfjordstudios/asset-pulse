#!/usr/bin/env bash
# Tool-neutral bootstrap; the library pin supplies studio identity enforcement.
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in
  ""|--hooks-only) ;;
  *) echo 'usage: tools/setup.sh [--hooks-only]' >&2; exit 2 ;;
esac
tools/sync-library.sh
library/tools/studio-identity.sh
git config --local core.hooksPath "$PWD/.githooks"
if [ "${1:-}" = --hooks-only ]; then exit 0; fi

GODOT_VERSION=4.7.2-stable
INSTALL_DIR="$HOME/.local/bin"
export PATH="$INSTALL_DIR:$PATH"
have="$(godot --headless --version 2>/dev/null || true)"
case "$have" in
  4.7.2.stable.*) ;;
  *)
    [ "$(uname -s)" = Linux ] || { echo 'setup: install Godot 4.7.2 on this platform' >&2; exit 1; }
    archive="Godot_v${GODOT_VERSION}_linux.x86_64"
    scratch="$(mktemp -d)"
    trap 'rm -rf "$scratch"' EXIT
    curl -fsSL -o "$scratch/godot.zip" "https://github.com/godotengine/godot/releases/download/$GODOT_VERSION/$archive.zip"
    unzip -q "$scratch/godot.zip" -d "$scratch"
    mkdir -p "$INSTALL_DIR"
    install -m 0755 "$scratch/$archive" "$INSTALL_DIR/godot"
    ;;
esac
case "$(godot --headless --version)" in
  4.7.2.stable.*) ;;
  *) echo 'setup: Godot 4.7.2 is required' >&2; exit 1 ;;
esac
command -v xvfb-run >/dev/null || { echo 'setup: install xvfb for rendering' >&2; exit 1; }
python3 -m pip install -q -r tools/catalog-test-requirements.txt
printf 'setup: studio hooks and Godot 4.7.2 ready; add %s to PATH\n' "$INSTALL_DIR"
