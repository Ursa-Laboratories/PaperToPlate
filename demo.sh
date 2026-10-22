#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec .venv/bin/python scripts/start_vision_demo.py "$@"
