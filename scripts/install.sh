#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
RUNTIME_ROOT="$HOME/.cloud-cua/runtime-venv"
PYTHON="$RUNTIME_ROOT/bin/python"

if [ ! -x "$PYTHON" ]; then
  python3 -m venv "$RUNTIME_ROOT"
fi

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install "$PROJECT_ROOT[h]"
"$PYTHON" -I -m cloud_cua.cli install-mcp --python-executable "$PYTHON"
"$PYTHON" -I -m cloud_cua.cli doctor

printf '%s\n' "Cloud CUA is installed for this user. Restart Codex so it reloads MCP configuration."
