#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -x .venv-vision/bin/python ]; then
  echo 'Install the vision environment first; see docs/vision/README.md.'
  exit 1
fi
export PYTHONUNBUFFERED=1
exec .venv-vision/bin/python -m paper_to_plate.vision_service
