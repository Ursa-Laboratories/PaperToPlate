"""Compare original and adapted liquid detection on frozen recording annotations."""
from __future__ import annotations
import argparse
import hashlib
import json
import time
from pathlib import Path
from PIL import Image
from paper_to_plate.vision_evaluation import evaluate, validate_partition
from paper_to_plate.vision_models import CameraTipDetector, YoloDetector
from paper_to_plate.vision_service import clean_detections


def run(manifest, models, out):
    doc=json.loads(manifest.read_text());frames=doc['frames'];validate_partition(frames,min_gap_s=1)
    out.mkdir(parents=True,exist_ok=False)
    baseline=CameraTipDetector(models,device='mps')
    baseline.liquid=YoloDetector(models/'yolov8n-tip-liquid-source.pt','mps',imgsz=640)
    adapted=CameraTipDetector(models,device='mps')
    if not (models/'local-liquid.pt').is_file():raise ValueError('A trained local-liquid checkpoint is required')
    predictions={'baseline':{},'adapted':{}};latency={key:[] for key in predictions}
    for frame in frames:
        if hashlib.sha256(Path(frame['image_path']).read_bytes()).hexdigest()!=frame['sha256']:
            raise ValueError(f"Frame changed: {frame['id']}")
        image=Image.open(frame['image_path']).convert('RGB')
        for key,detector in [('baseline',baseline),('adapted',adapted)]:
            start=time.monotonic();items=clean_detections(detector.predict(image),*image.size)
            predictions[key][frame['id']]=items;latency[key].append((time.monotonic()-start)*1000)
    report={'source_recording':doc['recording'],'label_source':doc['labels'],'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'model_sha256':hashlib.sha256((models/'local-liquid.pt').read_bytes()).hexdigest(),'confidence_threshold':.25,'iou_threshold':.5,'scope':'Within-recording temporal holdout, not an independent run','volume_calibrated':False,'results':{}}
    for key in predictions:
        report['results'][key]={}
        for split in ('train','validation','test'):
            ids={f['id'] for f in frames if f['split']==split}
            report['results'][key][split]=evaluate(frames,{i:v for i,v in predictions[key].items() if i in ids},split=split,label='liquid',confidence=.25,iou_threshold=.5)
    report['limitations']=doc['limitations']+['Labels are assistant-reviewed and should be checked by a lab operator.','No threshold was selected from the test window.']
    (out/'predictions.json').write_text(json.dumps(predictions,indent=2))
    (out/'evaluation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({key:report['results'][key]['test'] for key in report['results']},indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--models',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();run(a.manifest,a.models,a.out)
