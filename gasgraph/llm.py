"""Optional *local-only* LLM tool planner for LM Studio / Ollama OpenAI-compatible API.

A model does NOT compute impact, fabricate graph facts, or approve an action.
It may only select one constrained tool; the deterministic engine validates and
executes the request. Text is then grounded in that engine's output.
"""
from __future__ import annotations
import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class LocalPlannerError(Exception):
    pass


def config():
    base=os.getenv('GASGRAPH_LLM_BASE_URL','').strip().rstrip('/')
    model=os.getenv('GASGRAPH_LLM_MODEL','').strip()
    if not base or not model:
        return None
    parsed=urlparse(base)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1','localhost','::1'} or parsed.username or parsed.password:
        raise ValueError('LLM endpoint must use plain HTTP on loopback only (localhost, 127.0.0.1, ::1).')
    if parsed.query or parsed.fragment:
        raise ValueError('LLM base URL may not contain query or fragment.')
    return {'base_url':base,'model':model}


def plan_with_local_llm(question: str, assets: list[dict], start: str, duration_hours: float) -> dict | None:
    """Return validated tool request (NOT model claims). None = no tool selection."""
    cfg=config()
    if cfg is None:
        return None
    valid={a['id'] for a in assets}
    names='\n'.join(f"{a['id']}: {a['label']} ({a['type']})" for a in assets)
    schema={'type':'function','function':{'name':'analyze_maintenance','description':'Assess a hypothetical maintenance window on a known synthetic network asset. Never operates physical systems.',
          'parameters':{'type':'object','properties':{
             'asset_id':{'type':'string','description':'Exact ID from the fictional asset inventory'},
             'start':{'type':'string','description':'Local ISO 8601 date time YYYY-MM-DDTHH:MM'},
             'duration_hours':{'type':'number','description':'Duration between 0.5 and 48 hours'}},
             'required':['asset_id']}}}
    system=("You are a local planning assistant for a purely SYNTHETIC demonstration. "
            "Your only permitted action is to call analyze_maintenance for a named entity from this inventory. "
            "Use the user's requested time/duration if explicit, else use supplied defaults. "
            "Do not guess nonexistent IDs, source operational data, or claim you can operate infrastructure. "
            f"Demo default time: {start}; default duration hours: {duration_hours}.\nInventory:\n{names}")
    body={'model':cfg['model'],'messages':[{'role':'system','content':system},{'role':'user','content':question}],
          'temperature':0,'stream':False,'tools':[schema],'tool_choice':'auto'}
    req=Request(cfg['base_url']+'/chat/completions',data=json.dumps(body).encode(),
                headers={'Content-Type':'application/json'},method='POST')
    try:
        with urlopen(req,timeout=20) as resp:
            result=json.loads(resp.read(500000).decode())
    except Exception as exc:
        raise LocalPlannerError(f'Local model unavailable: {type(exc).__name__}: {exc}') from exc
    try:
        msg=result['choices'][0]['message']
        calls=msg.get('tool_calls') or []
        if not calls:
            return None
        item=next((c for c in calls if c.get('function',{}).get('name')=='analyze_maintenance'),None)
        if not item:
            return None
        args=json.loads(item['function']['arguments'])
        asset=str(args.get('asset_id','')).strip()
        if asset not in valid:
            return None
        proposed_start=str(args.get('start',start))
        proposed_duration=float(args.get('duration_hours',duration_hours))
        if not 0.5 <= proposed_duration <= 48:
            return None
        return {'asset_id':asset,'start':proposed_start,'duration_hours':proposed_duration,
                'planner_model':cfg['model']}
    except (KeyError,TypeError,ValueError,IndexError) as exc:
        raise LocalPlannerError(f'Malformed local model tool call: {exc}') from exc
