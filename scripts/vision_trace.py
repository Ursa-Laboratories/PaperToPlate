#!/usr/bin/env python3
"""Record timestamped local detector observations alongside an existing video."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import time

import httpx


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--session',type=Path,required=True)
    args=p.parse_args()
    metadata=json.loads((args.session/'session.json').read_text())
    started=datetime.fromisoformat(metadata['started_at']).timestamp()
    deadline=started+metadata.get('recording_limit_seconds',1200)
    path=args.session/'detector-observations.jsonl'
    with httpx.Client(timeout=3,trust_env=False) as client,path.open('a') as output:
        output.write(json.dumps({'event':'trace_started','at':time.time(),'video_start_at':started,'alignment':'Approximate local wall clock. Earlier footage has no synthesized predictions.'})+'\n')
        output.flush()
        while time.time()<deadline:
            now=time.time()
            try:
                value=client.get('http://127.0.0.1:8793/status').json()
                row={k:value.get(k) for k in ('state','model','session_id','frame_id','captured_at','result_age_s','inference_ms','counts','detections')}
                row.update(observed_at=now,video_offset_seconds=now-started,reviewed=False)
            except Exception as exc:
                row={'observed_at':now,'video_offset_seconds':now-started,'state':'unavailable','error':type(exc).__name__,'reviewed':False}
            output.write(json.dumps(row,allow_nan=False)+'\n');output.flush()
            time.sleep(.5)


if __name__=='__main__':main()
