"""Deterministic, testable business tools over a synthetic gas-network ontology.

SAFETY: This is a non-operational demonstration. Graph reachability does not
represent hydraulic flow, availability guarantees or operational safety.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import re

DATA_DIR = Path(__file__).resolve().parents[1] / 'data'


def load_json(name: str) -> Any:
    return json.loads((DATA_DIR / name).read_text(encoding='utf-8'))


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec='minutes')


def parse_time(value: str) -> datetime:
    # Demo only: local, naïve times in an explicitly fictional future schedule.
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        raise ValueError('Use local date-time without UTC offset for this demonstration')
    return dt


class NetworkEngine:
    """Read-only topology analysis. Mutations belong to DemoSession approval workflow."""

    def __init__(self, network: dict | None = None, jobs: list | None = None):
        self.network = network or load_json('network.json')
        self.jobs = jobs if jobs is not None else load_json('jobs.json')
        self.assets = {a['id']: a for a in self.network['assets']}
        self.edges = self.network['relationships']
        self.forward: dict[str, list[str]] = {aid: [] for aid in self.assets}
        self.backward: dict[str, list[str]] = {aid: [] for aid in self.assets}
        for e in self.edges:
            if e['source'] not in self.assets or e['target'] not in self.assets:
                raise ValueError(f'Invalid relationship endpoint: {e}')
            self.forward[e['source']].append(e['target'])
            self.backward[e['target']].append(e['source'])
        self.sources = list(self.network['sources'])

    def _walk(self, start: str, blocked: set[str] | None = None) -> dict[str, list[str]]:
        blocked = blocked or set()
        if start in blocked:
            return {}
        paths = {start: [start]}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for nxt in self.forward[node]:
                if nxt not in paths and nxt not in blocked:
                    paths[nxt] = paths[node] + [nxt]
                    queue.append(nxt)
        return paths

    def find_dependencies(self, asset_id: str) -> dict:
        """Return reachable downstream entities and an exact evidence path to each."""
        if asset_id not in self.assets:
            raise ValueError(f'Unknown synthetic asset: {asset_id}')
        paths = self._walk(asset_id)
        impacted = [key for key in paths if key != asset_id]
        return {'asset_id': asset_id,
                'direct': list(self.forward[asset_id]),
                'downstream': impacted,
                'paths': {key: paths[key] for key in impacted},
                'relationship_type': 'FLOWS_TO',
                'analysis_limit':'Topological dependencies only; no hydraulic simulation.'}

    def _available_sources(self, excluded: set[str]) -> set[str]:
        reachable = set()
        for source in self.sources:
            reachable.update(self._walk(source, blocked=excluded))
        return reachable

    def check_maintenance_conflicts(self, asset_id: str, start: str, duration_hours: float) -> dict:
        if asset_id not in self.assets:
            raise ValueError(f'Unknown synthetic asset: {asset_id}')
        st = parse_time(start)
        en = st + timedelta(hours=duration_hours)
        dependency = self.find_dependencies(asset_id)
        reachable = set(dependency['downstream'])
        conflicts = []
        for job in self.jobs:
            js, je = parse_time(job['start']), parse_time(job['end'])
            if st >= je or js >= en:  # touching endpoints is not a conflict
                continue
            target = job['asset_id']
            if target == asset_id:
                level, reason = 'direct', 'Same asset and overlapping time window.'
                path = [asset_id]
            elif target in reachable:
                level, reason = 'coordination', 'Overlapping work on a downstream dependency; review required.'
                path = dependency['paths'][target]
            elif asset_id in self._walk(target):
                level, reason = 'coordination', 'Overlapping work on an upstream dependency; review required.'
                path = self._walk(target)[asset_id]
            else:
                continue
            conflicts.append({**job,'classification':level,'reason':reason,'dependency_path':path})
        conflicts.sort(key=lambda c:(c['classification']!='direct',c['start'],c['id']))
        return {'asset_id':asset_id,'start':iso(st),'end':iso(en),
                'conflicts':conflicts,
                'direct_count':sum(c['classification']=='direct' for c in conflicts),
                'coordination_count':sum(c['classification']=='coordination' for c in conflicts)}

    def analyze_maintenance(self, asset_id: str, start: str, duration_hours: float = 4) -> dict:
        if not isinstance(duration_hours,(int,float)) or not 0.5 <= duration_hours <= 48:
            raise ValueError('Duration must be between 0.5 and 48 hours')
        st = parse_time(start)
        if st.year < 2026 or st.year > 2035:
            raise ValueError('Demo schedule must be between years 2026 and 2035')
        if asset_id not in self.assets:
            raise ValueError(f'Unknown synthetic asset: {asset_id}')
        asset = self.assets[asset_id]
        deps = self.find_dependencies(asset_id)
        scheduling = self.check_maintenance_conflicts(asset_id, start, duration_hours)
        baseline = self._available_sources(set())
        after = self._available_sources({asset_id})
        # Only assets that were previously source-reachable can be newly unserved.
        newly_unreachable = [a for a in deps['downstream'] if a in baseline and a not in after]
        alternate = [a for a in deps['downstream'] if a in after]
        potential = list(deps['downstream'])
        # This is a pedagogical demo score, NOT an engineering risk score.
        score = min(95, 12 + len(potential)*3 + scheduling['direct_count']*19 + scheduling['coordination_count']*7 + len(newly_unreachable)*3)
        if score >= 65:
            severity = 'Elevated'
        elif score >= 35:
            severity = 'Moderate'
        else:
            severity = 'Low'
        order_id = 'WO-' + sha256(f'{asset_id}|{iso(st)}|{duration_hours:g}'.encode()).hexdigest()[:9].upper()
        draft = {'id':order_id,'asset_id':asset_id,'asset_label':asset['label'],
                 'requested_window':{'start':iso(st),'end':scheduling['end']},
                 'description':f'Assess and plan synthetic maintenance intervention on {asset["label"]}.',
                 'checks':[ 'Confirm technical isolation and real-world constraints outside this demo',
                            'Review overlapping and downstream maintenance dependencies',
                            'Obtain human authorization through an approved operational workflow'],
                 'approval_status':('Blocked — direct scheduling overlap' if scheduling['direct_count'] else 'Draft — not sent to any operational system'),
                 'blocked':bool(scheduling['direct_count']),
                 'blocking_job_ids':[j['id'] for j in scheduling['conflicts'] if j['classification']=='direct'],
                 'synthetic_only':True}
        return {
            'analysis_id':'AN-'+sha256(order_id.encode()).hexdigest()[:9].upper(),
            'asset':asset,'window':{'start':iso(st),'end':scheduling['end']},
            'dependencies':deps,'schedule':scheduling,
            'impact':{'potentially_affected':potential,'alternate_path_possible':alternate,
                      'newly_unreachable_in_topology':newly_unreachable,
                      'affected_count':len(potential),'newly_unreachable_count':len(newly_unreachable),
                      'redundant_path_count':len(alternate)},
            'score':{'value':score,'label':severity,
                     'method':'Illustrative index: downstream reach + overlapping jobs + source reachability. Not an engineering or safety assessment.'},
            'draft_order':draft,
            'tool_trace':[
                {'tool':'ontology.resolve_entity','result':f'{asset["label"]} ({asset_id}) resolved'},
                {'tool':'graph.find_dependencies','result':f'{len(potential)} downstream assets with evidence paths'},
                {'tool':'schedule.check_conflicts','result':f'{scheduling["direct_count"]} direct, {scheduling["coordination_count"]} coordination reviews'},
                {'tool':'workflow.draft_work_order','result':f'{order_id}: DRAFT; no external action'}],
            'caveat':'Fictional data. Reachability is not gas-flow simulation. A possible alternate route is not proof of capacity or safety.'
        }

    def resolve_asset(self, query: str) -> dict | None:
        text = re.sub(r'[^a-z0-9]+',' ',query.lower()).strip()
        if not text:
            return None
        for a in self.assets.values():
            if a['id'].lower() in query.lower() or a['label'].lower() in query.lower():
                return a
        # Useful shorthand aliases, intentionally finite to avoid silent hallucinations.
        aliases = {'westhaven':'T-WEST','western terminal':'T-WEST','west terminal':'T-WEST',
                   'terminal a':'T-WEST','østterminal':'T-EAST','eastport':'T-EAST',
                   'southbay':'T-SOUTH','south terminal':'T-SOUTH','compressor':'C-201',
                   'kompressor':'C-201','south meter':'M-320','meter 320':'M-320',
                   'south grid':'OFF-SOUTH','central exchange':'J-CENT','boreal storage':'STOR-01'}
        for alias, aid in aliases.items():
            if alias in text:
                return self.assets[aid]
        return None

    def ask(self, question: str, start: str = '2027-07-13T09:00', duration_hours: float = 4) -> dict:
        """Auditable deterministic tool router (not an LLM). Does not pretend to understand every question."""
        if not question or len(question) > 600:
            raise ValueError('Question must contain 1–600 characters')
        asset = self.resolve_asset(question)
        if not asset:
            return {'mode':'deterministic-tool-router','understood':False,
                    'message':'I could not resolve an asset in this synthetic ontology. Select an asset or mention its ID/name.',
                    'available_assets':[{'id':a['id'],'label':a['label']} for a in list(self.assets.values())[:8]],
                    'tool_trace':[{'tool':'ontology.resolve_entity','result':'No asset matched; no analysis executed'}]}
        analysis = self.analyze_maintenance(asset['id'],start,duration_hours)
        names = [self.assets[aid]['label'] for aid in analysis['impact']['newly_unreachable_in_topology'][:4]]
        summary = f"{asset['label']} has {analysis['impact']['affected_count']} potentially dependent downstream assets. "
        summary += f"{analysis['impact']['newly_unreachable_count']} become unreachable from the synthetic sources when this node is removed. "
        summary += f"Review {analysis['schedule']['direct_count']} direct overlaps and {analysis['schedule']['coordination_count']} dependency-based coordination items. "
        if names:
            summary += f"Example unreachable nodes: {', '.join(names)}. "
        summary += 'A draft work order is ready for human review; no real actions are performed.'
        return {'mode':'deterministic-tool-router','understood':True,'message':summary,'analysis':analysis,
                'tool_trace':analysis['tool_trace']}
