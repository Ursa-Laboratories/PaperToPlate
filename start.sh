#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -x .venv/bin/python ]; then
  echo "Run ./setup.sh first to install this application's environment."
  exit 1
fi
if [ ! -f frontend/dist/index.html ]; then
  echo "Build the interface first: cd frontend && npm ci --legacy-peer-deps && npm run build"
  exit 1
fi
exec .venv/bin/python -m paper_to_plate
