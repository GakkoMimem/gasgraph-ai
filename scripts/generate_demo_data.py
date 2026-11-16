"""Generate reproducible, entirely fictional network, jobs and scenarios."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Units and entities are deliberately fictional: this is not Gassco operational information.
assets = [
    ('SRC-N','North Sea Alpha','source',72,115,110,'Operational','Fictional northern inlet'),
    ('P-101','North Trunk · P-101','pipeline',190,115,105,'Operational','Primary inlet corridor'),
    ('T-WEST','Westhaven Terminal','terminal',325,115,105,'Operational','Western processing and routing node'),
    ('M-101','Metering · M-101','meter',453,115,94,'Operational','Inbound flow measurement'),
    ('P-110','Coastal Link · P-110','pipeline',560,115,90,'Operational','Feed to central hub'),
    ('J-CENT','Central Exchange','junction',680,185,115,'Operational','Multi-route distribution hub'),
    ('C-201','Compression · C-201','compressor',798,110,95,'Operational','Pressure-support asset'),
    ('P-210','Eastern Link · P-210','pipeline',928,110,82,'Operational','Eastern export corridor'),
    ('T-EAST','Eastport Terminal','terminal',1055,190,95,'Operational','Eastern receiving terminal'),
    ('M-210','Metering · M-210','meter',1140,280,76,'Operational','Eastern delivery meter'),
    ('OFF-EAST','East Grid','offtake',1155,382,72,'Operational','Fictional industrial offtake'),
    ('SRC-S','Southern Delta','source',72,410,89,'Operational','Fictional secondary inlet'),
    ('P-301','Southern Trunk · P-301','pipeline',190,410,87,'Operational','Southern trunk pipeline'),
    ('T-SOUTH','Southbay Terminal','terminal',325,410,87,'Operational','Southern distribution terminal'),
    ('P-310','South Link · P-310','pipeline',452,410,82,'Operational','Feed to southern hub'),
    ('J-SOUTH','Southern Exchange','junction',570,410,105,'Operational','Southern branching hub'),
    ('P-320','Lakeside Link · P-320','pipeline',700,450,63,'Operational','Southwest distribution'),
    ('M-320','Metering · M-320','meter',824,450,65,'Review','Synthetic calibration warning'),
    ('OFF-SOUTH','South Grid','offtake',950,450,61,'Operational','Fictional southwest offtake'),
    ('P-330','Interconnector · P-330','pipeline',626,305,72,'Operational','Southern-to-central crossfeed'),
    ('P-220','Storage Link · P-220','pipeline',815,273,70,'Operational','Alternate eastern corridor'),
    ('STOR-01','Boreal Storage','storage',928,285,75,'Operational','Synthetic storage and buffer'),
]
asset_data = [
    {'id':aid,'label':label,'type':typ,'x':x,'y':y,'capacity':cap,'status':status,'description':desc,
     'data_classification':'SYNTHETIC','entity_source':'demo/assets.json'}
    for aid,label,typ,x,y,cap,status,desc in assets
]
flows = [
    ('SRC-N','P-101'),('P-101','T-WEST'),('T-WEST','M-101'),('M-101','P-110'),('P-110','J-CENT'),
    ('J-CENT','C-201'),('C-201','P-210'),('P-210','T-EAST'),('T-EAST','M-210'),('M-210','OFF-EAST'),
    ('SRC-S','P-301'),('P-301','T-SOUTH'),('T-SOUTH','P-310'),('P-310','J-SOUTH'),
    ('J-SOUTH','P-320'),('P-320','M-320'),('M-320','OFF-SOUTH'),
    ('J-SOUTH','P-330'),('P-330','J-CENT'),
    ('J-CENT','P-220'),('P-220','STOR-01'),('STOR-01','T-EAST'),
]
network={
    'name':'GasGraph synthetic network','scenario_label':'Fictional North-South system','classification':'SYNTHETIC — NO REAL INFRASTRUCTURE DATA',
    'units':'demonstration units per hour (invented, not calibrated)',
    'sources':['SRC-N','SRC-S'], 'assets':asset_data,
    'relationships':[{'id':f'E-{i:02}','source':s,'target':t,'type':'FLOWS_TO'} for i,(s,t) in enumerate(flows,1)],
    'ontology':{
        'entity_types':['Source','Pipeline','Terminal','Junction','Compressor','Meter','Storage','Offtake'],
        'relationship_types':['FLOWS_TO'],
        'rules':['FLOWS_TO represents potential directed dependency, not confirmed physical flow.',
                 'A topology-based consequence analysis never establishes hydraulic feasibility.',
                 'Proposed work orders cannot operate equipment or affect real systems.']
    }
}
jobs=[
    {'id':'MW-018','asset_id':'P-210','title':'Inspection on Eastern Link','start':'2027-07-13T08:30:00','end':'2027-07-13T12:30:00','status':'Scheduled','team':'Team Delta'},
    {'id':'MW-020','asset_id':'T-EAST','title':'Terminal control system upgrade','start':'2027-07-13T09:30:00','end':'2027-07-13T14:00:00','status':'Scheduled','team':'Team Echo'},
    {'id':'MW-022','asset_id':'C-201','title':'Compression unit service','start':'2027-07-15T08:00:00','end':'2027-07-15T11:00:00','status':'Scheduled','team':'Team Bravo'},
    {'id':'MW-024','asset_id':'M-320','title':'Meter calibration','start':'2027-07-13T09:00:00','end':'2027-07-13T12:00:00','status':'Scheduled','team':'Team Alpha'},
    {'id':'MW-027','asset_id':'T-WEST','title':'Routine terminal inspection','start':'2027-07-20T09:00:00','end':'2027-07-20T11:00:00','status':'Scheduled','team':'Team Foxtrot'},
]
scenarios=[
    {'id':'west','name':'Westhaven maintenance','subtitle':'Dependency and scheduling impact','asset_id':'T-WEST','start':'2027-07-13T09:00','duration_hours':4},
    {'id':'compression','name':'Compressor intervention','subtitle':'Compare alternate eastward routes','asset_id':'C-201','start':'2027-07-13T09:00','duration_hours':3},
    {'id':'south','name':'South meter calibration','subtitle':'Identify direct maintenance conflict','asset_id':'M-320','start':'2027-07-13T09:30','duration_hours':2},
    {'id':'no_conflict','name':'Quiet-window planning','subtitle':'Compare low-conflict scheduling','asset_id':'P-101','start':'2027-07-17T10:00','duration_hours':2},
]
for name,data in [('network.json',network),('jobs.json',jobs),('scenarios.json',scenarios)]:
    (ROOT/'data'/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(name,len(data))
