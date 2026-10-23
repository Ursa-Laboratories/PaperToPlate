import {useEffect,useState} from 'react';
import {ArrowLeft,ArrowRight,ArrowSquareOut,ChatCircleDots,CheckCircle,FilePdf,Flask,PaperPlaneTilt,SlidersHorizontal} from '@phosphor-icons/react';
import {api} from './api';
import type {Run} from './types';
import './question-explorer.css';

type Color='red'|'yellow'|'blue'|'water';
type Stock={color:Color;position:string;description:string};
type Point={x:number;y:number;z:number};
type Labware={key:string;config:Record<string,unknown>;positions?:Record<string,Point>;wells?:Record<string,Point>;location?:Point|null};
type Deck={mode:'live'|'recorded';label:string;deck:{labware:Labware[]};head:Point|null;inventory_id:number|null;containers:{labware_key:string;location_id:string;current_volume_ul:number;composition:Record<string,number>}[];tips:{rack_key:string;slot_id:string;status:string}[]};
type PaperIdea={id:string;title:string;url:string;abstract:string;authors:unknown[];source:string;year?:number;summary:string;experiment_title:string;experiment:string;steps:string[];readout:string;extra_materials:string[];fit:string;evidence:string;supported_method:boolean};
type Settings={total_ul:number;dye_percent:number;blocks:number;target_hex:string;start_row:string;first_tip:string;source_height_mm:number;red_source:string;yellow_source:string;blue_source:string;water_source:string;seed:number};
type Well={well:string;label:string;volumes_ul:Record<string,number>;total_ul:number};
type Selection={paper_id:string;status:string;paper:PaperIdea;proposal?:{title:string;explanation:string};settings?:Settings;design?:{wells:Well[]};validation?:{passed:boolean;errors:string[]};source?:{page_count:number};deck_mode?:string;depth_known?:boolean;tip_count?:number;run_id?:string};
type Exploration={id:string;question:string;answer:string;stocks:Stock[];papers:PaperIdea[];selected:Selection|null;bond:{mode:string;retrieved_at:number}};
const COLORS:Record<Color,string>={red:'#bd6469',yellow:'#d5b448',blue:'#5377b4',water:'#b5d2e1'};
const DEFAULTS:Stock[]=(['red','yellow','blue','water'] as Color[]).map((color,i)=>({color,position:`10_vial_holder.A${i+1}`,description:color==='water'?'Clean water':`Prepared ${color} aqueous dye, concentration not measured`}));
const RECORDED_RUN='8acbc9beb35c47bc8d2c9e08575f5b64';

export function DeckMap({value,stocks,proposed=[]}:{value:Deck;stocks:Stock[];proposed?:Well[]}){
 const projected=(p:Point)=>({x:p.x+13,y:177-p.y});
 const contents=new Map(value.containers.map(c=>[`${c.labware_key}.${c.location_id}`,c]));
 const tips=new Map(value.tips.map(t=>[`${t.rack_key}.${t.slot_id}`,t.status]));
 const targets=new Map(proposed.map(w=>[w.well,w]));
 const names:Record<string,string>={'10_vial_holder':'Stock vials',plate:'96-well plate',tips:'Tips',waste:'Waste'};
 return <svg viewBox="0 0 300 192" className="explore-deck" role="img" aria-label={`CubOS deck layout: stocks, 96-well plate, tip rack and waste. ${value.label}`}>
  <rect x="1" y="1" width="298" height="180" rx="3" fill="#fbfcfd" stroke="#d9e2ee"/>
  {Array.from({length:12},(_,i)=><line key={'x'+i} x1={13+i*25} y1="1" x2={13+i*25} y2="181" stroke="#e9eef4" strokeWidth=".35"/>)}
  {Array.from({length:8},(_,i)=><line key={'y'+i} x1="1" y1={2+i*25} x2="299" y2={2+i*25} stroke="#e9eef4" strokeWidth=".35"/>)}
  {value.deck.labware.map(l=>{const positions=l.positions||l.wells||{};const points=Object.entries(positions).map(([id,p])=>({id,...projected(p)}));const source=l.key==='10_vial_holder',rack=l.key==='tips';
   if(!points.length&&l.location){const p=projected(l.location);return <g key={l.key}><rect x={p.x-5} y={p.y-5} width="10" height="10" rx="2" fill="#eff2f6" stroke="#9aabc1" strokeWidth=".7"/><text x={p.x} y={p.y-8} textAnchor="middle" className="deck-label">{names[l.key]||l.key}</text></g>;}
   if(!points.length)return null;
   const xs=points.map(p=>p.x),ys=points.map(p=>p.y),x=Math.min(...xs)-6,y=Math.min(...ys)-7,w=Math.max(...xs)-Math.min(...xs)+12,h=Math.max(...ys)-Math.min(...ys)+14;
   return <g key={l.key}><rect x={x} y={y} width={w} height={h} rx="2" fill={rack?'#eff8f3':source?'#f6f8fc':'white'} stroke="#8da3c0" strokeWidth=".7"/><text x={x+1} y={y-3} className="deck-label">{names[l.key]||l.key}</text>
    {points.map(p=>{const key=l.key+'.'+p.id,stock=stocks.find(s=>s.position===key),tip=tips.get(key),record=contents.get(key),target=l.key==='plate'?targets.get(p.id):undefined;const occupied=(record?.current_volume_ul||0)>0;const fill=stock?COLORS[stock.color]:rack?(tip==='available'?'#72b69a':value.mode==='recorded'?'#c5d8d0':'#e6ede8'):target?'#d7e1f2':occupied?'#c8d3e8':'white';
     return <g key={p.id}><circle cx={p.x} cy={p.y} r={source?3:rack?1.5:2.8} fill={fill} stroke={rack?'none':target?'#233c78':'#7890b5'} strokeWidth={target?'.8':'.5'}><title>{key}{record?` · ${record.current_volume_ul} µL recorded`:''}{stock?` · ${stock.color}`:''}{target?` · proposed ${target.label}, ${target.total_ul} µL`:''}{tip?` · ${tip}`:''}</title></circle>{source&&<text x={p.x} y={p.y+7} textAnchor="middle" className="deck-coordinate">{p.id}</text>}</g>})}
   </g>;
  })}
  {value.head&&<g transform={`translate(${value.head.x+13},${177-value.head.y})`}><circle r="5" fill="#d7e1f2" stroke="#233c78" strokeWidth=".7"/><path d="M-7 0H7M0-7V7" stroke="#233c78" strokeWidth=".6"/><text x="8" y="1" className="deck-label">Pipette</text></g>}
  {[0,50,100,150,200,250].map(x=><text key={x} x={x+13} y="189" textAnchor="middle" className="deck-coordinate">{x}</text>)}
  <text x="294" y="189" textAnchor="end" className="deck-coordinate">mm</text>
 </svg>;
}

export default function QuestionExplorer({onProtocol,onPaperRequired}:{onProtocol:(run:Run)=>void;onPaperRequired:(question:string)=>void}){
 const [stage,setStage]=useState<'question'|'papers'|'experiment'>('question');
 const [question,setQuestion]=useState(''),[stocks,setStocks]=useState<Stock[]>(DEFAULTS),[editingStock,setEditingStock]=useState<Color|null>(null);
 const [deck,setDeck]=useState<Deck|null>(null),[deckError,setDeckError]=useState(''),[exploration,setExploration]=useState<Exploration|null>(null),[activePaper,setActivePaper]=useState('');
 const [busy,setBusy]=useState(''),[error,setError]=useState(''),[settings,setSettings]=useState<Settings|null>(null),[history,setHistory]=useState<{role:string;content:string}[]>([]);
 const [filter,setFilter]=useState('all'),[depthEntered,setDepthEntered]=useState(false);
 const inputsChanged=Boolean(exploration&&(question.trim()!==exploration.question.trim()||JSON.stringify(stocks)!==JSON.stringify(exploration.stocks)));
 useEffect(()=>{window.scrollTo({top:0,behavior:'smooth'});},[stage]);
 useEffect(()=>{let live=true;api<Deck>('/explore/deck').then(d=>{if(live)setDeck(d);}).catch(e=>{if(live)setDeckError(e.message);});return()=>{live=false;};},[]);
 useEffect(()=>{const id=new URLSearchParams(location.search).get('exploration');if(!id)return;let live=true;api<Exploration>(`/explore/${id}`).then(e=>{if(!live)return;setExploration(e);setQuestion(e.question);setStocks(e.stocks);setActivePaper(e.selected?.paper_id||e.papers[0]?.id||'');setSettings(e.selected?.settings||null);setStage(e.selected?'experiment':'papers');}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[]);
 async function research(){setBusy('Searching Valency Bond');setError('');try{const e=await api<Exploration>('/explore/research',{method:'POST',body:JSON.stringify({question,stocks,history:history.slice(-6)})});setExploration(e);setHistory(h=>[...h,{role:'user',content:question},{role:'assistant',content:e.answer}]);setActivePaper(e.papers[0]?.id||'');setStage('papers');setSettings(null);historyReplace(e.id);}catch(e){setError((e as Error).message);}finally{setBusy('');}}
 function historyReplace(id:string){window.history.replaceState(null,'',`?explore=1&exploration=${id}`);}
 async function choose(p:PaperIdea){if(!exploration)return;setBusy(p.supported_method?'Reading methods · proposing parameters':'Opening proposed setup');setError('');try{const e=await api<Exploration>(`/explore/${exploration.id}/select`,{method:'POST',body:JSON.stringify({paper_id:p.id})});setExploration(e);setSettings(e.selected?.settings||null);setStage('experiment');}catch(e){setError((e as Error).message);}finally{setBusy('');}}
 async function generate(){if(!exploration||!settings)return;setBusy('Generating CubOS protocol');setError('');try{const r=exploration.selected?.run_id&&JSON.stringify(settings)===JSON.stringify(exploration.selected.settings)?await api<Run>(`/runs/${exploration.selected.run_id}`):await api<Run>(`/explore/${exploration.id}/prepare`,{method:'POST',body:JSON.stringify({settings,source_depth_confirmed:depthEntered})});onProtocol(await api<Run>(`/runs/${r.id}`));}catch(e){setError((e as Error).message);}finally{setBusy('');}}
 const paper=exploration?.papers.find(p=>p.id===activePaper),selected=exploration?.selected;
 const visible=exploration?.papers.filter(p=>filter==='all'||(filter==='stocks'?p.fit==='fits_stocks':p.supported_method))||[];
 return <div className="question-explorer">
  <nav className="explore-progress" aria-label="Experiment discovery"><button className={stage==='question'?'current':''} onClick={()=>setStage('question')}>Question</button><span>/</span><button disabled={!exploration||inputsChanged} className={stage==='papers'?'current':''} onClick={()=>setStage('papers')}>Literature</button><span>/</span><button disabled={!selected||inputsChanged} className={stage==='experiment'?'current':''} onClick={()=>setStage('experiment')}>Experiment</button></nav>
  {stage==='question'&&<>
   <h1>Explore a question.</h1>
   <div className="explore-stocks" aria-label="Available stocks">{stocks.map(s=><button key={s.color} onClick={()=>setEditingStock(editingStock===s.color?null:s.color)} aria-expanded={editingStock===s.color}><i style={{background:COLORS[s.color]}}/><strong>{s.color}</strong><span>{s.position.split('.')[1]}</span></button>)}</div>
   {editingStock&&<label className="field stock-description">{editingStock} stock<input value={stocks.find(s=>s.color===editingStock)!.description} onChange={e=>setStocks(stocks.map(s=>s.color===editingStock?{...s,description:e.target.value}:s))}/></label>}
   <form className="question-composer" onSubmit={e=>{e.preventDefault();research();}}><label className="sr-only" htmlFor="explore-question">Your research question</label><textarea id="explore-question" rows={2} value={question} onChange={e=>setQuestion(e.target.value)} placeholder="What would you like to explore with these stocks?" onKeyDown={e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey)){e.preventDefault();if(question.trim().length>=5&&!busy)research();}}}/><div><span><ChatCircleDots size={17}/> Valency Bond</span><button className="button primary" disabled={!!busy||question.trim().length<5} type="submit">Explore <PaperPlaneTilt size={16}/></button></div></form>
   <section className="explore-deck-section"><div className="content-heading"><h2>Your workcell</h2><span className="deck-state"><i className={'dot '+(deck?.mode==='live'?'good':'')}/>{deck?.label||'Reading CubOS'}</span></div>{deck?<DeckMap value={deck} stocks={stocks}/>:<div className="deck-loading">{deckError||'Loading deck layout…'}</div>}</section>
  </>}
  {stage==='papers'&&exploration&&<>
   <div className="explore-page-heading"><div><span className="eyebrow">VALENCY BOND · {exploration.papers.length} PAPERS</span><h1>Explore the literature.</h1></div></div>
   <div className="research-response"><ChatCircleDots size={22}/><p>{exploration.answer}</p></div>
   <div className="paper-filter" aria-label="Paper filter">{[['all','All papers'],['stocks','Fits these stocks'],['method','Method available']].map(([key,label])=><button key={key} aria-pressed={filter===key} onClick={()=>setFilter(key)}>{label}</button>)}</div>
   <div className="literature-browser"><div className="literature-list" role="group" aria-label="Papers returned by Valency">{visible.map((p,i)=><button key={p.id} className={activePaper===p.id?'selected':''} onClick={()=>setActivePaper(p.id)}><span className="paper-number">{String(i+1).padStart(2,'0')}</span><span><strong>{p.title}</strong><small>{p.source||'Research paper'} · {p.evidence}</small></span></button>)}</div>
   {paper&&<article className="paper-inspector" key={paper.id}><div className="paper-meta"><FilePdf size={18}/><span>{paper.source||'Research paper'}{paper.year?` · ${paper.year}`:''}</span><span className={'fit-chip '+(paper.fit==='fits_stocks'?'fits':'')}>{paper.fit==='fits_stocks'?'Fits these stocks':paper.fit==='needs_equipment'?'Extra equipment':'Method details needed'}</span></div><h2>{paper.title}</h2><p className="paper-summary">{paper.summary}</p><div className="paper-source-links"><a href={paper.url} target="_blank" rel="noreferrer">Read paper <ArrowSquareOut size={14}/></a><details><summary>Abstract</summary><p>{paper.abstract}</p></details></div><section className="suggested-experiment"><span className="eyebrow">SUGGESTED EXPERIMENT</span><h3>{paper.experiment_title}</h3><p>{paper.experiment}</p><ol>{paper.steps.map((s,i)=><li key={i}>{s}</li>)}</ol><div className="suggested-readout"><span>Readout</span><strong>{paper.readout}</strong></div>{!!paper.extra_materials.length&&<div className="needed-materials"><span>Also needs</span>{paper.extra_materials.map(m=><small key={m}>{m}</small>)}</div>}</section><footer><span>{paper.supported_method?'Full method retrieved on selection':'Proposed from the abstract'}</span><button className="button primary" disabled={!!busy||inputsChanged} onClick={()=>choose(paper)}>Choose experiment <ArrowRight size={16}/></button></footer></article>}
   </div>
   <form className="question-refine" onSubmit={e=>{e.preventDefault();research();}}><input aria-label="Refine your question" value={question} onChange={e=>setQuestion(e.target.value)}/><button className="icon-button" aria-label="Search refined question" disabled={!!busy||question.trim().length<5}><PaperPlaneTilt size={20}/></button></form>
  </>}
  {stage==='experiment'&&selected&&<>
   <button className="text-link" onClick={()=>setStage('papers')}><ArrowLeft size={15}/> Back to papers</button>
   <span className="eyebrow experiment-kicker">SELECTED EXPERIMENT</span><h1>{selected.proposal?.title.split(':')[0]||selected.paper.experiment_title}</h1>
   <a className="selected-source" href={selected.paper.url} target="_blank" rel="noreferrer"><FilePdf size={16}/>{selected.paper.title}<ArrowSquareOut size={14}/></a>
   {selected.status==='methods_needed'?<div className="method-needed"><h2>Bring in the full method.</h2><p>{selected.paper.experiment}</p><p>The suggestion is based on the abstract. The full paper is needed to extract quantities and steps.</p><button className="button primary" onClick={()=>onPaperRequired(exploration!.question+': '+selected.paper.experiment)}>Upload full paper <ArrowRight size={16}/></button></div>:settings&&<>
    <details className="setup-rationale"><summary>Why this setup</summary><p>{selected.proposal?.explanation}</p></details>
    <div className="ai-setup-header"><span><CheckCircle size={18}/> AI-proposed setup</span><span>{selected.source?.page_count} source pages</span></div>
    <div className="proposed-parameters"><label>Per well<input aria-label="Volume per well" type="number" min={30} max={240} step={6} value={settings.total_ul} onChange={e=>setSettings({...settings,total_ul:Number(e.target.value)})}/><small>µL</small></label><label>Colored stocks<input aria-label="Dye fraction" type="number" min={10} max={90} step={10} value={settings.dye_percent} onChange={e=>setSettings({...settings,dye_percent:Number(e.target.value)})}/><small>%</small></label><label>Wells<select aria-label="Number of wells" value={settings.blocks} onChange={e=>setSettings({...settings,blocks:Number(e.target.value)})}><option value={1}>10</option><option value={2}>20</option></select></label></div>
    {deck&&<DeckMap value={deck} stocks={stocks} proposed={selected.design?.wells}/>}
    <details className="explore-setup-details" open={!selected.depth_known||undefined}><summary><SlidersHorizontal size={16}/> Deck setup</summary><div className="setup-fields"><label className="field">First plate row<select value={settings.start_row} onChange={e=>setSettings({...settings,start_row:e.target.value})}>{'ABCDEFGH'.split('').map(r=><option key={r}>{r}</option>)}</select></label><label className="field">First tip<input value={settings.first_tip} onChange={e=>setSettings({...settings,first_tip:e.target.value})}/></label><label className="field">Stock offset (mm)<input type="number" placeholder="Required" value={selected.depth_known||depthEntered?settings.source_height_mm:''} onChange={e=>{setDepthEntered(e.target.value!=='');setSettings({...settings,source_height_mm:Number(e.target.value)});}}/></label></div><p>{selected.deck_mode==='live'?'Suggested from current CubOS inventory. Verify the physical setup before Run.':'Recorded setup. Reconnect CubOS and confirm current stocks, wells and tips before a physical run.'}</p></details>
    {selected.validation&&!selected.validation.passed&&<div className="inline-warning">{selected.validation.errors.join(' ')}</div>}
    <div className="prepare-action"><span><Flask size={18}/> {selected.tip_count} tips · pipette mixing</span><button className="button primary" disabled={!!busy||inputsChanged||(!selected.depth_known&&!depthEntered)} onClick={generate}>{selected?.run_id&&JSON.stringify(settings)===JSON.stringify(selected.settings)?'Open experiment':'Generate experiment'} <ArrowRight size={17}/></button></div>
    <details className="recorded-run-link"><summary>Recorded demonstration</summary><button className="text-link" onClick={async()=>onProtocol(await api<Run>(`/runs/${RECORDED_RUN}`))}>View the completed RYB run <ArrowRight size={14}/></button></details>
   </>}
  </>}
  {inputsChanged&&stage!=='question'&&<p className="inline-warning">Search the revised question before choosing an experiment.</p>}
  {busy&&<div className="explore-busy" role="status"><span className="small-spinner"/>{busy}</div>}{error&&<p className="inline-warning" role="alert">{error}</p>}
 </div>;
}
