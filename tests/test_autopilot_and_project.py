import pytest
import asyncio
from pathlib import Path
from fastapi.testclient import TestClient

from tuikarma.project.manager import ProjectManager
from tuikarma.memory.reflexion import ExperienceStore
from tuikarma.harness.planner import AutonomousPlanner
from tuikarma.harness.autopilot import AutoPilotRunner
from tuikarma.core.event_bus import EventBus
from tuikarma.core.llm import ScenarioLLMProvider
from tuikarma.web.server import app, manager


def test_project_manager_create_and_list(tmp_path):
    reg_file = tmp_path / "projects.json"
    pm = ProjectManager(registry_file=reg_file)

    p1 = pm.create_new_project("Payment Gateway", "Xây dựng cổng thanh toán trực tuyến", target_dir=str(tmp_path / "pay"))
    assert p1.name == "Payment Gateway"
    assert Path(p1.path).exists()
    assert (Path(p1.path) / "README.md").exists()

    projects = pm.list_projects()
    assert len(projects) == 1
    assert projects[0].id == p1.id


def test_project_manager_open_existing(tmp_path):
    reg_file = tmp_path / "projects.json"
    pm = ProjectManager(registry_file=reg_file)

    existing_dir = tmp_path / "my_existing_app"
    existing_dir.mkdir(parents=True)
    (existing_dir / "app.py").write_text("print('hello')", encoding="utf-8")
    (existing_dir / "pyproject.toml").write_text("[project]\nname='demo'", encoding="utf-8")

    proj = pm.open_existing_project(str(existing_dir), goal="Refactor to async")
    assert proj.name == "my_existing_app"
    assert proj.is_new is False

    scan = pm.scan_project_codebase(proj.path)
    assert scan["total_files"] == 2
    assert "pyproject.toml" in scan["key_configs"]


def test_project_manager_browse_local_directories():
    res = ProjectManager.browse_local_directories()
    assert "current_path" in res
    assert "folders" in res
    assert isinstance(res["folders"], list)


def test_experience_store_and_reflexion(tmp_path):
    store_file = tmp_path / "memory.json"
    store = ExperienceStore(storage_path=store_file)

    assert len(store.lessons) >= 3  # default seeded lessons

    # Retrieve matching lesson
    lessons = store.retrieve_relevant_lessons("race condition token bucket concurrency", limit=2)
    assert len(lessons) > 0
    assert any(l.domain == "concurrency" for l in lessons)

    # Format for prompt
    prompt_injection = store.format_lessons_for_prompt("concurrency async")
    assert "BÀI HỌC KINH NGHIỆM" in prompt_injection

    # Record new lesson
    new_lesson = store.record_lesson(
        domain="database",
        trigger_error="Connection pool exhaustion",
        root_cause="Unclosed database cursor in exception block",
        lesson_learned="Always use context manager `async with db.acquire():`",
        recommended_pattern="async with db.acquire() as conn:\n    await conn.execute()",
    )
    assert new_lesson.id.startswith("LESSON-")
    assert len(store.lessons) >= 4

    # Persistence verification
    store2 = ExperienceStore(storage_path=store_file)
    assert len(store2.lessons) == len(store.lessons)


@pytest.mark.asyncio
async def test_autonomous_planner_heuristic():
    planner = AutonomousPlanner(llm=None)
    plan = await planner.plan_project("Xây dựng module cache TTL với Redis")
    assert len(plan.milestones) >= 3
    assert plan.milestones[0].id == "M1"
    assert len(plan.milestones[0].deliverables) > 0


@pytest.mark.asyncio
async def test_autopilot_runner_execution(tmp_path):
    reg_file = tmp_path / "projects.json"
    pm = ProjectManager(registry_file=reg_file)
    proj = pm.create_new_project("Autopilot Test App", "Viết module utility và test", target_dir=str(tmp_path / "app"))

    bus = EventBus()
    llm = ScenarioLLMProvider()
    store = ExperienceStore(storage_path=tmp_path / "exp.json")

    runner = AutoPilotRunner(project=proj, llm=llm, bus=bus, memory_store=store, project_manager=pm)
    res = await runner.run()

    assert res["status"] in ("COMPLETED", "PAUSED")
    assert res["total_milestones"] >= 3
    assert res["completed_milestones"] >= 1
    assert proj.status in ("COMPLETED", "PAUSED")


def test_web_api_project_endpoints(tmp_path):
    client = TestClient(app)

    # 1. Browse folders
    res = client.get("/api/fs/browse")
    assert res.status_code == 200
    assert "current_path" in res.json()

    # 2. List experience lessons
    res_mem = client.get("/api/memory/lessons")
    assert res_mem.status_code == 200
    assert len(res_mem.json()) >= 3

    # 3. Create project via API
    target_p = str(tmp_path / "api_test_project")
    res_create = client.post("/api/projects/new", json={
        "name": "API Created Project",
        "goal": "Test project creation via REST API",
        "target_dir": target_p
    })
    assert res_create.status_code == 200
    p_data = res_create.json()
    assert p_data["name"] == "API Created Project"

    # 4. List projects
    res_list = client.get("/api/projects")
    assert res_list.status_code == 200
    assert any(p["id"] == p_data["id"] for p in res_list.json())

    # 5. Open project via API
    res_open = client.post("/api/projects/open", json={
        "folder_path": target_p,
        "goal": "Inspect project"
    })
    assert res_open.status_code == 200
    assert "codebase" in res_open.json()
