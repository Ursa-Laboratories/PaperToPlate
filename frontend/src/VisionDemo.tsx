import {useEffect, useRef, useState} from 'react';
import {ArrowLeft, CheckCircle, VideoCamera, WarningCircle, X} from '@phosphor-icons/react';

type VisionModel='yolo'|'yolo_source'|'dino';
type ViewMode='live'|'example';
type Box=[number,number,number,number];
type Detection={label:string;confidence:number;box:Box};
type ModelOption={id:string;label:string;available:boolean;detail?:string};
type VisionStatus={
  state?:string; camera?:string; model?:VisionModel; session_id?:string; frame_id?:string|number; captured_at?:string|number;
  frame_age_s?:number; inference_ms?:number; fps?:number; detections?:Detection[];
  counts?:{tip?:number|null;liquid?:number|null}; warning?:string|null; models?:ModelOption[]; training?:unknown;
  recording?:{id?:string;active?:boolean;frames?:number;seconds_remaining?:number};
};
type Example={id:string;label:string};
type Capture={id:string;image_url?:string;image?:string};
type Annotation={label:'tip'|'liquid';box:Box};
type Point={x:number;y:number};

const streamUrl='/api/vision/stream';
const modelOptionsFallback:ModelOption[]=[
  {id:'yolo',label:'YOLO · fast',available:false,detail:'Waiting for model status'},
  {id:'dino',label:'DINO · exploratory',available:false,detail:'Waiting for model status'},
];

function humanState(state?:string){
  if(!state) return 'Connecting to camera';
  return state.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
}

function formatTime(value?:string|number){
  if(value===undefined||value===null||value==='') return '—';
  const numeric=typeof value==='number' ? (value>1e12?value:value*1000) : value;
  const date=new Date(numeric);
  return Number.isNaN(date.getTime())?String(value):date.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});
}

function pointFromEvent(event:React.PointerEvent<HTMLDivElement>,surface:HTMLDivElement):Point{
  const rect=surface.getBoundingClientRect();
  return {x:Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),y:Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))};
}

function boxStyle(box:Box,width:number,height:number){
  return {left:`${box[0]/width*100}%`,top:`${box[1]/height*100}%`,width:`${(box[2]-box[0])/width*100}%`,height:`${(box[3]-box[1])/height*100}%`};
}

export default function VisionDemo(){
  const currentRunId=new URLSearchParams(location.search).get('run')||'';
  const backHref=currentRunId?`/?run=${encodeURIComponent(currentRunId)}`:'/';
  const [status,setStatus]=useState<VisionStatus|null>(null);
  const [error,setError]=useState('');
  const [model,setModel]=useState<VisionModel>('yolo');
  const [modelBusy,setModelBusy]=useState(false);
  const [lastUpdate,setLastUpdate]=useState<number|null>(null);
  const [viewMode,setViewMode]=useState<ViewMode>('live');
  const [examples,setExamples]=useState<Example[]>([]);
  const [exampleId,setExampleId]=useState('');
  const [examplesLoading,setExamplesLoading]=useState(true);
  const [capture,setCapture]=useState<Capture|null>(null);
  const [captureBusy,setCaptureBusy]=useState(false);
  const [recordBusy,setRecordBusy]=useState(false);
  const [annotationBusy,setAnnotationBusy]=useState(false);
  const [annotationMessage,setAnnotationMessage]=useState('');
  const [annotationLabel,setAnnotationLabel]=useState<'tip'|'liquid'>('tip');
  const [annotations,setAnnotations]=useState<Annotation[]>([]);
  const [draftStart,setDraftStart]=useState<Point|null>(null);
  const [draftEnd,setDraftEnd]=useState<Point|null>(null);
  const [imageSize,setImageSize]=useState({width:1,height:1});
  const annotationSurface=useRef<HTMLDivElement>(null);

  useEffect(()=>{
    let cancelled=false;
    const read=async()=>{
      try{
        const response=await fetch('/api/vision/status',{cache:'no-store'});
        if(!response.ok) throw new Error(`Vision status returned ${response.status}.`);
        const next=await response.json() as VisionStatus;
        if(cancelled) return;
        setStatus(next); setLastUpdate(Date.now()); setError('');
        if(next.model==='yolo'||next.model==='yolo_source'||next.model==='dino') setModel(next.model);
      }catch(cause){
        if(!cancelled) setError(cause instanceof Error?cause.message:'Unable to read vision status.');
      }
    };
    read();
    const timer=window.setInterval(read,1000);
    return()=>{cancelled=true;window.clearInterval(timer);};
  },[]);

  useEffect(()=>{
    let cancelled=false;
    const readExamples=async()=>{
      try{
        const response=await fetch('/api/vision/examples',{cache:'no-store'});
        if(!response.ok) return;
        const next=await response.json() as Example[];
        if(!cancelled){setExamples(next);if(next.length) setExampleId(next[0].id);}
      }catch{/* Example mode is optional while the backend is being prepared. */}
      finally{if(!cancelled) setExamplesLoading(false);}
    };
    readExamples();
    return()=>{cancelled=true;};
  },[]);

  const stale=!status || (typeof status.frame_age_s==='number'?status.frame_age_s>3:lastUpdate===null||Date.now()-lastUpdate>3500);
  const stateValue=(status?.state||'').toLowerCase();
  const offline=stateValue.includes('offline')||stateValue.includes('error')||stateValue.includes('failed');
  const cameraReady=stateValue==='live'&&!stale&&!error;
  const stateLabel=error?'Camera unavailable':stale?(status?'Frame stale':'Connecting to camera'):offline?'Camera offline':humanState(status?.state);
  const detections=status?.detections||[];
  const models=status?.models?.length?status.models:modelOptionsFallback;
  const selectedModel=models.find(option=>option.id===model);
  const modelReady=stateValue==='live'&&!!selectedModel?.available&&!modelBusy;
  const captureImageUrl=capture?.image_url||capture?.image||(capture?`/api/vision/capture/${capture.id}/image`:'');

  const selectModel=async(next:VisionModel)=>{
    setModel(next); setModelBusy(true); setError('');
    try{
      const response=await fetch('/api/vision/model',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:next})});
      if(!response.ok) throw new Error(`Could not select ${next.toUpperCase()}.`);
      const body=await response.json().catch(()=>null) as VisionStatus|null;
      if(body) setStatus(current=>({...current,...body}));
    }catch(cause){setError(cause instanceof Error?cause.message:'Could not change the vision model.');}
    finally{setModelBusy(false);}
  };

  const captureFrame=async()=>{
    setCaptureBusy(true); setAnnotationMessage(''); setError('');
    try{
      const response=await fetch('/api/vision/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(currentRunId?{run_id:currentRunId}:{})});
      if(!response.ok) throw new Error('Could not save the current frame.');
      const next=await response.json() as Capture;
      setCapture(next); setAnnotations([]); setViewMode('live');
      setAnnotationMessage('Frame saved. Draw boxes below to correct the detector.');
    }catch(cause){setError(cause instanceof Error?cause.message:'Could not save the current frame.');}
    finally{setCaptureBusy(false);}
  };

  const beginBox=(event:React.PointerEvent<HTMLDivElement>)=>{
    if(!annotationSurface.current) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const point=pointFromEvent(event,annotationSurface.current); setDraftStart(point); setDraftEnd(point);
  };
  const moveBox=(event:React.PointerEvent<HTMLDivElement>)=>{
    if(!draftStart||!annotationSurface.current) return;
    setDraftEnd(pointFromEvent(event,annotationSurface.current));
  };
  const finishBox=()=>{
    if(!draftStart||!draftEnd) return;
    const x1=Math.min(draftStart.x,draftEnd.x),x2=Math.max(draftStart.x,draftEnd.x);
    const y1=Math.min(draftStart.y,draftEnd.y),y2=Math.max(draftStart.y,draftEnd.y);
    setDraftStart(null); setDraftEnd(null);
    if((x2-x1)<.015||(y2-y1)<.015) return;
    setAnnotations(current=>[...current,{label:annotationLabel,box:[x1*imageSize.width,y1*imageSize.height,x2*imageSize.width,y2*imageSize.height]}]);
  };
  const submitAnnotations=async()=>{
    if(!capture) return;
    setAnnotationBusy(true); setError('');
    try{
      const response=await fetch('/api/vision/annotations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({frame_id:capture.id,boxes:annotations,reviewed:true})});
      if(!response.ok) throw new Error('Could not save annotations.');
      setAnnotationMessage(annotations.length?'Annotations saved for review.':'Negative frame saved for review.');
    }catch(cause){setError(cause instanceof Error?cause.message:'Could not save annotations.');}
    finally{setAnnotationBusy(false);}
  };
  const startRecording=async()=>{
    if(status?.state?.toLowerCase()!=='live') return;
    setRecordBusy(true); setError('');
    try{
      const response=await fetch('/api/vision/recording',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({duration_seconds:30})});
      if(!response.ok) throw new Error('Could not start the recording.');
    }catch(cause){setError(cause instanceof Error?cause.message:'Could not start the recording.');}
    finally{setRecordBusy(false);}
  };

  return <div className="vision-shell">
    <header className="vision-topbar">
      <a href={backHref} className="vision-brand" aria-label="Back to Paper to Plate"><span className="vision-logo-image" aria-hidden="true"/><span className="vision-divider"/><span>Vision lab</span></a>
      <div className="vision-top-actions"><span className="vision-preview-label">Research preview</span><a className="vision-back" href={backHref}><ArrowLeft size={15}/> Paper to Plate</a></div>
    </header>
    <main className="vision-main">
      <div className="vision-heading"><div><span className="vision-eyebrow">{viewMode==='live'?'MX BRIO · LIVE CAMERA':'RECORDED SOURCE · MODEL COMPARISON'}</span><h1>See the bench clearly.</h1><p>Watch tip and liquid predictions, capture evidence, and review frames for training.</p>{currentRunId&&<span className="vision-linked-run">Linked experiment · {currentRunId}</span>}</div><div className={'vision-state '+(cameraReady?'is-live':'is-stale')}><i/>{viewMode==='live'?stateLabel:'Recorded example'}</div></div>
      <div className="vision-disclaimer"><span>Research preview</span><span>Visible regions, not verified volume</span></div>
      <div className="vision-view-toggle" role="group" aria-label="Vision source"><button className={viewMode==='live'?'selected':''} onClick={()=>setViewMode('live')}>Live camera</button><button disabled={!examples.length} className={viewMode==='example'?'selected':''} onClick={()=>setViewMode('example')}>{examplesLoading?'Loading examples…':examples.length?'Recorded validation example':'No recorded examples'}</button>{viewMode==='example'&&examples.length>0&&<select aria-label="Choose recorded validation example" value={exampleId} onChange={event=>setExampleId(event.target.value)}>{examples.map(example=><option value={example.id} key={example.id}>{example.label}</option>)}</select>}</div>
      {error&&<div className="vision-alert error" role="alert"><WarningCircle size={19}/><span>{error}</span></div>}
      {status?.warning&&viewMode==='live'&&<div className="vision-alert warning" role="status"><WarningCircle size={19}/><span>{status.warning}</span></div>}
      <div className="vision-layout">
        <section className="vision-stage-panel">
          <div className="vision-panel-head"><div><span className="vision-eyebrow">{viewMode==='live'?'ANNOTATED STREAM':'HELD-OUT SOURCE'}</span><h2>{viewMode==='live'?'MX Brio field of view':'Recorded validation example'}</h2></div><span className="vision-live-chip"><i/>{viewMode==='live'?(cameraReady?'MJPEG · live':'Camera · waiting'):'OT-2 source data'}</span></div>
          {viewMode==='live'?<><div className="vision-frame"><img src={`${streamUrl}?session=${encodeURIComponent(status?.session_id||'connecting')}`} alt="Live annotated MX Brio camera stream" /><div className="vision-frame-overlay"><span>{status?.camera||'MX Brio'}</span><span>Frame {status?.frame_id??'—'}</span></div></div><div className="vision-caption"><span><VideoCamera size={15}/> Annotated frames from the camera endpoint</span><span>Captured {formatTime(status?.captured_at)}</span></div></>:<><div className="vision-frame vision-example-frame">{exampleId?<img src={`/api/vision/examples/${encodeURIComponent(exampleId)}/image?model=${encodeURIComponent(model)}`} alt="Recorded validation example"/>:<div className="vision-example-empty">Choose a recorded example when one is available.</div>}</div><div className="vision-caption"><span>Recorded validation example — OT-2 source data, not this camera</span><span>Held out for review</span></div></>}
          {viewMode==='live'&&<div className="vision-capture-row"><div><span className="vision-eyebrow">HUMAN REVIEW</span><p>Save a frame when the detector needs a correction.</p></div><div className="vision-record-actions"><button className="vision-capture-button secondary" disabled={captureBusy||!cameraReady} onClick={captureFrame}>{captureBusy?'Saving…':'Save frame for review'}</button><button className="vision-capture-button" disabled={recordBusy||status?.state?.toLowerCase()!=='live'||!!status?.recording?.active} onClick={startRecording}>{status?.recording?.active?`Recording ${status.recording.seconds_remaining??'…'}s`:recordBusy?'Starting…':'Record 30 seconds'}</button></div></div>}
          {viewMode==='live'&&status?.recording?.id&&!status.recording.active&&!!status.recording.frames&&<div className="vision-record-complete"><span>Recording complete · {status.recording.frames} frames</span><a href={`/api/vision/recordings/${encodeURIComponent(status.recording.id)}/archive`}>Download archive</a></div>}
        </section>
        <aside className="vision-inspector">
          <section className="vision-card model-card"><div className="vision-card-head"><div><span className="vision-eyebrow">DETECTOR</span><h3>Choose a model</h3></div><span className="vision-model-status">{modelBusy?'Switching…':modelReady?'Ready':selectedModel?.available===false?'Unavailable':'Loading'}</span></div><div className="vision-models">{models.map(option=><button key={option.id} disabled={!option.available||modelBusy} className={'vision-model-option '+(model===option.id?'selected':'')+(option.available?'':' unavailable')} onClick={()=>option.available&&selectModel(option.id as VisionModel)}><span><strong>{option.label}</strong><small>{option.detail|| (option.available?'Available':'Unavailable')}</small></span><span className="vision-radio">{model===option.id&&<CheckCircle size={18}/>}</span></button>)}</div>{viewMode==='example'&&<p className="vision-inline-note">Model selection applies to both views.</p>}</section>
          {viewMode==='live'?<><section className="vision-card"><div className="vision-card-head"><div><span className="vision-eyebrow">CURRENT READ</span><h3>What the model sees</h3></div><span className="vision-refresh">1 s polling</span></div><div className="vision-counts"><div><strong>{status?.counts?.tip??'—'}</strong><span>tips</span></div><div><strong>{status?.counts?.liquid??'—'}</strong><span>liquid regions</span></div></div><div className="vision-detection-list">{!cameraReady?<div className="vision-empty-read"><span>—</span><p>Waiting for a fresh live frame.<br/>Detections will appear when available.</p></div>:detections.length?detections.map((d,index)=><div className="vision-detection" key={`${d.label}-${index}`}><span className={'vision-detection-dot '+(d.label.toLowerCase().includes('liquid')?'liquid':'tip')}/><span><strong>{d.label}</strong><small>{Math.round(d.confidence*100)}% confidence · box [{d.box.map(n=>Math.round(n)).join(', ')}]</small></span></div>):<div className="vision-empty-read"><span>—</span><p>No visible detections yet.<br/>Keep the tip and liquid region in frame.</p></div>}</div></section><section className="vision-card vision-metrics"><div className="vision-card-head"><div><span className="vision-eyebrow">SIGNAL</span><h3>Capture health</h3></div></div><dl><div><dt>Inference</dt><dd>{typeof status?.inference_ms==='number'?`${status.inference_ms.toFixed(1)} ms`:'—'}</dd></div><div><dt>Frame rate</dt><dd>{typeof status?.fps==='number'?`${status.fps.toFixed(1)} fps`:'—'}</dd></div><div><dt>Last capture</dt><dd>{formatTime(status?.captured_at)}</dd></div></dl></section></>:<section className="vision-card vision-example-note"><span className="vision-eyebrow">VALIDATION LANE</span><h3>Source data stays separate</h3><p>This image is held out from the live camera path. Live frame age, detections, and capture health are intentionally hidden here.</p></section>}
        </aside>
      </div>
      {capture&&<section className="vision-annotation-panel"><div className="vision-panel-head"><div><span className="vision-eyebrow">FRAME {capture.id}</span><h2>Correct the detector</h2></div><button className="vision-close" aria-label="Close annotation panel" onClick={()=>setCapture(null)}><X size={18}/></button></div><p className="vision-annotation-help">Choose a label, then drag a box over each visible region. Leave the frame empty and save to record a negative example.</p><div className="vision-annotation-tools"><span>Label</span><button className={annotationLabel==='tip'?'selected':''} onClick={()=>setAnnotationLabel('tip')}>Tip</button><button className={annotationLabel==='liquid'?'selected':''} onClick={()=>setAnnotationLabel('liquid')}>Liquid</button><button className="vision-clear" onClick={()=>setAnnotations([])} disabled={!annotations.length}>Clear boxes</button></div><div className="vision-annotation-image-wrap"><div ref={annotationSurface} className="vision-annotation-surface" onPointerDown={beginBox} onPointerMove={moveBox} onPointerUp={finishBox}><img src={captureImageUrl} alt="Captured frame for annotation" onLoad={event=>setImageSize({width:event.currentTarget.naturalWidth||1,height:event.currentTarget.naturalHeight||1})}/>{annotations.map((annotation,index)=><div key={`${annotation.label}-${index}`} className={'vision-box '+annotation.label} style={boxStyle(annotation.box,imageSize.width,imageSize.height)}><span>{annotation.label}</span><button aria-label={`Remove ${annotation.label} box`} onPointerDown={event=>{event.stopPropagation();setAnnotations(current=>current.filter((_,i)=>i!==index));}}><X size={11}/></button></div>)}{draftStart&&draftEnd&&<div className="vision-box draft" style={{left:`${Math.min(draftStart.x,draftEnd.x)*100}%`,top:`${Math.min(draftStart.y,draftEnd.y)*100}%`,width:`${Math.abs(draftEnd.x-draftStart.x)*100}%`,height:`${Math.abs(draftEnd.y-draftStart.y)*100}%`}}/>}</div></div><div className="vision-annotation-footer"><span>{annotationMessage||`${annotations.length} box${annotations.length===1?'':'es'} ready`}</span><button className="vision-capture-button" disabled={annotationBusy} onClick={submitAnnotations}>{annotationBusy?'Saving…':'Save annotations'}</button></div></section>}
      <footer className="vision-footer"><span><i className="vision-footer-dot"/> No hardware controls in this preview</span><span>Powered by CubOS · {cameraReady?'Camera connected':stateLabel}</span></footer>
    </main>
  </div>;
}
