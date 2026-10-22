import {useState} from 'react';
import {ArrowRight,CheckCircle,User,Robot,WarningCircle} from '@phosphor-icons/react';
import type {Run,StockInput} from './types';

type Props={run:Run;busy:boolean;onSave:(stocks:StockInput[])=>Promise<void>;onConfirm:(positions:string[])=>Promise<void>;onValidate:()=>void;onReview:()=>void;onInspect:()=>void;onRun:()=>void};
const volume=(n:number|null)=>n===null?'Not specified':n>=1000?`${Number((n/1000).toFixed(3))} mL`:`${Number(n.toFixed(2))} µL`;
const position=(p:string)=>p.split('.').slice(1).join('.')||p;

export default function PreparationPanel(props:Props){
 const {run,busy,onSave,onConfirm,onValidate,onReview,onInspect}=props;
 const sheet=run.preparation;
 const [loaded,setLoaded]=useState<string[]>([]),[humanReady,setHumanReady]=useState(false),[editing,setEditing]=useState(false),[stocks,setStocks]=useState<StockInput[]>([]);
 if(!sheet)return <section className="bench-empty">No protocol yet.</section>;
 const allLoaded=sheet.stocks.length>0&&sheet.stocks.every(s=>loaded.includes(s.position));
 const configured=Math.min(...sheet.stocks.map(s=>s.effective_capacity_ul??Infinity));
 const robot=run.execution_summary?.length?run.execution_summary:sheet.robot_operations.length?Array.from(new Set(sheet.robot_operations)):['Perform the transfers and mixing shown in the generated protocol.'];
 const colorDemo=run.demonstration?.kind==='colored_water';
 const validated=sheet.validation_ready;
 const reviewed=sheet.review_ready;
 function beginEdit(){setStocks(sheet!.stocks.map(s=>({position:s.position,material:s.material,concentration:s.concentration,preparation:s.preparation,load_volume_ul:s.load_volume_ul,citations:s.citations||[]})));setEditing(true);}
 function edit(index:number,patch:Partial<StockInput>){setStocks(old=>old.map((s,i)=>i===index?{...s,...patch}:s));}
 return <div className="bench-workflow">
  <div className="bench-constraints" aria-label="Experimental limits">
   <div><small>Pipette</small><strong>{sheet.pipette_min_ul}–{sheet.pipette_max_ul} µL</strong></div>
   <div><small>Well fill / limit</small><strong>{volume(sheet.well_peak_ul)} <em>/ {volume(sheet.well_capacity_ul)}</em></strong></div>
   <div><small>Vial limit</small><strong>{Number.isFinite(configured)?volume(configured):'—'}</strong></div>
   <div><small>Tips</small><strong>{sheet.tip_count}</strong></div>
  </div>
  <div className="bench-columns">
   <section className="human-preparation" aria-labelledby="human-prep-heading">
    <div className="bench-section-heading"><div className="owner-symbol"><User size={22}/></div><div><h2 id="human-prep-heading">Load stocks</h2></div><button className="small-button" disabled={busy||!!run.handoff} onClick={()=>editing?setEditing(false):beginEdit()}>{editing?'Cancel':'Edit'}</button></div>
    {run.demonstration?.stock_layout&&<div className="color-stock-map"><div className="color-stock-grid" aria-label="Stock holder">{run.demonstration.stock_layout.map(v=><div key={v.position} className={'color-vial color-vial-'+v.color} title={v.use}><strong>{position(v.position)}</strong><span>{v.color}</span></div>)}</div></div>}
    <div className="stock-table-wrap"><table className="stock-table"><thead><tr><th>Vial</th><th>Stock</th><th>Load</th><th>Loaded</th></tr></thead><tbody>
     {sheet.stocks.map((stock,i)=><tr key={stock.position} className={sheet.confirmed||loaded.includes(stock.position)?'stock-loaded':''}>
      <th scope="row"><span className="vial-position">{position(stock.position)}</span></th>
      <td>{editing?<><label className="field">Stock<input value={stocks[i]?.material||''} onChange={e=>edit(i,{material:e.target.value})}/></label><label className="field">Concentration<input value={stocks[i]?.concentration||''} onChange={e=>edit(i,{concentration:e.target.value})}/></label><label className="field">Preparation<textarea rows={3} value={stocks[i]?.preparation||''} onChange={e=>edit(i,{preparation:e.target.value})}/></label></>:<strong>{colorDemo?stock.material.split(' · ')[0].replace(' water',''):stock.material}{!colorDemo&&stock.concentration?` · ${stock.concentration}`:''}</strong>}</td>
      <td>{editing?<label className="field">µL<input type="number" min="0.1" step="0.1" value={stocks[i]?.load_volume_ul??''} onChange={e=>edit(i,{load_volume_ul:e.target.value===''?null:Number(e.target.value)})}/></label>:<strong>{volume(stock.load_volume_ul)}</strong>}</td>
      <td><input type="checkbox" aria-label={`Loaded vial ${position(stock.position)}`} disabled={editing||busy||sheet.confirmed} checked={sheet.confirmed||loaded.includes(stock.position)} onChange={e=>setLoaded(old=>e.target.checked?[...old,stock.position]:old.filter(x=>x!==stock.position))}/></td>
     </tr>)}
    </tbody></table></div>
    {editing&&<div className="stock-edit-actions"><button className="button primary" disabled={busy} onClick={async()=>{await onSave(stocks);setEditing(false);}}>Save</button></div>}
    <details className="prep-detail"><summary>Instructions</summary><div className="human-before"><ol>{sheet.human_before.map((step,i)=><li key={i}>{step}</li>)}</ol>{sheet.stocks.map(s=><p key={s.position}><strong>{position(s.position)}</strong> · {s.preparation}</p>)}</div></details>
    {sheet.issues.length>0&&<div className="prep-issues" role="status"><strong><WarningCircle size={17}/> Resolve the loading plan</strong><ul>{sheet.issues.map((issue,i)=><li key={i}>{issue}</li>)}</ul></div>}
    <div className="loading-confirmation">{sheet.confirmed?<p className="loading-complete"><CheckCircle size={22}/> Loading confirmed</p>:<><label className="check-row"><input type="checkbox" checked={humanReady} disabled={editing||busy} onChange={e=>setHumanReady(e.target.checked)}/><span>Preparation and setup checked</span></label><button className="button primary" disabled={busy||editing||!allLoaded||!humanReady||!sheet.can_confirm} onClick={()=>onConfirm(sheet.stocks.map(s=>s.position))}>Confirm loading <CheckCircle size={17}/></button></>}</div>
   </section>
   <aside className="execution-column">
    <section className="robot-work"><div className="bench-section-heading"><div className="owner-symbol"><Robot size={23}/></div><div><h2>CubOS</h2></div></div><details className="prep-detail"><summary>{run.steps?.length||0} commands</summary><ol>{robot.map((step,i)=><li key={i}><span>{String(i+1).padStart(2,'0')}</span><p>{step}</p></li>)}</ol></details><button className="text-link" onClick={onInspect}>View protocol <ArrowRight size={16}/></button></section>
    {sheet.human_after.length>0&&<details className="after-run prep-detail"><summary>After run</summary>{sheet.human_after.map((step,i)=><p key={i}>{step}</p>)}</details>}
    <section className="bench-run-state"><div className="readiness-row"><span>{validated?<CheckCircle/>:<WarningCircle/>} Validation</span><button className="text-link" disabled={busy} onClick={onValidate}>{validated?'Recheck':'Validate'}</button></div><div className="readiness-row"><span>{reviewed?<CheckCircle/>:<WarningCircle/>} Review</span><button className="text-link" disabled={busy} onClick={onReview}>{reviewed?'View':'Review'}</button></div><div className="readiness-row"><span>{sheet.confirmed?<CheckCircle/>:<WarningCircle/>} Loading</span></div></section>
   </aside>
  </div>
 </div>;
}
