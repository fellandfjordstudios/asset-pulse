#!/bin/bash
# Provisions what a run needs: headless Godot, a virtual display, Pillow, then
# the pinned library. Idempotent. The Godot install is transect's, unchanged.
set -euo pipefail
GODOT_VERSION="4.5-stable"
GODOT_BIN_NAME="Godot_v${GODOT_VERSION}_linux.x86_64"
GODOT_URL="https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}/${GODOT_BIN_NAME}.zip"
INSTALL_DIR="${HOME}/.local/bin"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if ! command -v godot >/dev/null 2>&1 && [ ! -x "${INSTALL_DIR}/godot" ] && [ "$(uname -s)" = "Linux" ]; then
  echo "installing godot ${GODOT_VERSION} -> ${INSTALL_DIR}/godot"
  mkdir -p "${INSTALL_DIR}"; tmp="$(mktemp -d)"
  curl -fsSL -o "${tmp}/godot.zip" "${GODOT_URL}"
  unzip -o -q "${tmp}/godot.zip" -d "${tmp}"
  install -m 0755 "${tmp}/${GODOT_BIN_NAME}" "${INSTALL_DIR}/godot"; rm -rf "${tmp}"
fi
case ":${PATH}:" in *":${INSTALL_DIR}:"*) ;; *)
  export PATH="${INSTALL_DIR}:${PATH}"
  [ -n "${CLAUDE_ENV_FILE:-}" ] && echo "export PATH=\"${INSTALL_DIR}:\${PATH}\"" >> "${CLAUDE_ENV_FILE}" ;;
esac
command -v xvfb-run >/dev/null 2>&1 || { command -v apt-get >/dev/null 2>&1 && (apt-get install -y -q xvfb >/dev/null 2>&1 || sudo apt-get install -y -q xvfb >/dev/null 2>&1 || echo "xvfb: install it (the sheet needs a virtual display)"); }
python3 -c "import PIL" 2>/dev/null || pip install -q pillow 2>/dev/null || pip3 install -q pillow 2>/dev/null || echo "pillow: install it (the sheet needs it)"
cd "$ROOT" && tools/sync-library.sh
