"""Lightweight FastAPI web server for TUIKarma Light Fluent 2 Mica UI Dashboard."""

from __future__ import annotations
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from tuikarma.core.event_bus import EventBus
from tuikarma.core.events import (
    BaseEvent,
    MessageEvent,
    StateChangeEvent,
    ToolCallEvent,
    ToolResultEvent,
    MetricsEvent,
    HITLApprovalRequestEvent,
    HITLApprovalResponseEvent,
    HITLCommandEvent,
    HITLAction,
    WorkflowStartedEvent,
    WorkflowNodeStartedEvent,
    WorkflowNodeCompletedEvent,
    WorkflowTransitionEvent,
    WorkflowCompletedEvent,
    WorkflowNodeRetryEvent,
    WorkflowFailedEvent,
    WorkflowRollbackStartedEvent,
    WorkflowNodeRollbackEvent,
    WorkflowRollbackCompletedEvent,
)
from tuikarma.core.topology import SwarmTopology
from tuikarma.core.llm import get_default_llm_provider
from tuikarma.harness.task import TaskSpec
from tuikarma.harness.evaluator import TaskEvaluator
from tuikarma.harness.trajectory import TrajectoryRecorder
from tuikarma.workflow.parser import WorkflowParser
from tuikarma.workflow.state import WorkflowState
from tuikarma.project.manager import ProjectManager, ProjectMetadata
from tuikarma.memory.reflexion import ExperienceStore
from tuikarma.harness.autopilot import AutoPilotRunner

logger = logging.getLogger("tuikarma.web")

# Static assets directory
STATIC_DIR = Path(__file__).resolve().parent / "static"


class RunTaskRequest(BaseModel):
    prompt: Optional[str] = None
    task_file: Optional[str] = None
    workflow_file: Optional[str] = None
    backend: str = "auto"


class HITLCommandRequest(BaseModel):
    action: str
    payload: Optional[str] = None


class CreateProjectRequest(BaseModel):
    name: str
    goal: str
    target_dir: Optional[str] = None


class OpenProjectRequest(BaseModel):
    folder_path: str
    goal: Optional[str] = None


class AutoPilotRequest(BaseModel):
    project_id: Optional[str] = None
    name: Optional[str] = None
    goal: str
    project_path: Optional[str] = None
    backend: str = "auto"



class WebSessionManager:
    """Manages active Swarm execution, EventBus subscriptions, and WebSocket clients."""

    def __init__(self) -> None:
        self.bus = EventBus()
        self.topology = SwarmTopology(self.bus, llm=get_default_llm_provider("auto"))
        self.evaluator = TaskEvaluator(self.topology.workspace_dir, bus=self.bus)
        self.recorder: Optional[TrajectoryRecorder] = None
        self.project_manager = ProjectManager()
        self.memory_store = ExperienceStore()
        self.active_project: Optional[ProjectMetadata] = None
        self.active_task_coro: Optional[asyncio.Task] = None
        self.is_running = False
        self.last_status: Dict[str, Any] = {
            "status": "IDLE",
            "current_node": None,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_usd": 0.0,
            "score": None,
            "passed": None,
            "pending_approval": None,
        }
        self.active_connections: List[WebSocket] = []

        # Hook all events to WebSocket broadcast
        self.bus.subscribe(BaseEvent, self._on_any_event)

    async def connect_client(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        # Send current initial state
        await websocket.send_json({
            "type": "INITIAL_STATE",
            "data": self.last_status,
        })

    def disconnect_client(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_event(self, event_data: Dict[str, Any]) -> None:
        disconnected = []
        for ws in self.active_connections:
            try:
                await ws.send_json(event_data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect_client(ws)

    async def _on_any_event(self, event: BaseEvent) -> None:
        evt_type = event.__class__.__name__
        payload = event.model_dump()
        payload["_event_type"] = evt_type
        payload["_timestamp"] = getattr(event, "timestamp", time.time())

        # Update cached status
        if isinstance(event, MetricsEvent):
            self.last_status["tokens_in"] += event.tokens_in
            self.last_status["tokens_out"] += event.tokens_out
            self.last_status["cost_usd"] += event.cost_usd
        elif isinstance(event, WorkflowNodeStartedEvent):
            self.last_status["current_node"] = event.node_id
            self.last_status["status"] = "RUNNING"
        elif isinstance(event, WorkflowCompletedEvent):
            self.last_status["status"] = "COMPLETED" if event.success else "FAILED"
        elif isinstance(event, HITLApprovalRequestEvent):
            self.last_status["pending_approval"] = {
                "node_id": event.node_id,
                "prompt": event.prompt,
            }
        elif isinstance(event, HITLApprovalResponseEvent):
            self.last_status["pending_approval"] = None

        if self.active_project:
            self.last_status["active_project"] = self.active_project.model_dump()
            self.last_status["active_milestones"] = self.active_project.milestones

        await self.broadcast_event({"type": "EVENT", "event": payload})

    async def start_task(self, req: RunTaskRequest) -> Dict[str, Any]:
        if self.is_running and self.active_task_coro and not self.active_task_coro.done():
            raise HTTPException(status_code=400, detail="A task is already actively running.")

        # Re-initialize Swarm & Recorder
        self.bus = EventBus()
        self.bus.subscribe(BaseEvent, self._on_any_event)
        llm = get_default_llm_provider(req.backend)
        self.topology = SwarmTopology(self.bus, llm=llm)
        self.evaluator = TaskEvaluator(self.topology.workspace_dir, bus=self.bus)
        self.recorder = TrajectoryRecorder(self.bus)
        self.last_status = {
            "status": "RUNNING",
            "current_node": None,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_usd": 0.0,
            "score": None,
            "passed": None,
            "pending_approval": None,
        }

        # Resolve TaskSpec
        if req.prompt:
            task = TaskSpec(
                id=f"TASK-WEB-{int(time.time())}",
                title="Web Interactive Task",
                description=req.prompt,
            )
        elif req.task_file:
            task_p = Path(req.task_file)
            if task_p.exists():
                task = TaskSpec.from_yaml(str(task_p))
            else:
                task = TaskSpec(id="DEFAULT", title="Default Task", description="Demo web run")
        else:
            task = TaskSpec(id="DEFAULT", title="Default Task", description="Multi-agent co-development run")

        workflow_path = Path(req.workflow_file) if req.workflow_file else None

        async def _run():
            self.is_running = True
            try:
                if workflow_path and workflow_path.exists():
                    engine = WorkflowParser.load_from_yaml(workflow_path, self.topology)
                    self.topology.active_workflow = engine
                    st = WorkflowState(task_description=task.description, max_steps=engine.max_steps)
                    await engine.execute(st)
                else:
                    await self.topology.execute_task_loop(task.description)

                eval_res = await self.evaluator.evaluate_task(task)
                self.last_status["score"] = eval_res.score
                self.last_status["passed"] = eval_res.passed
                self.last_status["status"] = "COMPLETED"
            except Exception as e:
                logger.error(f"Task failed: {e}", exc_info=True)
                self.last_status["status"] = "FAILED"
            finally:
                self.is_running = False
                await self.broadcast_event({"type": "TASK_FINISHED", "data": self.last_status})

        self.active_task_coro = asyncio.create_task(_run())
        return {"status": "STARTED", "task_id": task.id, "title": task.title}

    async def start_autopilot(self, req: AutoPilotRequest) -> Dict[str, Any]:
        if self.is_running and self.active_task_coro and not self.active_task_coro.done():
            raise HTTPException(status_code=400, detail="Một tác vụ hoặc phiên AutoPilot đang tích cực hoạt động.")

        # Re-initialize EventBus & broadcast
        self.bus = EventBus()
        self.bus.subscribe(BaseEvent, self._on_any_event)
        llm = get_default_llm_provider(req.backend)

        # Resolve or create project
        if req.project_id:
            project = self.project_manager.get_project(req.project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Không tìm thấy project_id trong registry.")
            if req.goal:
                project.goal = req.goal
        elif req.project_path:
            project = self.project_manager.open_existing_project(req.project_path, goal=req.goal or "")
        else:
            p_name = req.name or "Dự án Tự hành AutoPilot"
            project = self.project_manager.create_new_project(p_name, goal=req.goal)

        self.active_project = project
        self.topology = SwarmTopology(self.bus, workspace_dir=Path(project.path), llm=llm)
        self.evaluator = TaskEvaluator(self.topology.workspace_dir, bus=self.bus)
        self.recorder = TrajectoryRecorder(self.bus)

        self.last_status = {
            "status": "RUNNING",
            "mode": "AUTOPILOT",
            "current_node": "PLANNER",
            "active_project": project.model_dump(),
            "active_milestones": project.milestones,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_usd": 0.0,
            "score": None,
            "passed": None,
            "pending_approval": None,
        }

        runner = AutoPilotRunner(
            project=project,
            llm=llm,
            bus=self.bus,
            memory_store=self.memory_store,
            project_manager=self.project_manager
        )

        async def _run():
            self.is_running = True
            try:
                res = await runner.run()
                self.last_status["status"] = res["status"]
                self.last_status["active_project"] = project.model_dump()
                self.last_status["active_milestones"] = project.milestones
            except Exception as e:
                logger.error(f"AutoPilot execution failed: {e}", exc_info=True)
                self.last_status["status"] = "FAILED"
            finally:
                self.is_running = False
                await self.broadcast_event({"type": "TASK_FINISHED", "data": self.last_status})

        self.active_task_coro = asyncio.create_task(_run())
        return {
            "status": "STARTED",
            "project": project.model_dump(),
            "project_id": project.id,
            "project_name": project.name,
            "project_path": project.path,
        }

    async def handle_hitl_command(self, action_str: str, payload: Optional[str] = None) -> Dict[str, Any]:
        action_upper = action_str.upper()
        wf = self.topology.active_workflow

        if action_upper == "PAUSE":
            self.topology.set_paused(True)
        elif action_upper == "RESUME":
            self.topology.set_paused(False)
        elif action_upper == "STEP":
            self.topology.step_forward()
        elif action_upper == "APPROVE":
            await self.bus.publish(HITLCommandEvent(action=HITLAction.APPROVE, payload=payload))
            if self.last_status.get("pending_approval"):
                node_id = self.last_status["pending_approval"]["node_id"]
                await self.bus.publish(HITLApprovalResponseEvent(node_id=node_id, approved=True, guidance=payload))
                self.last_status["pending_approval"] = None
        elif action_upper == "REJECT":
            await self.bus.publish(HITLCommandEvent(action=HITLAction.REJECT, payload=payload))
            if self.last_status.get("pending_approval"):
                node_id = self.last_status["pending_approval"]["node_id"]
                await self.bus.publish(HITLApprovalResponseEvent(node_id=node_id, approved=False, guidance=payload or "Từ chối bởi Web UI"))
                self.last_status["pending_approval"] = None
        elif action_upper == "RETRY_NOW":
            if wf:
                wf.trigger_immediate_retry()
        elif action_upper == "SKIP":
            if wf:
                wf.skip_current_node()
        elif action_upper == "ROLLBACK":
            if wf:
                wf.force_rollback()
        elif action_upper == "INJECT":
            if wf and payload:
                wf.inject_guidance(payload)
            await self.bus.publish(HITLCommandEvent(action=HITLAction.INJECT, payload=payload))
        else:
            raise HTTPException(status_code=400, detail=f"Unknown HITL action '{action_str}'")

        return {"status": "SUCCESS", "action": action_upper}


manager = WebSessionManager()
app = FastAPI(title="TUIKarma Light Fluent 2 Mica Web UI", version="2026.1")


@app.get("/api/status")
async def get_status():
    return {
        **manager.last_status,
        "is_running": manager.is_running,
        "is_paused": getattr(manager.topology, "is_paused", False),
        "active_project": manager.active_project.model_dump() if manager.active_project else None,
        "experience_lessons_count": len(manager.memory_store.lessons),
        "agents": {
            k: {
                "role": v.role,
                "model": v.model_name,
                "state": v.state.value if hasattr(v.state, "value") else str(v.state),
            }
            for k, v in manager.topology.agents.items()
        }
    }


@app.get("/api/projects")
async def list_projects():
    return [p.model_dump() for p in manager.project_manager.list_projects()]


@app.post("/api/projects/new")
async def create_new_project(req: CreateProjectRequest):
    proj = manager.project_manager.create_new_project(req.name, req.goal, req.target_dir)
    manager.active_project = proj
    return proj.model_dump()


@app.post("/api/projects/open")
async def open_existing_project(req: OpenProjectRequest):
    try:
        proj = manager.project_manager.open_existing_project(req.folder_path, req.goal or "")
        manager.active_project = proj
        codebase = manager.project_manager.scan_project_codebase(proj.path)
        return {"project": proj.model_dump(), "codebase": codebase}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/fs/browse")
async def browse_folders(path: Optional[str] = None):
    return ProjectManager.browse_local_directories(path)


@app.get("/api/memory/lessons")
async def list_memory_lessons():
    return [l.model_dump() for l in manager.memory_store.lessons]


@app.post("/api/autopilot/start")
async def start_autopilot(req: AutoPilotRequest):
    return await manager.start_autopilot(req)


def _get_active_graph_engine(custom_path: Optional[str] = None):
    from tuikarma.graph.engine import CodeKnowledgeGraphEngine
    if custom_path and Path(custom_path).exists() and Path(custom_path).is_dir():
        target = Path(custom_path)
    elif manager.active_project and Path(manager.active_project.path).exists():
        target = Path(manager.active_project.path)
    else:
        target = manager.topology.workspace_dir
    return CodeKnowledgeGraphEngine(target)


@app.get("/api/graph/summary")
async def get_graph_summary(path: Optional[str] = Query(None)):
    engine = _get_active_graph_engine(path)
    return engine.get_summary()


@app.get("/api/graph/query")
async def query_graph_symbol(symbol: str = Query(...), path: Optional[str] = Query(None)):
    engine = _get_active_graph_engine(path)
    return engine.query_symbol(symbol)


@app.get("/api/graph/path")
async def find_graph_path(source: str = Query(...), target: str = Query(...), path: Optional[str] = Query(None)):
    engine = _get_active_graph_engine(path)
    return engine.find_path(source, target)


@app.get("/api/graph/impact")
async def analyze_graph_impact(symbol: str = Query(...), depth: int = Query(2), path: Optional[str] = Query(None)):
    engine = _get_active_graph_engine(path)
    return engine.impact_analysis(symbol, max_depth=depth)


@app.get("/api/graph/view")
async def view_graph_html(path: Optional[str] = Query(None)):
    engine = _get_active_graph_engine(path)
    html_path = engine.export_interactive_html()
    if html_path and html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Không thể tạo file HTML trực quan hóa đồ thị (chưa có code files).")


@app.get("/api/pipelines")
async def get_pipelines():
    pipeline_dir = Path("tasks/pipelines")
    results = []
    if pipeline_dir.exists():
        import yaml
        for p in pipeline_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                results.append({
                    "id": p.name,
                    "path": str(p),
                    "name": data.get("name", p.stem),
                    "max_steps": data.get("max_steps", 10),
                    "nodes": [
                        {
                            "id": n.get("id"),
                            "name": n.get("name"),
                            "type": n.get("type"),
                            "agent": n.get("agent"),
                        }
                        for n in data.get("nodes", [])
                    ]
                })
            except Exception:
                pass
    return results


@app.get("/api/sandbox/files")
async def get_sandbox_files():
    if manager.active_project and Path(manager.active_project.path).exists():
        sb_dir = Path(manager.active_project.path)
    else:
        sb_dir = manager.topology.workspace_dir
    files = []
    if sb_dir.exists():
        ignore = {".git", ".venv", "venv", "__pycache__", ".tuikarma", ".pytest_cache"}
        for f in sb_dir.rglob("*"):
            if any(part in ignore for part in f.parts):
                continue
            if f.is_file():
                rel_path = f.relative_to(sb_dir).as_posix()
                files.append({
                    "name": f.name,
                    "path": rel_path,
                    "size": f.stat().st_size,
                    "updated_at": f.stat().st_mtime,
                })
    return files


@app.get("/api/sandbox/file")
async def get_sandbox_file_content(path: str = Query(...)):
    if manager.active_project and Path(manager.active_project.path).exists():
        sb_dir = Path(manager.active_project.path)
    else:
        sb_dir = manager.topology.workspace_dir
    target = (sb_dir / path).resolve()
    if not str(target).startswith(str(sb_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = target.read_text(encoding="utf-8")
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/run")
async def run_task(req: RunTaskRequest):
    return await manager.start_task(req)


@app.post("/api/hitl/command")
async def hitl_command(req: HITLCommandRequest):
    return await manager.handle_hitl_command(req.action, req.payload)


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect_client(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action"):
                    await manager.handle_hitl_command(msg["action"], msg.get("payload"))
            except Exception as e:
                logger.error(f"Error handling WS client message: {e}")
    except WebSocketDisconnect:
        manager.disconnect_client(websocket)


# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "TUIKarma Web UI is ready. static/index.html loading."}


def run_web_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Start uvicorn server serving TUIKarma Light Fluent 2 Mica Web UI."""
    import uvicorn
    print(f"\n[TUIKarma Web] 🌟 Khởi chạy Light Fluent 2 Mica Web UI tại http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
