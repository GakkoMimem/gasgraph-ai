import pytest
from gasgraph.engine import NetworkEngine
from gasgraph.server import DemoSession

@pytest.fixture
def eng(): return NetworkEngine()

def test_dataset_is_internally_consistent(eng):
    assert len(eng.assets)==22
    assert all(e['type']=='FLOWS_TO' for e in eng.edges)
    assert len(set(eng.assets))==len(eng.assets)
    assert all(e['source'] in eng.assets and e['target'] in eng.assets for e in eng.edges)

def test_dependency_evidence_paths_are_valid(eng):
    dep=eng.find_dependencies('T-WEST')
    assert 'T-EAST' in dep['downstream']
    for dest,path in dep['paths'].items():
        assert path[0]=='T-WEST' and path[-1]==dest
        assert all(b in eng.forward[a] for a,b in zip(path,path[1:]))

def test_redundant_supply_detected(eng):
    result=eng.analyze_maintenance('C-201','2027-07-13T09:00',3)
    assert 'T-EAST' in result['impact']['alternate_path_possible']
    assert 'T-EAST' not in result['impact']['newly_unreachable_in_topology']
    assert 'P-210' in result['impact']['newly_unreachable_in_topology']

def test_source_isolation_has_alternative_central_feed(eng):
    result=eng.analyze_maintenance('T-WEST','2027-07-13T09:00',4)
    assert 'J-CENT' in result['impact']['alternate_path_possible']
    assert 'M-101' in result['impact']['newly_unreachable_in_topology']

def test_overlapping_maintenance_classified(eng):
    result=eng.check_maintenance_conflicts('M-320','2027-07-13T09:30',2)
    assert result['direct_count']==1
    assert result['coordination_count']==0
    assert result['conflicts'][0]['id']=='MW-024'

def test_touching_interval_not_overlapping(eng):
    result=eng.check_maintenance_conflicts('M-320','2027-07-13T12:00',1)
    assert result['direct_count']==0

def test_distant_job_ignored(eng):
    result=eng.check_maintenance_conflicts('P-101','2027-07-17T10:00',2)
    assert len(result['conflicts'])==0

def test_agent_declines_unknown_assets(eng):
    r=eng.ask('Please maintain the fictional Moon Beacon')
    assert not r['understood']
    assert len(r['tool_trace'])==1

def test_agent_routes_known_asset(eng):
    r=eng.ask('Can you plan maintenance on Westhaven Terminal?')
    assert r['understood'] and r['analysis']['asset']['id']=='T-WEST'
    assert r['mode']=='deterministic-tool-router'

def test_invalid_times_and_duration(eng):
    with pytest.raises(ValueError): eng.analyze_maintenance('T-WEST','2027-07-13T09:00',0)
    with pytest.raises(ValueError): eng.analyze_maintenance('T-WEST','2027-07-13T09:00',49)
    with pytest.raises(ValueError): eng.analyze_maintenance('NOPE','2027-07-13T09:00',2)
    with pytest.raises(ValueError): eng.analyze_maintenance('T-WEST','banana',2)

def test_approval_is_explicit_demo_only(eng):
    session=DemoSession(eng)
    analysis=session.analyze({'asset_id':'P-101','start':'2027-07-17T10:00','duration_hours':2})
    oid=analysis['draft_order']['id']
    with pytest.raises(ValueError): session.approve({'order_id':oid,'reviewer':'Demo Operator','confirmed':False})
    confirmation=session.approve({'order_id':oid,'reviewer':'Demo Operator','confirmed':True})
    assert confirmation['order']['approval_status']=='Approved in demo only'
    assert 'No field systems' in confirmation['message']
    assert len(session.audit)>=2

def test_no_approval_for_nonexistent_order(eng):
    with pytest.raises(ValueError): DemoSession(eng).approve({'order_id':'WO-FAKE','reviewer':'Demo','confirmed':True})

def test_workorder_identifier_stable(eng):
    a=eng.analyze_maintenance('T-WEST','2027-07-13T09:00',4)
    b=eng.analyze_maintenance('T-WEST','2027-07-13T09:00',4)
    assert a['draft_order']['id']==b['draft_order']['id']


def test_direct_overlap_blocks_approval(eng):
    session=DemoSession(eng)
    report=session.analyze({'asset_id':'M-320','start':'2027-07-13T09:30','duration_hours':2})
    assert report['draft_order']['blocked']
    with pytest.raises(ValueError,match='direct scheduling conflict'):
        session.approve({'order_id':report['draft_order']['id'],'reviewer':'Demo reviewer','confirmed':True})
