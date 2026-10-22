#!/usr/bin/env python3
"""Start localhost demo services without touching robot control or protocols."""
import argparse
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def read_json(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return json.load(response)
    except Exception:
        return None


def start(name, args, log):
    if subprocess.run(['tmux', 'has-session', '-t', name], capture_output=True).returncode == 0:
        raise SystemExit(f'{name} exists but did not answer its health check. Inspect tmux attach -t {name}; this script will not replace another process.')
    command = shlex.join([str(x) for x in args])+' > '+shlex.quote(str(log))+' 2>&1'
    subprocess.run(['tmux', 'new-session', '-d', '-s', name, '-c', str(ROOT), command], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cubos-root', type=Path, default=ROOT.parents[1]/'CubOS')
    args = parser.parse_args()
    if not shutil.which('tmux') or not shutil.which('ffmpeg'):
        raise SystemExit('Install tmux and ffmpeg before starting the demo.')
    if not (ROOT/'.venv-vision/bin/python').is_file():
        raise SystemExit('Install the vision environment: see docs/vision/README.md.')
    if not (ROOT/'frontend/dist/index.html').is_file():
        raise SystemExit('Build the frontend first: cd frontend && npm ci --legacy-peer-deps && npm run build')
    (ROOT/'artifacts').mkdir(exist_ok=True)
    camera = read_json('http://127.0.0.1:8090/status')
    if not camera:
        tool = args.cubos_root/'tools/livestream_camera.py'
        python = args.cubos_root/'.venv/bin/python'
        if not tool.is_file() or not python.is_file():
            raise SystemExit('Supply --cubos-root pointing to a CubOS checkout with the camera bridge and its environment. See docs/vision/README.md.')
        listing = subprocess.run([str(python), str(tool), '--list-devices'], capture_output=True, text=True, check=True).stdout
        match = re.search(r'^\[(\d+)\] MX Brio\s*$', listing, re.MULTILINE)
        if not match:
            raise SystemExit('MX Brio was not found. Connect it and grant camera access to this terminal.')
        start('paper-to-plate-camera', [python, tool, '--device', match[1], '--fps', '30', '--width', '1920', '--height', '1080', '--host', '127.0.0.1', '--port', '8090'], ROOT/'artifacts/camera.log')
    elif camera.get('state') in ('stale', 'no_frames'):
        print('Existing camera bridge reports stale/no frames; inspect it before trusting results.')
    if not read_json('http://127.0.0.1:8793/status'):
        start('paper-to-plate-vision', [ROOT/'start-vision.sh'], ROOT/'artifacts/vision-worker.log')
    if not read_json('http://127.0.0.1:8785/api/status'):
        start('paper-to-plate', [ROOT/'start.sh'], ROOT/'artifacts/server.log')
    print('Open http://127.0.0.1:8785/?vision=1. Watch the on-screen camera/model health until ready.')
    print('Logs: artifacts/camera.log, artifacts/vision-worker.log, artifacts/server.log')


if __name__ == '__main__':
    main()
