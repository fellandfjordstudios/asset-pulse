#!/bin/bash
# Every host uses the same bootstrap.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INSTALL_DIR="${HOME}/.local/bin"
bash "$ROOT/tools/setup.sh"
case ":${PATH}:" in *":${INSTALL_DIR}:"*) ;; *)
  export PATH="${INSTALL_DIR}:${PATH}"
  [ -n "${CLAUDE_ENV_FILE:-}" ] && echo "export PATH=\"${INSTALL_DIR}:\${PATH}\"" >> "${CLAUDE_ENV_FILE}" ;;
esac
