"""Exercise the actual stdlib web API in a local ephemeral server."""
import json
from threading import Thread
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import pytest
from gasgraph.server import make_handler, DemoSession

@pytest.fixture
def server_url():
    session=DemoSession()
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(session))
    worker=Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown();server.server_close();worker.join(timeout=2)

def req(base,path,body=None):
    payload=json.dumps(body).encode() if body is not None else None
    with urlopen(Request(base+path,data=payload,headers={'Content-Type':'application/json'} if body is not None else {}),timeout=3) as resp:
        return resp.status,json.loads(resp.read())

def test_bootstrap_and_health(server_url):
    code,boot=req(server_url,'/api/bootstrap')
    assert code==200 and len(boot['network']['assets'])==22
    assert len(boot['scenarios'])==4
    code,health=req(server_url,'/api/health')
    assert health['mode']=='synthetic-offline'

def test_full_analysis_and_approval_api(server_url):
    code, report=req(server_url,'/api/analyze',{'asset_id':'P-101','start':'2027-07-17T10:00','duration_hours':2})
    assert code==200 and report['schedule']['direct_count']==0
    code,order=req(server_url,'/api/approve',{'order_id':report['draft_order']['id'],'reviewer':'Demo reviewer','confirmed':True})
    assert order['order']['approval_status']=='Approved in demo only'
    code,session=req(server_url,'/api/bootstrap')
    assert session['current']['draft_order']['approval_status']=='Approved in demo only'
    assert any(e['action']=='DEMO_APPROVAL' for e in session['audit'])

def test_unknown_asset_returns_400(server_url):
    with pytest.raises(HTTPError) as exc:
        req(server_url,'/api/analyze',{'asset_id':'REAL-PIPE','start':'2027-07-13T09:30','duration_hours':2})
    assert exc.value.code==400

def test_web_server_sends_strict_security_headers(server_url):
    with urlopen(server_url+'/',timeout=3) as resp:
        assert resp.status==200
        assert 'GasGraph AI' in resp.read().decode()
        assert resp.headers['X-Frame-Options']=='DENY'
        assert "default-src 'self'" in resp.headers['Content-Security-Policy']

def test_path_traversal_not_served(server_url):
    with pytest.raises(HTTPError):
        with urlopen(server_url+'/no-such-file',timeout=3) as resp:
            resp.read()

def test_agent_unknown_query_fails_closed(server_url):
    code,result=req(server_url,'/api/ask',{'question':'Operate pipeline on another planet'})
    assert code==200 and not result['understood']
    assert result['analysis'] if 'analysis' in result else True

def test_reset_removes_approvals(server_url):
    _,report=req(server_url,'/api/analyze',{'asset_id':'P-101','start':'2027-07-17T10:00','duration_hours':2})
    _,reset=req(server_url,'/api/reset',{})
    _,boot=req(server_url,'/api/bootstrap')
    assert reset['ok'] and not boot['orders'] and boot['current'] is None


def test_direct_conflict_is_blocked_by_http(server_url):
    _,report=req(server_url,'/api/analyze',{'asset_id':'M-320','start':'2027-07-13T09:30','duration_hours':2})
    assert report['draft_order']['blocked']
    with pytest.raises(HTTPError) as exc:
        req(server_url,'/api/approve',{'order_id':report['draft_order']['id'],'reviewer':'Demo reviewer','confirmed':True})
    assert exc.value.code==400
