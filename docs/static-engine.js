/* GasGraph AI — GitHub Pages edition.
 * All calculations run locally in the browser; no server, API key or hosted LLM.
 * Independent educational prototype. Entirely fictional topology and schedules.
 */
(() => {
  'use strict';
  const model = { network: null, jobs: null, scenarios: null, assets: null, forward: null,
    audit: [], current: null };
  const MAX_EVENTS = 60;
  const canonical = (value) => String(value).trim();
  const pad = n => String(n).padStart(2, '0');
  const fmt = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;

  function parseTime(s) {
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(s)) throw new Error('Use a local date-time without time zone');
    const d = new Date(s);
    if (Number.isNaN(d.getTime()) || !fmt(d).startsWith(s.substring(0,16))) throw new Error('Invalid demo date');
    return d;
  }
  async function sha256(s) {
    const raw = new TextEncoder().encode(s);
    const digest = await crypto.subtle.digest('SHA-256', raw);
    return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2,'0')).join('');
  }
  function event(action, detail) {
    model.audit.unshift({ at: new Date().toISOString().replace(/\.\d{3}Z$/, '+00:00'), action, detail });
    model.audit = model.audit.slice(0,MAX_EVENTS);
  }
  function walk(start, blocked = new Set()) {
    if (blocked.has(start)) return {};
    const paths = { [start]: [start] };
    const queue = [start];
    for (let i = 0; i < queue.length; i++) {
      const id = queue[i];
      for (const next of model.forward[id] || []) {
        if (!Object.prototype.hasOwnProperty.call(paths,next) && !blocked.has(next)) {
          paths[next] = [...paths[id],next];
          queue.push(next);
        }
      }
    }
    return paths;
  }
  function dependencies(id) {
    if (!model.assets[id]) throw new Error('Unknown synthetic asset: ' + id);
    const paths = walk(id); delete paths[id];
    return { asset_id:id, direct:[...model.forward[id]], downstream:Object.keys(paths), paths,
      relationship_type:'FLOWS_TO', analysis_limit:'Topological dependencies only; no hydraulic simulation.' };
  }
  function sourceReach(blocked) {
    const seen = new Set();
    for (const src of model.network.sources) for (const id of Object.keys(walk(src,blocked))) seen.add(id);
    return seen;
  }
  function checkConflicts(id,start,duration) {
    const st = parseTime(start), en = new Date(st.getTime()+duration*3600000);
    const dependency = dependencies(id);
    const downstream = new Set(dependency.downstream);
    const conflicts = [];
    for (const job of model.jobs) {
      const js = parseTime(job.start), je = parseTime(job.end);
      if (st >= je || js >= en) continue;
      let classification,reason,path;
      if (job.asset_id === id) {
        classification='direct'; reason='Same asset and overlapping time window.'; path=[id];
      } else if (downstream.has(job.asset_id)) {
        classification='coordination'; reason='Overlapping work on a downstream dependency; review required.';
        path=dependency.paths[job.asset_id];
      } else {
        const reverse = walk(job.asset_id);
        if (!Object.prototype.hasOwnProperty.call(reverse,id)) continue;
        classification='coordination'; reason='Overlapping work on an upstream dependency; review required.';
        path=reverse[id];
      }
      conflicts.push({...job,classification,reason,dependency_path:path});
    }
    conflicts.sort((a,b) => (a.classification==='direct'?0:1)-(b.classification==='direct'?0:1) || a.start.localeCompare(b.start) || a.id.localeCompare(b.id));
    return { asset_id:id, start:fmt(st), end:fmt(en), conflicts,
      direct_count:conflicts.filter(c => c.classification==='direct').length,
      coordination_count:conflicts.filter(c => c.classification==='coordination').length };
  }
  async function analyze(payload) {
    const id = canonical(payload.asset_id), start = canonical(payload.start);
    const duration = Number(payload.duration_hours ?? 4);
    if (!Number.isFinite(duration) || duration < 0.5 || duration > 48) throw new Error('Duration must be between 0.5 and 48 hours');
    const st = parseTime(start);
    if (st.getFullYear()<2026 || st.getFullYear()>2035) throw new Error('Demo schedule must be between years 2026 and 2035');
    const asset = model.assets[id];
    if (!asset) throw new Error('Unknown synthetic asset: ' + id);
    const deps=dependencies(id), scheduling=checkConflicts(id,start,duration);
    const baseline=sourceReach(new Set()), after=sourceReach(new Set([id]));
    const potential=[...deps.downstream], unreachable=potential.filter(a=>baseline.has(a)&&!after.has(a));
    const alternate=potential.filter(a=>after.has(a));
    const score=Math.min(95,12+potential.length*3+scheduling.direct_count*19+scheduling.coordination_count*7+unreachable.length*3);
    const severity=score>=65?'Elevated':score>=35?'Moderate':'Low';
    const orderId='WO-'+(await sha256(`${id}|${fmt(st)}|${duration}`)).slice(0,9).toUpperCase();
    const order={id:orderId,asset_id:id,asset_label:asset.label,
      requested_window:{start:fmt(st),end:scheduling.end},
      description:`Assess and plan synthetic maintenance intervention on ${asset.label}.`,
      checks:['Confirm technical isolation and real-world constraints outside this demo',
        'Review overlapping and downstream maintenance dependencies',
        'Obtain human authorization through an approved operational workflow'],
      approval_status:scheduling.direct_count?'Blocked — direct scheduling overlap':'Draft — not sent to any operational system',
      blocked:Boolean(scheduling.direct_count),
      blocking_job_ids:scheduling.conflicts.filter(c=>c.classification==='direct').map(c=>c.id),synthetic_only:true};
    const analysisId='AN-'+(await sha256(orderId)).slice(0,9).toUpperCase();
    const report={ analysis_id:analysisId, asset,window:{start:fmt(st),end:scheduling.end},
      dependencies:deps,schedule:scheduling,
      impact:{potentially_affected:potential,alternate_path_possible:alternate,
        newly_unreachable_in_topology:unreachable,affected_count:potential.length,
        newly_unreachable_count:unreachable.length,redundant_path_count:alternate.length},
      score:{value:score,label:severity,
        method:'Illustrative index: downstream reach + overlapping jobs + source reachability. Not an engineering or safety assessment.'},
      draft_order:order,
      tool_trace:[
        {tool:'ontology.resolve_entity',result:`${asset.label} (${id}) resolved`},
        {tool:'graph.find_dependencies',result:`${potential.length} downstream assets with evidence paths`},
        {tool:'schedule.check_conflicts',result:`${scheduling.direct_count} direct, ${scheduling.coordination_count} coordination reviews`},
        {tool:'workflow.draft_work_order',result:`${orderId}: DRAFT; no external action`}],
      caveat:'Fictional data. Reachability is not gas-flow simulation. A possible alternate route is not proof of capacity or safety.'};
    model.current=report;
    event('ANALYSIS', `${id} · ${analysisId}`);
    return report;
  }
  function resolveAsset(query) {
    const text=query.toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
    if (!text) return null;
    for (const asset of Object.values(model.assets)) {
      if (query.toLowerCase().includes(asset.id.toLowerCase()) || query.toLowerCase().includes(asset.label.toLowerCase())) return asset;
    }
    const aliases={'westhaven':'T-WEST','western terminal':'T-WEST','west terminal':'T-WEST',
      'terminal a':'T-WEST','østterminal':'T-EAST','eastport':'T-EAST',
      'southbay':'T-SOUTH','south terminal':'T-SOUTH','compressor':'C-201',
      'kompressor':'C-201','south meter':'M-320','meter 320':'M-320',
      'south grid':'OFF-SOUTH','central exchange':'J-CENT','boreal storage':'STOR-01'};
    for (const [alias,id] of Object.entries(aliases)) if (text.includes(alias)) return model.assets[id];
    return null;
  }
  async function ask(payload) {
    const question=canonical(payload.question||'');
    if (!question || question.length>600) throw new Error('Question must contain 1–600 characters');
    const asset=resolveAsset(question);
    event('AGENT_QUERY',`Rule router · ${asset?'resolved':'unresolved'}`);
    if (!asset) return {mode:'deterministic-tool-router',understood:false,
      message:'I could not resolve an asset in this synthetic ontology. Select an asset or mention its ID/name.',
      available_assets:Object.values(model.assets).slice(0,8).map(a=>({id:a.id,label:a.label})),
      tool_trace:[{tool:'ontology.resolve_entity',result:'No asset matched; no analysis executed'}]};
    const analysis=await analyze({asset_id:asset.id,start:payload.start??'2027-07-13T09:00',duration_hours:payload.duration_hours??4});
    const imp=analysis.impact, sched=analysis.schedule;
    const names=imp.newly_unreachable_in_topology.slice(0,4).map(id=>model.assets[id].label);
    let message=`${asset.label} has ${imp.affected_count} potentially dependent downstream assets. `+
      `${imp.newly_unreachable_count} become unreachable from the synthetic sources when this node is removed. `+
      `Review ${sched.direct_count} direct overlaps and ${sched.coordination_count} dependency-based coordination items. `;
    if (names.length) message+=`Example unreachable nodes: ${names.join(', ')}. `;
    message+='A draft work order is ready for human review; no real actions are performed.';
    return {mode:'deterministic-tool-router',understood:true,message,analysis,tool_trace:analysis.tool_trace};
  }
  async function bootstrap() {
    if (!model.network) {
      const names=['network','jobs','scenarios'];
      const responses=await Promise.all(names.map(name=>fetch(`./data/${name}.json`)));
      for (let i=0;i<responses.length;i++) if (!responses[i].ok) throw new Error(`Could not load ${names[i]}.json (${responses[i].status})`);
      const items=await Promise.all(responses.map(r=>r.json()));
      [model.network,model.jobs,model.scenarios]=items;
      model.assets=Object.fromEntries(model.network.assets.map(a=>[a.id,a]));
      model.forward=Object.fromEntries(model.network.assets.map(a=>[a.id,[]]));
      for (const e of model.network.relationships) {
        if (!model.assets[e.source]||!model.assets[e.target]) throw new Error('Invalid synthetic relationship');
        model.forward[e.source].push(e.target);
      }
    }
    return {network:model.network,jobs:model.jobs,scenarios:model.scenarios,orders:[],
      audit:[...model.audit],current:model.current,
      engine:'Deterministic graph and rule tools (browser-only, no hosted LLM)',
      version:'1.2.0',environment:'PUBLIC / SYNTHETIC · BROWSER-ONLY'};
  }
  async function api(path, body) {
    await bootstrap();
    switch(path) {
      case 'bootstrap': return bootstrap();
      case 'health': return {ok:true,mode:'synthetic-browser',version:'1.2.0'};
      case 'analyze': return analyze(body||{});
      case 'ask': return ask(body||{});
      case 'approve': throw new Error('Public preview: work-order approvals are intentionally disabled.');
      case 'reset': throw new Error('Public preview: no shared server state exists to reset.');
      default: throw new Error('Unknown demo operation: '+path);
    }
  }
  window.GasGraphStatic = {api};
})();
