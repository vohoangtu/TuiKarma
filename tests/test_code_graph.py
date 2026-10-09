import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from tuikarma.graph.engine import CodeKnowledgeGraphEngine
from tuikarma.tools.graph import CodeGraphTool
from tuikarma.core.event_bus import EventBus
from tuikarma.core.topology import SwarmTopology
from tuikarma.web.server import app, manager


@pytest.fixture
def sample_code_dir(tmp_path):
    pkg_dir = tmp_path / "sample_pkg"
    pkg_dir.mkdir(parents=True)

    # File A: core models
    (pkg_dir / "models.py").write_text("""
class User:
    def __init__(self, name: str):
        self.name = name

class Account:
    def __init__(self, user: User):
        self.user = user
""", encoding="utf-8")

    # File B: service that imports models
    (pkg_dir / "service.py").write_text("""
from sample_pkg.models import User, Account

class UserService:
    def create_account(self, name: str) -> Account:
        user = User(name)
        return Account(user)
""", encoding="utf-8")

    # File C: main entry that imports service
    (pkg_dir / "main.py").write_text("""
from sample_pkg.service import UserService

def run():
    svc = UserService()
    acc = svc.create_account("Alice")
    print(acc)
""", encoding="utf-8")

    return pkg_dir


def test_code_graph_engine_build_and_summary(sample_code_dir):
    engine = CodeKnowledgeGraphEngine(sample_code_dir)
    assert engine.is_available() is True

    summary = engine.get_summary()
    assert summary["available"] is True
    assert summary["total_nodes"] > 0
    assert summary["total_edges"] > 0
    assert isinstance(summary["god_nodes"], list)


def test_code_graph_engine_query_and_path(sample_code_dir):
    engine = CodeKnowledgeGraphEngine(sample_code_dir)

    # Query User
    res = engine.query_symbol("User")
    assert res["found"] is True
    assert res["degree"] > 0
    assert len(res["connections"]) > 0

    # Path from UserService to User
    path_res = engine.find_path("UserService", "User")
    assert path_res["found"] is True
    assert path_res["length"] >= 1
    assert any(step["label"] == "User" for step in path_res["path"])


def test_code_graph_engine_impact_analysis(sample_code_dir):
    engine = CodeKnowledgeGraphEngine(sample_code_dir)

    # Impact when changing User
    impact = engine.impact_analysis("User", max_depth=2)
    assert impact["found"] is True
    assert impact["total_affected_components"] > 0
    assert impact["risk_level"] in ("LOW", "MEDIUM", "HIGH")


def test_code_graph_engine_html_export(sample_code_dir, tmp_path):
    engine = CodeKnowledgeGraphEngine(sample_code_dir)
    out_html = tmp_path / "graph.html"
    res_path = engine.export_interactive_html(out_html)
    assert res_path is not None
    assert res_path.exists()
    assert res_path.stat().st_size > 1000


@pytest.mark.asyncio
async def test_code_graph_tool_execution(sample_code_dir):
    tool = CodeGraphTool(workspace_root=sample_code_dir)

    # Summary action
    summary_raw = await tool.execute(action="summary")
    assert "total_nodes" in summary_raw

    # Query action
    query_raw = await tool.execute(action="query", symbol="User")
    assert "User" in query_raw

    # Path action
    path_raw = await tool.execute(action="path", symbol="UserService", target_symbol="User")
    assert "path" in path_raw

    # Impact action
    impact_raw = await tool.execute(action="impact", symbol="User")
    assert "risk_level" in impact_raw

    # Cycles action
    cycles_raw = await tool.execute(action="cycles")
    assert "import_cycles" in cycles_raw


def test_swarm_topology_includes_code_graph_tool(tmp_path):
    bus = EventBus()
    topology = SwarmTopology(bus=bus, workspace_dir=tmp_path)
    assert topology.tools.contains("code_graph") is True
    tool = topology.tools.get("code_graph")
    assert isinstance(tool, CodeGraphTool)


def test_web_api_graph_endpoints(sample_code_dir):
    from tuikarma.project.manager import ProjectMetadata
    manager.active_project = ProjectMetadata(
        id="TEST-GRAPH",
        name="Sample Pkg",
        path=str(sample_code_dir),
        goal="Test Graph APIs"
    )
    client = TestClient(app)

    # Test summary endpoint
    res_sum = client.get("/api/graph/summary")
    assert res_sum.status_code == 200
    data = res_sum.json()
    assert data["total_nodes"] > 0

    # Test query endpoint
    res_q = client.get("/api/graph/query?symbol=User")
    assert res_q.status_code == 200
    assert res_q.json()["found"] is True

    # Test impact endpoint
    res_imp = client.get("/api/graph/impact?symbol=User&depth=2")
    assert res_imp.status_code == 200
    assert res_imp.json()["found"] is True
    assert "risk_level" in res_imp.json()
