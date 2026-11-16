"""Mock tool-call traffic: no real model or external requests in tests."""
import io
import json
import pytest
from gasgraph.engine import NetworkEngine
from gasgraph import llm

class FakeReply:
    def __init__(self,obj): self.content=json.dumps(obj).encode()
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,amount=None): return self.content

def fake_tool_call(asset='C-201'):
    return {'choices':[{'message':{'tool_calls':[{'function':{'name':'analyze_maintenance','arguments':json.dumps({'asset_id':asset,'duration_hours':3})}}]}}]}

def test_local_only_config(monkeypatch):
    monkeypatch.setenv('GASGRAPH_LLM_BASE_URL','http://127.0.0.1:1234/v1')
    monkeypatch.setenv('GASGRAPH_LLM_MODEL','test-model')
    assert llm.config()['model']=='test-model'
    monkeypatch.setenv('GASGRAPH_LLM_BASE_URL','https://external.example/v1')
    with pytest.raises(ValueError): llm.config()
    monkeypatch.setenv('GASGRAPH_LLM_BASE_URL','http://127.0.0.1:1234/v1')
    assert llm.config()['base_url']=='http://127.0.0.1:1234/v1'

def test_planner_only_returns_validated_assets(monkeypatch):
    monkeypatch.setenv('GASGRAPH_LLM_BASE_URL','http://localhost:1234/v1')
    monkeypatch.setenv('GASGRAPH_LLM_MODEL','model-with-tools')
    monkeypatch.setattr(llm,'urlopen',lambda *args,**kwargs:FakeReply(fake_tool_call('C-201')))
    plan=llm.plan_with_local_llm('Compressor maintenance',list(NetworkEngine().assets.values()),'2027-07-13T09:00',4)
    assert plan['asset_id']=='C-201' and plan['duration_hours']==3
    monkeypatch.setattr(llm,'urlopen',lambda *args,**kwargs:FakeReply(fake_tool_call('NONEXISTENT')))
    assert llm.plan_with_local_llm('Unknown',list(NetworkEngine().assets.values()),'2027-07-13T09:00',4) is None

def test_planner_failure_cannot_invent_answer(monkeypatch):
    monkeypatch.setenv('GASGRAPH_LLM_BASE_URL','http://localhost:1234/v1')
    monkeypatch.setenv('GASGRAPH_LLM_MODEL','test')
    monkeypatch.setattr(llm,'urlopen',lambda *args,**kwargs:(_ for _ in ()).throw(ConnectionError('Model unavailable')))
    with pytest.raises(llm.LocalPlannerError):
        llm.plan_with_local_llm('Maintenance',list(NetworkEngine().assets.values()),'2027-07-13T09:00',4)
