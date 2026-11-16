"""Optional REAL MCP server using the official MCP Python SDK v2.

Install: pip install 'mcp>=2,<3'
Run:     python -m gasgraph.mcp_server
Or:      mcp dev gasgraph/mcp_server.py

All tools operate only on the fictional in-repo network; none can reach plants.
"""
from mcp.server import MCPServer
from gasgraph.engine import NetworkEngine

engine = NetworkEngine()
mcp = MCPServer('GasGraph Synthetic Ontology')

@mcp.tool()
def list_entity_types() -> dict:
    """Discover the fictional gas-network ontology entity and relation types."""
    return engine.network['ontology']

@mcp.tool()
def list_assets() -> list[dict]:
    """List synthetic assets available for analysis."""
    return [{'id':a['id'],'label':a['label'],'type':a['type']} for a in engine.assets.values()]

@mcp.tool()
def find_dependencies(asset_id: str) -> dict:
    """Traverse FLOWS_TO relationships; explain each downstream dependency with evidence paths."""
    return engine.find_dependencies(asset_id)

@mcp.tool()
def check_maintenance_conflicts(asset_id: str, start: str, duration_hours: float = 4) -> dict:
    """Detect synthetic scheduling overlaps. Times are YYYY-MM-DDTHH:MM."""
    return engine.check_maintenance_conflicts(asset_id,start,duration_hours)

@mcp.tool()
def draft_work_order(asset_id: str, start: str, duration_hours: float = 4) -> dict:
    """Create a work-order suggestion in memory; NEVER actuates real systems."""
    return engine.analyze_maintenance(asset_id,start,duration_hours)['draft_order']

if __name__ == '__main__':
    mcp.run()
