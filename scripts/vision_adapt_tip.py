"""Few-shot local tip adaptation from explicitly reviewed camera boxes.

Input is an annotation manifest. Cropped variants stay in training and are not
independent samples. A later live frame is a smoke test, not an accuracy eval.
"""
import argparse
import json
import math
import random
from pathlib import Path

from PIL import Image
from ultralytics import YOLO


def prepare(manifest, out):
    records = json.loads(Path(manifest).read_text())
    if out.exists():
        raise ValueError('Choose a new output directory to preserve prior training data.')
    folder = out/'train'
    (folder/'images').mkdir(parents=True)
    (folder/'labels').mkdir()
    rng = random.Random(20261022)
    index = 0
    for record in records:
        im = Image.open(record.get('image') or record['image_path']).convert('RGB')
        raw_boxes = record.get('boxes', [])
        boxes = [item['box'] if isinstance(item, dict) else item for item in raw_boxes if not isinstance(item, dict) or item.get('label') == 'tip']
        for box in boxes:
            if len(box) != 4 or not all(math.isfinite(v) for v in box) or not (0 <= box[0] < box[2] <= im.width and 0 <= box[1] < box[3] <= im.height):
                raise ValueError('A reviewed tip box is invalid or outside its frame.')
        for variant in range(24):
            if boxes:
                x1,y1,x2,y2=rng.choice(boxes)
                side = rng.choice([320,448,640,800])
                cx=(x1+x2)/2 + rng.uniform(-side*.25,side*.25)
                cy=(y1+y2)/2 + rng.uniform(-side*.20,side*.20)
                left=max(0,min(im.width-side,int(cx-side/2)))
                top=max(0,min(im.height-side,int(cy-side/2)))
                right=min(im.width,left+side); bottom=min(im.height,top+side)
            else:
                left,top,right,bottom = record.get('background_crop', [0,0,im.width,im.height])
            crop=im.crop((left,top,right,bottom))
            name=f'local-{index:04d}'
            crop.save(folder/'images'/f'{name}.jpg',quality=95)
            labels=[]
            for x1,y1,x2,y2 in boxes:
                if x1>=left and x2<=right and y1>=top and y2<=bottom:
                    labels.append(f'0 {((x1+x2)/2-left)/crop.width} {((y1+y2)/2-top)/crop.height} {(x2-x1)/crop.width} {(y2-y1)/crop.height}')
            (folder/'labels'/f'{name}.txt').write_text('\n'.join(labels)+'\n')
            index+=1
    # Train and validation are the same calibration images intentionally;
    # no score from this manifest is claimed as independent validation.
    (out/'data.yaml').write_text(f'path: {out.resolve()}\ntrain: train/images\nval: train/images\nnames: [tip]\nnc: 1\n')
    (out/'provenance.json').write_text(json.dumps({'records':records,'derived_training_images':index,'independent_target_test':False,'purpose':'few-shot calibration only','label_source':'user-confirmed presence; assistant visual box review'},indent=2))
    return out/'data.yaml'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--epochs',type=int,default=30)
    p.add_argument('--device',default='mps')
    args=p.parse_args()
    data=prepare(args.manifest,args.out)
    model=YOLO('yolov8n.pt')
    model.train(data=str(data),epochs=args.epochs,imgsz=512,batch=8,device=args.device,
                project=str(args.out/'runs'),name='local-tip',workers=0,amp=False,
                optimizer='AdamW',lr0=.001,patience=0,val=False,plots=False,
                mosaic=.5,close_mosaic=5,scale=.4,translate=.2,fliplr=.5,
                seed=20261022,verbose=False)
    # Select final weights; the calibration set is not used as a model-selection test.
    print(json.dumps({'weights':str(args.out/'runs/local-tip/weights/last.pt'),'independent_accuracy_established':False}))


if __name__=='__main__':main()
