#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
RUNTIME_ROOT="$HOME/.cloud-cua/runtime-venv"
PYTHON="$RUNTIME_ROOT/bin/python"

if [ ! -x "$PYTHON" ]; then
  python3 -m venv "$RUNTIME_ROOT"
fi

"$PYTHON" -m pip install --upgrade pip
WHEEL=$(find "$PROJECT_ROOT/wheel" -maxdepth 1 -name 'cloud_cua-*.whl' -print -quit 2>/dev/null || true)
if [ -n "$WHEEL" ]; then
  "$PYTHON" -m pip install "$WHEEL"
  "$PYTHON" -m pip install 'hai-agents[browser]>=1.0.6'
else
  "$PYTHON" -m pip install "$PROJECT_ROOT[h]"
fi
"$PYTHON" -I -m cloud_cua.cli install-mcp --python-executable "$PYTHON"
"$PYTHON" -I -m cloud_cua.cli doctor

printf '%s\n' "Cloud CUA is installed for this user. Restart Codex so it reloads MCP configuration."
