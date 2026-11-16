/* GasGraph AI. All analysis is computed on the local synthetic Python backend. */
'use strict';
const $ = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const state = { data: null, report: null, selected: 'T-WEST', route: 'overview', activeScenario: 'west', askBusy: false, busy: false, pendingOrder: null };
const TYPES = ['source', 'pipeline', 'terminal', 'meter', 'junction', 'compressor', 'storage', 'offtake'];
const q = (node, selector) => node.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
let toastTimer;
function toast(message, error = false) { const el = $('toast'); el.textContent = message; el.className = 'toast show' + (error ? ' error' : ''); clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.className = 'toast'; }, 3900); }
async function api(path, body) { const options = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }; const res = await fetch('/api/' + path, options); let content = await res.json(); if (!res.ok)
    throw new Error(content.error || 'Server error'); return content; }
function nodeById(id) { return state.data?.network.assets.find(a => a.id === id); }
function setRoute(route) { state.route = route; document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.route === route)); document.querySelectorAll('.view').forEach(v => v.classList.toggle('hidden', v.id !== 'view-' + route)); $('breadcrumb').textContent = ({ overview: 'Overview', agent: 'Agent studio', ontology: 'Ontology explorer', activity: 'Activity & audit' })[route] || route; if (route === 'activity')
    refreshActivity(); if (route === 'ontology')
    renderCatalog(); window.scrollTo({ top: 0, behavior: 'smooth' }); }
function populate() {
    const d = state.data;
    $('kpiAssets').textContent = d.network.assets.length;
    $('kpiRelations').textContent = d.network.relationships.length;
    $('kpiJobs').textContent = d.jobs.length;
    const publicDemo = d.environment.startsWith('PUBLIC');
    if (publicDemo) {
        document.querySelector('.demo-tag').textContent = 'PUBLIC · SYNTHETIC · READ-ONLY';
        $('resetSession').disabled = true;
        $('resetSession').title = 'Reset is available in local mode only';
        $('resetSession').textContent = 'Read-only public preview';
    }
    const hasLlm = d.engine.includes('Local LLM');
    $('agentModeTitle').textContent = hasLlm ? 'LOCAL LLM TOOL PLANNER' : 'DETERMINISTIC AGENT';
    $('agentModeDescription').textContent = hasLlm ? 'Local model selects validated tools · Backend computes outcomes' : 'Real tool execution · No remote model calls';
    $('agentModeBadge').textContent = hasLlm ? 'LOCAL LLM' : 'RULE ROUTER';
    $('assetSelect').innerHTML = d.network.assets.map(a => `<option value="${esc(a.id)}">${esc(a.label)} · ${esc(a.id)}</option>`).join('');
    $('scenarioSelect').innerHTML = d.scenarios.map(s => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('') + '<option value="custom">Custom analysis</option>';
    $('sidebarScenarios').innerHTML = d.scenarios.map((s, i) => `<button class="sidebar-scenario" data-scenario="${esc(s.id)}"><span class="side-dot"></span>${esc(s.name)}</button>`).join('');
    $('typeFilter').innerHTML = '<option value="all">All entity types</option>' + TYPES.map(t => `<option value="${t}">${t.charAt(0).toUpperCase() + t.slice(1)}</option>`).join('');
    $('typeChips').innerHTML = d.network.ontology.entity_types.map(t => `<span>${esc(t)}</span>`).join('');
    $('ontologyRules').innerHTML = d.network.ontology.rules.map(r => `<div class="schema-rule">${esc(r)}</div>`).join('');
    applyScenario('west', false);
    renderGraph();
    renderCatalog();
    refreshActivity();
}
function applyScenario(id, run = false) {
    const s = state.data.scenarios.find(x => x.id === id);
    if (!s)
        return;
    state.activeScenario = id;
    state.selected = s.asset_id;
    $('scenarioSelect').value = id;
    $('assetSelect').value = s.asset_id;
    $('startInput').value = s.start;
    $('durationSelect').value = String(s.duration_hours);
    document.querySelectorAll('.sidebar-scenario').forEach(el => el.classList.toggle('active', el.dataset.scenario === id));
    renderGraph();
    renderNodeDetails();
    if (run) {
        setRoute('overview');
        analyze();
    }
}
function markCustom() { state.activeScenario = 'custom'; $('scenarioSelect').value = 'custom'; document.querySelectorAll('.sidebar-scenario').forEach(el => el.classList.remove('active')); }
function selectNode(id, updateSelect = true) { state.selected = id; if (updateSelect) {
    $('assetSelect').value = id;
    markCustom();
} renderNodeDetails(); renderGraph(); }
function renderNodeDetails() { const a = nodeById(state.selected); if (!a)
    return; $('nodeName').textContent = a.label; $('nodeType').textContent = a.type.toUpperCase(); $('nodeCapacity').textContent = a.capacity + ' demo units/h'; $('nodeStatus').textContent = a.status.toUpperCase(); $('nodeStatus').className = a.status === 'Operational' ? 'ok' : 'warn'; $('nodeIncoming').textContent = state.data.network.relationships.filter(e => e.target === a.id).length; $('nodeOutgoing').textContent = state.data.network.relationships.filter(e => e.source === a.id).length; $('nodeClass').textContent = a.type.toUpperCase(); $('nodeDescription').textContent = a.description + ' · All attributes are invented for demonstration.'; $('selectedClass').textContent = a.data_classification; }
function svg(tag, attrs = {}, text) { const el = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs))
    el.setAttribute(k, String(v)); if (text !== undefined)
    el.textContent = text; return el; }
function pathLine(a, b) {
    const dx = b.x - a.x, dy = b.y - a.y;
    const len = Math.hypot(dx, dy) || 1;
    const ux = dx / len, uy = dy / len;
    const x1 = a.x + ux * 21, y1 = a.y + uy * 21, x2 = b.x - ux * 23, y2 = b.y - uy * 23;
    // Smooth bend for long, angled connections; keeps flow direction clear.
    const bend = Math.abs(dy) > 45 ? Math.sign(dy) * Math.min(28, Math.abs(dy) * .14) : 0;
    return `M ${x1} ${y1} C ${x1 + (x2 - x1) * .47} ${y1 + bend}, ${x2 - (x2 - x1) * .46} ${y2 - bend}, ${x2} ${y2}`;
}
function renderGraph() {
    if (!state.data)
        return;
    const root = $('networkGraph');
    root.replaceChildren();
    const defs = svg('defs');
    const marker = svg('marker', { id: 'arrowHead', markerWidth: 8, markerHeight: 8, refX: 6, refY: 3, orient: 'auto', markerUnits: 'userSpaceOnUse' });
    marker.append(svg('path', { d: 'M0 0L6 3L0 6', fill: 'none', stroke: '#5b8ca3', 'stroke-width': 1.5 }));
    defs.append(marker);
    root.append(defs);
    const assets = state.data.network.assets, edges = state.data.network.relationships;
    const byId = Object.fromEntries(assets.map(a => [a.id, a]));
    let paths = state.report?.dependencies?.paths || {};
    const focus = state.selected;
    const downstream = new Set(state.report?.asset.id === focus ? state.report?.dependencies?.downstream : []);
    const alternate = new Set(state.report?.asset.id === focus ? state.report?.impact?.alternate_path_possible : []);
    for (const e of edges) {
        const a = byId[e.source], b = byId[e.target];
        let kind = '';
        if (state.report?.asset.id === focus) {
            if (e.source === focus || downstream.has(e.source)) {
                if (downstream.has(e.target))
                    kind = 'highlight';
            }
            if (alternate.has(e.target) && alternate.has(e.source))
                kind = 'alternative';
        }
        const p = svg('path', { d: pathLine(a, b), class: 'edge-path ' + kind, 'marker-end': 'url(#arrowHead)', 'data-from': e.source, 'data-to': e.target });
        root.append(p);
    }
    for (const a of assets) {
        const g = svg('g', { class: 'graph-node type-' + a.type + (a.id === focus ? ' selected' : '') + (downstream.has(a.id) ? ' impacted' : '') + (alternate.has(a.id) ? ' alternate' : ''), role: 'button', tabindex: '0', 'aria-label': `${a.label}, ${a.type}, select for analysis`, 'data-id': a.id });
        g.append(svg('circle', { cx: a.x, cy: a.y, r: 29, class: 'node-halo' }));
        g.append(svg('circle', { cx: a.x, cy: a.y, r: 19, class: 'node-core' }));
        let icon;
        if (a.type === 'terminal') {
            icon = svg('path', { d: `M${a.x - 8} ${a.y + 7}v-15l8-5 8 5v15z M${a.x - 3} ${a.y + 2}h6 M${a.x - 3} ${a.y - 4}h6`, class: 'node-inner', fill: 'none', stroke: '#ddfcf4', 'stroke-width': 2, 'stroke-linejoin': 'round' });
        }
        else if (a.type === 'source') {
            icon = svg('path', { d: `M${a.x - 8} ${a.y + 7}l8-15 8 15z`, class: 'node-inner' });
        }
        else if (a.type === 'pipeline') {
            icon = svg('path', { d: `M${a.x - 10} ${a.y}h20 M${a.x - 5} ${a.y - 5}v10 M${a.x + 5} ${a.y - 5}v10`, stroke: '#cde6fa', 'stroke-width': 3, 'stroke-linecap': 'round' });
        }
        else if (a.type === 'meter') {
            icon = svg('path', { d: `M${a.x - 9} ${a.y + 3}a9 9 0 0 1 18 0M${a.x} ${a.y + 3}l6-8M${a.x - 10} ${a.y + 6}h20`, stroke: '#cde6fa', 'stroke-width': 2.1 });
        }
        else if (a.type === 'junction') {
            icon = svg('path', { d: `M${a.x - 10} ${a.y}h20M${a.x} ${a.y - 10}v20`, stroke: '#cde6fa', 'stroke-width': 3 });
        }
        else if (a.type === 'storage') {
            icon = svg('path', { d: `M${a.x - 9} ${a.y - 7}h18v14h-18z M${a.x - 9} ${a.y - 1}h18`, stroke: '#e5d8ff', 'stroke-width': 2 });
        }
        else if (a.type === 'compressor') {
            icon = svg('path', { d: `M${a.x - 8} ${a.y - 8}L${a.x + 8} ${a.y} ${a.x - 8} ${a.y + 8}z`, class: 'node-inner' });
        }
        else
            icon = svg('circle', { cx: a.x, cy: a.y, r: 6, class: 'node-inner' });
        g.append(icon);
        const shortLabels = { 'SRC-N': 'North inlet', 'SRC-S': 'South inlet', 'T-WEST': 'Westhaven', 'T-EAST': 'Eastport', 'T-SOUTH': 'Southbay', 'J-CENT': 'Central hub', 'J-SOUTH': 'South hub', 'C-201': 'Compressor', 'STOR-01': 'Boreal store', 'OFF-EAST': 'East grid', 'OFF-SOUTH': 'South grid' };
        const labelText = shortLabels[a.id] || (a.type === 'pipeline' || a.type === 'meter' ? a.id : a.label.slice(0, 12));
        const label = svg('text', { x: a.x, y: a.y + 37, class: 'node-label' }, labelText);
        g.append(label);
        if (shortLabels[a.id])
            g.append(svg('text', { x: a.x, y: a.y + 48, class: 'node-id' }, a.id));
        g.addEventListener('click', () => selectNode(a.id));
        g.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            selectNode(a.id);
        } });
        g.append(svg('title', {}, `${a.label}\n${a.description}\n${a.id}`));
        root.append(g);
    }
}
async function analyze() { if (state.busy)
    return; state.busy = true; const btn = $('analyzeBtn'); const old = btn.innerHTML; btn.disabled = true; btn.textContent = 'Analyzing synthetic topology…'; try {
    const body = { asset_id: $('assetSelect').value, start: $('startInput').value, duration_hours: Number($('durationSelect').value) };
    if (!body.start)
        throw Error('Please select a start time');
    const report = await api('analyze', body);
    state.report = report;
    state.selected = report.asset.id;
    renderReport(report);
    toast('Analysis completed · ' + report.analysis_id);
}
catch (e) {
    toast(e.message, true);
}
finally {
    btn.disabled = false;
    btn.innerHTML = old;
    state.busy = false;
} }
function renderReport(report) { $('resultRunId').textContent = report.analysis_id; $('riskScore').textContent = String(report.score.value); $('riskLabel').textContent = report.score.label; $('riskLabel').className = 'risk-tag ' + report.score.label.toLowerCase(); $('gaugeArc').setAttribute('stroke-dashoffset', String(120 - report.score.value / 100 * 120)); $('gaugeArc').setAttribute('stroke', report.score.value >= 65 ? '#f0b17b' : report.score.value >= 35 ? '#e4d68d' : '#75e0c1'); $('affectedCount').textContent = report.impact.affected_count; $('conflictCount').textContent = report.schedule.conflicts.length; $('alternateCount').textContent = report.impact.redundant_path_count; renderGraph(); renderNodeDetails(); renderFindings(report); renderOrder(report.draft_order); }
function renderFindings(report) {
    const c = report.schedule.conflicts, imp = report.impact;
    const summary = `${esc(report.asset.label)} has <strong>${imp.affected_count} downstream dependencies</strong>. Removing it from the fictional graph makes ${imp.newly_unreachable_count} entities source-unreachable; ${imp.redundant_path_count} still have at least one topological alternative path. This does not establish operational capacity.`;
    const itemHTML = c.length ? c.map(j => `<div class="path-item"><div><strong>${esc(j.id)} · ${esc(j.title)}</strong><div style="margin-top:4px;color:#809aaa;font-size:9px">${esc(j.dependency_path.join(' → '))}</div></div><small style="color:${j.classification === 'direct' ? '#f1b390' : '#9cdec4'}">${j.classification === 'direct' ? 'DIRECT' : 'REVIEW'}</small></div>`).join('') : '<div class="path-item">No overlapping work found in the selected time window. <small>0 items</small></div>';
    const pathIds = Object.keys(report.dependencies.paths).slice(0, 3);
    const evidenceHTML = pathIds.map(id => `<div class="path-item"><strong>${esc(id)}</strong><span style="font-size:9px;color:#879ca8">${esc(report.dependencies.paths[id].join(' → '))}</span></div>`).join('');
    $('findingsContent').innerHTML = `<div class="finding-summary"><svg><use href="#ic-link"></use></svg><div><strong>Path-based impact assessment</strong><p>${summary}</p></div></div><div class="finding-grid"><div class="finding-box"><span>TOPOLOGY-UNREACHABLE</span><strong>${imp.newly_unreachable_count}</strong><p>Reachability after hypothetical node removal</p></div><div class="finding-box"><span>SCHEDULING FINDINGS</span><strong>${c.length}</strong><p>${report.schedule.direct_count} direct overlaps · ${report.schedule.coordination_count} coordination reviews</p></div></div><div style="font-size:10px;letter-spacing:1px;color:#91b8b9;font-weight:750;margin-top:15px">CONFLICT EVIDENCE</div><div class="path-list">${itemHTML}</div><div style="font-size:10px;letter-spacing:1px;color:#91b8b9;font-weight:750;margin-top:17px">EXAMPLE DEPENDENCY PATHS</div><div class="path-list">${evidenceHTML || '<div class="path-item">No downstream dependencies found.</div>'}</div>`;
}
function renderOrder(order) {
    const approved = order.approval_status === 'Approved in demo only';
    const blocked = !!order.blocked;
    $('orderContent').innerHTML = `<div class="order-card"><div class="order-card-header"><strong>${esc(order.id)}</strong><span class="${approved ? 'approved' : ''}">${approved ? 'DEMO APPROVED' : blocked ? 'BLOCKED · DIRECT CONFLICT' : 'DRAFT · REVIEW'}</span></div><div class="order-meta"><div><span>ASSET</span><strong>${esc(order.asset_label)}</strong></div><div><span>WORK WINDOW</span><strong>${esc(order.requested_window.start.replace('T', ' '))}</strong></div><div><span>STATUS</span><strong>${approved ? 'Locally approved' : blocked ? 'Window change required' : 'Human review required'}</strong></div><div><span>INTEGRATION</span><strong>No external systems</strong></div></div>${approved ? '<div class="order-meta"><strong style="color:#92e6c4">Approval stored in demo memory only.</strong></div>' : blocked ? '<div class="order-blocked">Direct same-asset overlap detected. Choose a different time window before approval.</div>' : state.data?.environment.startsWith('PUBLIC') ? '<div class="order-blocked">Public preview: proposed actions are read-only. Use the local app to test simulated approvals.</div>' : `<button class="primary-btn order-action" id="openApprove" data-order="${esc(order.id)}"><svg><use href="#ic-shield"></use></svg> Review & approve (demo only)</button>`}</div>`;
    const button = $('openApprove');
    if (button)
        button.addEventListener('click', () => openModal(order.id));
}
function openModal(order) { state.pendingOrder = order; $('reviewerInput').value = ''; $('approvalConfirm').checked = false; $('approvalModal').classList.remove('hidden'); $('reviewerInput').focus(); }
function closeModal() { $('approvalModal').classList.add('hidden'); state.pendingOrder = null; }
async function approve() { const reviewer = $('reviewerInput').value.trim(); if (!reviewer || !$('approvalConfirm').checked) {
    toast('Enter a reviewer name and confirm the demo-only restriction.', true);
    return;
} try {
    const result = await api('approve', { order_id: state.pendingOrder, reviewer, confirmed: true });
    closeModal();
    if (state.report && state.report.draft_order.id === result.order.id) {
        state.report.draft_order = result.order;
        renderOrder(result.order);
    }
    toast('Local demo approval recorded. No physical action was performed.');
}
catch (e) {
    toast(e.message, true);
} }
function setPrompt(text) { setRoute('agent'); $('questionInput').value = text; $('questionInput').focus(); }
async function ask(question) { if (state.askBusy)
    return; state.askBusy = true; appendChat('user', question); $('questionInput').value = ''; const send = q($('askForm'), 'button'); send.disabled = true; try {
    const result = await api('ask', { question, start: $('startInput').value || '2027-07-13T09:00', duration_hours: Number($('durationSelect').value || 4) });
    appendChat('assistant', result.message);
    renderTrace(result.tool_trace);
    if (result.analysis) {
        state.report = result.analysis;
        state.selected = result.analysis.asset.id;
        $('assetSelect').value = state.selected;
        renderReport(state.report);
    }
}
catch (e) {
    appendChat('assistant', 'The demo could not process this query: ' + e.message);
    toast(e.message, true);
}
finally {
    state.askBusy = false;
    send.disabled = false;
} }
function appendChat(role, text) { const el = document.createElement('div'); el.className = 'chat-message ' + role; el.innerHTML = `<div class="chat-avatar"><svg><use href="#${role === 'user' ? 'ic-grid' : 'ic-spark'}"></use></svg></div><div class="chat-bubble">${role === 'assistant' ? '<strong>Network intelligence assistant</strong>' : ''}<p>${esc(text)}</p></div>`; $('messages').append(el); $('messages').scrollTop = $('messages').scrollHeight; }
function renderTrace(trace) { $('agentTrace').innerHTML = trace?.length ? trace.map((s, i) => `<div class="tool-step"><span class="tool-step-icon"><svg><use href="#ic-${i === trace.length - 1 ? 'check' : 'code'}"></use></svg></span><div><strong>${esc(s.tool)}</strong><p>${esc(s.result)}</p></div></div>`).join('') : '<div class="empty-state">No tools executed.</div>'; }
function renderCatalog() { if (!state.data)
    return; const type = $('typeFilter').value, term = $('catalogSearch').value.trim().toLowerCase(); const arr = state.data.network.assets.filter(a => (type === 'all' || a.type === type) && (`${a.id} ${a.label} ${a.type}`.toLowerCase().includes(term))); $('catalogRows').innerHTML = arr.length ? arr.map(a => `<button class="catalog-row" data-asset="${esc(a.id)}"><span class="id">${esc(a.id)}</span><span>${esc(a.label)}</span><span class="type">${esc(a.type)}</span><span class="status">${esc(a.status)}</span></button>`).join('') : '<div class="empty-state">No matching assets.</div>'; }
async function refreshActivity() { if (!state.data)
    return; try {
    const result = await api('bootstrap');
    state.data.audit = result.audit;
    const audit = result.audit || [];
    $('auditRows').innerHTML = audit.length ? audit.map(e => `<div class="audit-row"><div class="audit-icon"><svg><use href="#ic-${e.action === 'DEMO_APPROVAL' ? 'shield' : e.action === 'AGENT_QUERY' ? 'spark' : 'activity'}"></use></svg></div><div><strong>${esc(e.action.replaceAll('_', ' '))}</strong><p>${esc(e.detail)}</p><time>${esc(e.at.replace('T', ' ').replace('+00:00', ' UTC'))}</time></div></div>`).join('') : '<div class="empty-state">No activity logged in this local demo session.</div>';
}
catch (e) {
    toast(e.message, true);
} }
function exportReport() { if (!state.report) {
    toast('Run an analysis before exporting.', true);
    return;
} const blob = new Blob([JSON.stringify({ notice: 'INDEPENDENT DEMO — SYNTHETIC DATA ONLY', exported_at: new Date().toISOString(), report: state.report }, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'gasgraph-' + state.report.analysis_id.toLowerCase() + '.json'; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 500); toast('Synthetic analysis exported as JSON'); }
function bind() {
    document.querySelectorAll('[data-route]').forEach(el => el.addEventListener('click', () => setRoute(el.dataset.route)));
    $('sidebarScenarios').addEventListener('click', e => { const el = e.target.closest('[data-scenario]'); if (el)
        applyScenario(el.dataset.scenario, true); });
    $('scenarioSelect').addEventListener('change', e => { if (e.target.value !== 'custom')
        applyScenario(e.target.value, false);
    else
        markCustom(); });
    $('assetSelect').addEventListener('change', e => selectNode(e.target.value, true));
    $('startInput').addEventListener('change', markCustom);
    $('durationSelect').addEventListener('change', markCustom);
    $('graphResetBtn').addEventListener('click', () => { state.report = null; renderGraph(); toast('Cleared highlighted paths; the saved analysis remains in session history'); });
    $('analyzeBtn').addEventListener('click', analyze);
    $('heroRun').addEventListener('click', () => { $('analyzeBtn').scrollIntoView({ behavior: 'smooth', block: 'center' }); analyze(); });
    $('heroAgent').addEventListener('click', () => setRoute('agent'));
    $('runSelected').addEventListener('click', () => { $('assetSelect').value = state.selected; analyze(); });
    $('viewFindingsBtn').addEventListener('click', () => q(document, '.findings-panel').scrollIntoView({ behavior: 'smooth', block: 'start' }));
    $('exportBtn').addEventListener('click', exportReport);
    $('askForm').addEventListener('submit', e => { e.preventDefault(); const text = $('questionInput').value.trim(); if (text)
        ask(text); });
    document.querySelectorAll('[data-prompt]').forEach(el => el.addEventListener('click', () => { const text = el.dataset.prompt; setPrompt(text); ask(text); }));
    $('catalogSearch').addEventListener('input', renderCatalog);
    $('typeFilter').addEventListener('change', renderCatalog);
    $('catalogRows').addEventListener('click', e => { const el = e.target.closest('[data-asset]'); if (el) {
        selectNode(el.dataset.asset);
        setRoute('overview');
    } });
    $('refreshActivity').addEventListener('click', refreshActivity);
    $('resetSession').addEventListener('click', async () => { if (!window.confirm('Reset local demo session, approvals and audit history?'))
        return; try {
        await api('reset', {});
        state.report = null;
        applyScenario('west', false);
        $('riskScore').textContent = '—';
        $('riskLabel').textContent = 'No analysis';
        $('affectedCount').textContent = '—';
        $('conflictCount').textContent = '—';
        $('alternateCount').textContent = '—';
        $('resultRunId').textContent = '—';
        $('findingsContent').innerHTML = '<div class="empty-state">Run an analysis to inspect evidence paths.</div>';
        $('orderContent').innerHTML = '<div class="empty-state">No work order yet.</div>';
        await refreshActivity();
        toast('Local demo session reset');
    }
    catch (e) {
        toast(e.message, true);
    } });
    $('cancelApproval').addEventListener('click', closeModal);
    $('modalBackdrop').addEventListener('click', closeModal);
    $('confirmApproval').addEventListener('click', approve);
    document.addEventListener('keydown', e => { if (e.key === 'Escape')
        closeModal(); });
}
async function init() { try {
    state.data = await api('bootstrap');
    populate();
    bind();
    if (state.data.current) {
        state.report = state.data.current;
        state.selected = state.report.asset.id;
        renderReport(state.report);
    }
    else {
        await analyze();
    }
}
catch (e) {
    document.querySelector('#content').insertAdjacentHTML('afterbegin', `<div class="empty-state" style="margin-bottom:20px;color:#ffb1b1">Could not load backend: ${esc(e.message)}. Start with <code>python -m gasgraph.server</code> from the project folder.</div>`);
    toast('Backend connection failed: ' + e.message, true);
} }
document.addEventListener('DOMContentLoaded', init);
