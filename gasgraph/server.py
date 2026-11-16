"""Single-command, dependency-free local demonstration server."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit

from gasgraph.engine import NetworkEngine, load_json
from gasgraph.llm import config as llm_config, plan_with_local_llm, LocalPlannerError

WEB_DIR = Path(__file__).resolve().parents[1] / 'web'
CONTENT_TYPES = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8',
                 '.js':'application/javascript; charset=utf-8','.svg':'image/svg+xml',
                 '.png':'image/png','.ico':'image/x-icon','.json':'application/json'}

class DemoSession:
    def __init__(self, engine=None):
        self.engine = engine or NetworkEngine()
        self.lock = threading.RLock()
        self.orders = {}
        self.audit = []
        self.current = None

    def event(self, action, detail):
        self.audit.insert(0,{'at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
                             'action':action,'detail':detail})
        self.audit = self.audit[:100]

    def analyze(self, payload):
        with self.lock:
            report = self.engine.analyze_maintenance(
                str(payload['asset_id']),str(payload['start']),float(payload.get('duration_hours',4)))
            oid = report['draft_order']['id']
            existing = self.orders.get(oid)
            if existing and existing['approval_status'] == 'Approved in demo only':
                report['draft_order']=existing.copy()
            else:
                self.orders[oid]=report['draft_order'].copy()
            self.current=report
            self.event('ANALYSIS',f"{report['asset']['id']} · {report['analysis_id']}")
            return report

    def ask(self,payload):
        with self.lock:
            question=str(payload['question'])
            start=str(payload.get('start','2027-07-13T09:00'))
            duration=float(payload.get('duration_hours',4))
            # Try optional local LLM *only* when explicitly configured.
            # It chooses a tool; the deterministic engine alone produces facts.
            plan=None
            planner_notice=None
            if llm_config():
                try:
                    plan=plan_with_local_llm(question,list(self.engine.assets.values()),start,duration)
                except LocalPlannerError as exc:
                    planner_notice=str(exc)
            if plan:
                report=self.engine.analyze_maintenance(plan['asset_id'],plan['start'],plan['duration_hours'])
                imp=report['impact']
                msg=(f"Local LLM selected {report['asset']['label']} for synthetic maintenance analysis. "
                     f"{imp['affected_count']} assets are potentially dependent; "
                     f"{imp['newly_unreachable_count']} become topologically unreachable. "
                     f"{len(report['schedule']['conflicts'])} overlapping jobs need review. "
                     "A work-order draft requires human review and cannot reach operational systems.")
                trace=[{'tool':'local_llm.select_tool','result':f"{plan['planner_model']} selected validated asset {plan['asset_id']}"}]+report['tool_trace']
                result={'mode':'local-llm-tool-planner','understood':True,'message':msg,
                        'analysis':report,'tool_trace':trace}
            else:
                result=self.engine.ask(question,start,duration)
                if planner_notice:
                    result['planner_notice']=planner_notice
                if llm_config() and not planner_notice:
                    result['planner_notice']='Local model did not select a supported tool; used deterministic resolver.'
            self.event('AGENT_QUERY', ('Local LLM tool selection' if plan else 'Rule router') + (' · resolved' if result['understood'] else ' · unresolved'))
            if result.get('analysis'):
                report=result['analysis']
                oid=report['draft_order']['id']
                self.orders.setdefault(oid,report['draft_order'].copy())
                if self.orders[oid]['approval_status']=='Approved in demo only':
                    report['draft_order']=self.orders[oid].copy()
                self.current=report
            return result

    def approve(self,payload):
        with self.lock:
            oid = str(payload.get('order_id',''))
            reviewer=str(payload.get('reviewer','')).strip()
            if oid not in self.orders:
                raise ValueError('Unknown demo work order')
            if not 2 <= len(reviewer) <= 80:
                raise ValueError('Reviewer name must contain 2–80 characters')
            if payload.get('confirmed') is not True:
                raise ValueError('Explicit confirmation is required')
            order=self.orders[oid]
            if order.get('blocked'):
                raise ValueError('Approval blocked: direct scheduling conflict. Choose a non-overlapping window first.')
            order['approval_status']='Approved in demo only'
            order['approved_by']=reviewer
            order['approved_at']=datetime.now(timezone.utc).isoformat(timespec='seconds')
            self.event('DEMO_APPROVAL',f'{oid} · {reviewer}; no external system contacted')
            if self.current and self.current['draft_order']['id']==oid:
                self.current['draft_order']=order.copy()
            return {'order':order,'message':'Recorded local demo approval. No field systems or external APIs contacted.'}

    def reset(self):
        with self.lock:
            self.orders.clear(); self.audit.clear(); self.current=None
            self.event('RESET','Local demo state reset')
            return {'ok':True}

    def bootstrap(self):
        with self.lock:
            return {'network':self.engine.network,'jobs':self.engine.jobs,
                    'scenarios':load_json('scenarios.json'),'orders':list(self.orders.values()),
                    'audit':list(self.audit),'current':self.current,
                    'engine':('Local LLM tool planner + deterministic graph' if llm_config() else 'Deterministic graph and rule tools (no hosted LLM calls)'),
                    'version':'1.0.0','environment':'LOCAL / SYNTHETIC'}


def make_handler(session: DemoSession, public_demo: bool = False):
    class Handler(BaseHTTPRequestHandler):
        server_version='GasGraphDemo/1.0'
        def log_message(self,format,*args):
            print('[http]',format % args)
        def _headers(self,status,content_type,length):
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(length))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
        def _send(self,payload,status=200):
            raw=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf-8')
            self._headers(status,'application/json; charset=utf-8',len(raw))
            self.wfile.write(raw)
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/api/bootstrap':
                result = session.bootstrap()
                if public_demo:
                    result.update({'environment':'PUBLIC / SYNTHETIC · READ-ONLY', 'engine':'Deterministic graph and rule tools (public read-only demo)', 'orders':[], 'audit':[], 'current':None})
                return self._send(result)
            if path=='/api/health':
                return self._send({'ok':True,'mode':'synthetic-offline','version':'1.0.0'})
            if path.startswith('/api/'):
                return self._send({'error':'Not found'},404)
            # Restrict file serving to the web directory, no traversal.
            candidate=(WEB_DIR / (path.lstrip('/') or 'index.html')).resolve()
            if not candidate.is_relative_to(WEB_DIR) or not candidate.is_file():
                return self._send({'error':'Not found'},404)
            raw=candidate.read_bytes()
            self._headers(200,CONTENT_TYPES.get(candidate.suffix,'application/octet-stream'),len(raw))
            self.wfile.write(raw)
        def do_POST(self):
            path=urlsplit(self.path).path
            if path not in {'/api/analyze','/api/ask','/api/approve','/api/reset'}:
                return self._send({'error':'Not found'},404)
            if public_demo and path in {'/api/approve','/api/reset'}:
                return self._send({'error':'Public preview is read-only: approval and reset are disabled.'},403)
            try:
                sz=int(self.headers.get('Content-Length','0'))
                if not 0 <= sz <= 15000:
                    return self._send({'error':'Payload too large'},413)
                body=json.loads(self.rfile.read(sz)) if sz else {}
                if not isinstance(body,dict):
                    raise ValueError('Expected a JSON object')
                if path=='/api/analyze':
                    result=DemoSession(session.engine).analyze(body) if public_demo else session.analyze(body)
                elif path=='/api/ask':
                    # Public demo uses deterministic tools, not the optional local LLM.
                    if public_demo:
                        question=str(body['question'])
                        result=session.engine.ask(question,str(body.get('start','2027-07-13T09:00')),float(body.get('duration_hours',4)))
                    else:
                        result=session.ask(body)
                elif path=='/api/approve':
                    result=session.approve(body)
                else:
                    result=session.reset()
                return self._send(result)
            except (ValueError,KeyError,TypeError,OverflowError) as err:
                return self._send({'error':str(err)},400)
    return Handler


def serve(host='127.0.0.1',port=8765,public_demo=False):
    session=DemoSession()
    srv=ThreadingHTTPServer((host,port),make_handler(session,public_demo=public_demo))
    print(f'GasGraph AI running at http://{host}:{port} (synthetic demo only)',flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    finally: srv.server_close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Start the local GasGraph AI dashboard')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--host',default='127.0.0.1',help='Use localhost for the full demo. Public deployment requires --public-demo.')
    parser.add_argument('--public-demo',action='store_true',help='Use stateless read-only public preview: disables approvals and shared audit state')
    args=parser.parse_args()
    if args.host not in {'127.0.0.1','localhost','::1'} and not args.public_demo:
        parser.error('Refusing to bind on a public interface without --public-demo')
    serve(args.host,args.port,args.public_demo)
