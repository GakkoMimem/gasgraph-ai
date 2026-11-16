const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const { webcrypto }=require('crypto');const {TextEncoder}=require('util');
const base=path.resolve(__dirname,'../docs');
const context={console,crypto:webcrypto,TextEncoder,Date,Set,Map,Promise,Number,Object,String,Uint8Array};
context.window=context;
context.fetch=async (url)=>{
 const file=path.resolve(base,String(url).replace(/^\.\//,''));
 if(!file.startsWith(base+path.sep))throw Error('Outside docs');
 return {ok:fs.existsSync(file),status:fs.existsSync(file)?200:404,json:async()=>JSON.parse(fs.readFileSync(file,'utf8'))};
};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(base,'static-engine.js'),'utf8'),context);
(async()=>{
 const api=context.GasGraphStatic.api;
 const b=await api('bootstrap');assert.equal(b.network.assets.length,22);
 for(const s of b.scenarios){
  const r=await api('analyze',s);
  assert.equal(r.asset.id,s.asset_id);
  assert.equal(r.window.start,s.start);
  assert.ok(r.analysis_id.startsWith('AN-'));
  console.log(s.id, r.analysis_id, r.score.value, r.impact.affected_count,r.schedule.direct_count,r.schedule.coordination_count);
  if(s.id==='south'){assert.equal(r.draft_order.blocked,true); assert.ok(r.draft_order.blocking_job_ids.includes('MW-024'));}
 }
 const ask=await api('ask',{question:'Can you analyze compressor C-201?',start:'2027-07-13T09:00',duration_hours:3});assert.equal(ask.analysis.asset.id,'C-201');
 const unrecognized=await api('ask',{question:'???'});assert.equal(unrecognized.understood,false);
 let blocked=false;try{await api('approve',{order_id:'test'})}catch(e){blocked=true;}assert.ok(blocked);
 assert.ok((await api('bootstrap')).audit.length>0);
 console.log('Static engine checks: PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
