#!/bin/bash
# One-time setup: a Python environment for the layer + card scripts (and, optionally, Playwright to record the card to video).
# The local models need Python 3.10-3.13 (onnxruntime has no wheels for newer ones yet); uv is used to fetch one if needed.
# usage: bash setup.sh [--record]
set -euo pipefail
cd "$(dirname "$0")/.."
PKGS=(numpy scipy pillow opencv-python-headless onnxruntime "rembg[cpu]" huggingface_hub)
ok_py() { "$1" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)' 2>/dev/null; }
if [ -x .venv/bin/python ] && ! ok_py .venv/bin/python; then echo "existing .venv has an unsupported Python: rebuilding it"; rm -rf .venv; fi
if [ ! -x .venv/bin/python ]; then
  PY=""
  for c in python3.13 python3.12 python3.11 python3.10 python3; do command -v "$c" >/dev/null && ok_py "$(command -v "$c")" && { PY=$(command -v "$c"); break; }; done
  if [ -n "$PY" ]; then "$PY" -m venv .venv
  elif command -v uv >/dev/null; then uv venv --python 3.12 .venv
  else echo "Need Python 3.10-3.13 (or uv: https://docs.astral.sh/uv/). Install one and run this again."; exit 1; fi
fi
if command -v uv >/dev/null; then uv pip install --python .venv/bin/python "${PKGS[@]}"
else .venv/bin/python -m pip install --upgrade pip && .venv/bin/python -m pip install "${PKGS[@]}"; fi
.venv/bin/python -c "import numpy, scipy, PIL, cv2, onnxruntime, rembg, huggingface_hub" && echo "python ready: $(pwd)/.venv/bin/python ($(.venv/bin/python --version))"
if [ "${1:-}" = "--record" ]; then
  command -v node >/dev/null || { echo "recording needs Node.js 18+ (https://nodejs.org)"; exit 1; }
  command -v ffmpeg >/dev/null || echo "recording also needs ffmpeg (brew install ffmpeg / apt install ffmpeg)"
  [ -f package.json ] || echo '{"private": true}' > package.json
  npm install --silent playwright@1.49.1 && npx playwright install chromium
  echo "recorder ready"
fi
