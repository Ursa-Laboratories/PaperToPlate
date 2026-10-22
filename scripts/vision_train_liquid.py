"""Train a local liquid-region model from reviewed original recording frames.

Cropped variants retain their source frame's split. Adjacent test frames do not
constitute independent experiments. Commanded volumes are never used as labels.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from pathlib import Path

from PIL import Image
from paper_to_plate.vision_evaluation import validate_partition


def prepare(manifest: Path, output: Path):
    document=json.loads(manifest.read_text());frames=document['frames']
    validate_partition(frames,min_gap_s=1)
    if output.exists():raise ValueError('Use a new output directory; existing datasets are preserved.')
    rng=random.Random(20261022)
    counts={};provenance=[]
    for split in ('train','validation','test'):
        (output/split/'images').mkdir(parents=True);(output/split/'labels').mkdir()
    for frame in frames:
        split=frame['split']
        if split=='excluded' or frame['visibility']!='clear':continue
        source=Path(frame['image_path'])
        if hashlib.sha256(source.read_bytes()).hexdigest()!=frame['sha256']:raise ValueError(f"Frame changed: {frame['id']}")
        image=Image.open(source).convert('RGB')
        a,b,c,d=frame['training_roi']
        if not (0<=a<c<=image.width and 0<=b<d<=image.height):raise ValueError('Invalid training ROI')
        boxes=[x['box'] for x in frame['boxes'] if x['label']=='liquid']
        variants=24 if split=='train' else 1
        for variant in range(variants):
            # Vary context without clipping or relabeling the observed liquid.
            pad=rng.randint(0,28) if variant else 0
            left=max(0,int(a-pad));top=max(0,int(b-pad));right=min(image.width,int(c+pad));bottom=min(image.height,int(d+pad))
            crop=image.crop((left,top,right,bottom));name=f"{frame['id']}-{variant:02d}"
            crop.save(output/split/'images'/f'{name}.jpg',quality=95)
            labels=[]
            for x1,y1,x2,y2 in boxes:
                if not (left<=x1<x2<=right and top<=y1<y2<=bottom):raise ValueError('Liquid annotation would be cropped')
                labels.append(f'0 {((x1+x2)/2-left)/crop.width:.8f} {((y1+y2)/2-top)/crop.height:.8f} {(x2-x1)/crop.width:.8f} {(y2-y1)/crop.height:.8f}')
            (output/split/'labels'/f'{name}.txt').write_text('\n'.join(labels)+'\n')
            provenance.append({'file':name,'source_id':frame['id'],'split':split,'crop':[left,top,right,bottom]})
            counts[split]=counts.get(split,0)+1
        if split=='train':
            # Colored vials and deck backgrounds are not liquid *inside a tip*.
            for index,rect in enumerate(([490,540,780,750],[700,530,1000,750],[1300,500,1700,900])):
                left,top,right,bottom=rect
                # These reviewed background rectangles are only used for the
                # pre-aspiration/no-tip training frames, never a loaded frame.
                if boxes:continue
                name=f"{frame['id']}-background-{index}"
                image.crop(rect).save(output/split/'images'/f'{name}.jpg',quality=95)
                (output/split/'labels'/f'{name}.txt').write_text('')
                provenance.append({'file':name,'source_id':frame['id'],'split':split,'crop':rect,'purpose':'colored background hard negative'})
                counts[split]=counts.get(split,0)+1
    (output/'data.yaml').write_text(f'path: {output.resolve()}\ntrain: train/images\nval: validation/images\ntest: test/images\nnames: [liquid]\nnc: 1\n')
    (output/'provenance.json').write_text(json.dumps({'manifest':str(manifest.resolve()),'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'counts':counts,'derived_examples':provenance,'independent_experiment_count':1},indent=2))
    return output/'data.yaml',counts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--epochs',type=int,default=35)
    parser.add_argument('--device',default='mps')
    args=parser.parse_args();data,counts=prepare(args.manifest,args.out)
    from ultralytics import YOLO
    model=YOLO('yolov8n.pt')
    model.train(data=str(data),epochs=args.epochs,imgsz=320,batch=8,device=args.device,
                project=str(args.out/'runs'),name='liquid',workers=0,amp=False,
                optimizer='AdamW',lr0=.001,patience=0,val=False,plots=False,
                mosaic=.3,close_mosaic=5,scale=.3,translate=.15,fliplr=.5,
                hsv_h=.005,hsv_s=.2,hsv_v=.2,seed=20261022,verbose=False)
    weights=args.out/'runs/liquid/weights/last.pt'
    (args.out/'training-receipt.json').write_text(json.dumps({'weights':str(weights.resolve()),'weights_sha256':hashlib.sha256(weights.read_bytes()).hexdigest(),'epochs':args.epochs,'imgsz':320,'counts':counts,'selection':'Fixed-epoch final checkpoint; test partition not used for training or selection','label_source':'assistant visual review of original frames','volume_calibrated':False},indent=2))
    print(json.dumps({'weights':str(weights),'counts':counts}))


if __name__=='__main__':main()
