"""Public mode must be stateless, with approvals and resets disabled."""
import json
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import pytest
from gasgraph.server import DemoSession, make_handler

@pytest.fixture
def public_url():
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(DemoSession(),public_demo=True))
    thread=Thread(target=server.serve_forever,daemon=True); thread.start()
    try: yield 'http://127.0.0.1:'+str(server.server_port)
    finally: server.shutdown(); server.server_close(); thread.join(2)

def get(base,path):
    with urlopen(base+path,timeout=3) as resp: return json.load(resp)

def post(base,path,body):
    b=json.dumps(body).encode('utf8')
    with urlopen(Request(base+path,data=b,headers={'Content-Type':'application/json'}),timeout=3) as resp: return json.load(resp)

def test_public_mode_is_stateless(public_url):
    before=get(public_url,'/api/bootstrap')
    assert before['environment'].startswith('PUBLIC') and not before['audit']
    result=post(public_url,'/api/analyze',{'asset_id':'P-101','start':'2027-07-17T10:00','duration_hours':2})
    assert result['asset']['id']=='P-101'
    after=get(public_url,'/api/bootstrap')
    assert not after['orders'] and not after['current'] and not after['audit']

def test_public_mode_blocks_mutating_actions(public_url):
    for path in ('/api/approve','/api/reset'):
        with pytest.raises(HTTPError) as exc: post(public_url,path,{'confirmed':True,'order_id':'anything','reviewer':'Someone'})
        assert exc.value.code==403

def test_public_agent_is_available(public_url):
    response=post(public_url,'/api/ask',{'question':'Assess Westhaven Terminal maintenance and affected downstream assets'})
    assert response['understood'] and response['analysis']['asset']['id']=='T-WEST'
