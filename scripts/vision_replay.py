"""Replay original video through a model and save annotations with timestamps."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import time
import cv2
from PIL import Image
from paper_to_plate.vision_models import CameraTipDetector
from paper_to_plate.vision_service import clean_detections,render


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,required=True);p.add_argument('--models',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--sample-fps',type=int,default=5)
    a=p.parse_args()
    if a.out.exists():raise ValueError('Use a new output directory to preserve existing evidence.')
    a.out.mkdir(parents=True)
    capture=cv2.VideoCapture(str(a.video));fps=capture.get(cv2.CAP_PROP_FPS)
    width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps<=0 or a.sample_fps<=0 or a.sample_fps>fps:raise ValueError('Invalid source/replay frame rate')
    stride=round(fps/a.sample_fps)
    if abs(fps/stride-a.sample_fps)>.01:raise ValueError('Replay rate must divide source FPS exactly')
    detector=CameraTipDetector(a.models,device='mps')
    movie=a.out/'annotated-replay.mp4'
    command=['ffmpeg','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r',str(a.sample_fps),'-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-movflags','+faststart',str(movie)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE)
    index=0;written=0;positive=[];start=time.time()
    try:
        with (a.out/'predictions.jsonl').open('w') as log:
            while True:
                ok,bgr=capture.read()
                if not ok:break
                if index%stride==0:
                    t=index/fps;image=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))
                    before=time.monotonic();detections=clean_detections(detector.predict(image),width,height);elapsed=(time.monotonic()-before)*1000
                    log.write(json.dumps({'source_frame':index,'video_seconds':t,'detections':detections,'inference_ms':elapsed,'reviewed':False})+'\n')
                    if any(d['label']=='liquid' for d in detections):positive.append(t)
                    # render() produces JPEG; decode for the video encoder.
                    import io
                    marked=Image.open(io.BytesIO(render(image,detections,f'RECORDED REPLAY | {t:.1f}s | T=tip, L=visible pink liquid | Volume not measured'))).convert('RGB')
                    process.stdin.write(marked.tobytes());written+=1
                    if written%100==0:print(json.dumps({'frames':written,'at_seconds':round(t,1),'liquid_frames':len(positive)}),flush=True)
                index+=1
    finally:
        capture.release();process.stdin.close();code=process.wait()
    if code:raise RuntimeError(f'Video encoder failed: {code}')
    summary={'source':str(a.video),'source_fps':fps,'replay_fps':a.sample_fps,'frames':written,'liquid_positive_frames':len(positive),'liquid_positive_times':positive,'wall_seconds':round(time.time()-start,2),'volume_calibrated':False,'note':'Full-recording replay includes both training and held-out windows; use evaluation.json for held-out metrics.'}
    (a.out/'replay-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
