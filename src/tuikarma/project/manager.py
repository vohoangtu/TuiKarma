"""Project Workspace Manager for TUIKarma.
Supports creating new projects or browsing and opening existing projects on the local filesystem.
"""

from __future__ import annotations
import json
import logging
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("tuikarma.project")


class ProjectMetadata(BaseModel):
    """Metadata representing a managed project workspace."""
    id: str
    name: str
    path: str  # Absolute path on local filesystem
    is_new: bool = True
    goal: str = ""
    status: str = "INITIALIZED"  # INITIALIZED, PLANNING, IN_PROGRESS, COMPLETED, PAUSED
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    milestones: List[Dict[str, Any]] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class ProjectManager:
    """Manages project workspaces, local folder browsing, and multi-project persistence."""

    def __init__(self, registry_file: Optional[Path] = None) -> None:
        if registry_file is None:
            self.registry_file = Path("projects/projects_registry.json")
        else:
            self.registry_file = Path(registry_file)

        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self.projects: Dict[str, ProjectMetadata] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        if self.registry_file.exists():
            try:
                data = json.loads(self.registry_file.read_text(encoding="utf-8"))
                for item in data:
                    proj = ProjectMetadata(**item)
                    self.projects[proj.id] = proj
            except Exception as e:
                logger.warning(f"Failed to load project registry: {e}")
                self.projects = {}

    def _save_registry(self) -> None:
        try:
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            data = [p.model_dump() for p in self.projects.values()]
            self.registry_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save project registry: {e}")

    @staticmethod
    def _slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        return re.sub(r"[-\s]+", "_", text)[:40] or "project"

    def create_new_project(
        self,
        name: str,
        goal: str,
        target_dir: Optional[str] = None
    ) -> ProjectMetadata:
        """Creates a brand new project workspace directory."""
        slug = self._slugify(name)
        project_id = f"PROJ-{int(time.time())}-{slug[:12]}"

        if target_dir:
            proj_path = Path(target_dir).resolve()
        else:
            proj_path = (Path("projects") / slug).resolve()

        proj_path.mkdir(parents=True, exist_ok=True)

        # Initialize project metadata folder
        meta_dir = proj_path / ".tuikarma"
        meta_dir.mkdir(parents=True, exist_ok=True)

        # Create basic README if none exists
        readme_file = proj_path / "README.md"
        if not readme_file.exists():
            readme_file.write_text(
                f"# {name}\n\n## Mục tiêu dự án\n{goal}\n\n*Được quản lý tự động bởi TUIKarma Autonomous Harness.*\n",
                encoding="utf-8"
            )

        metadata = ProjectMetadata(
            id=project_id,
            name=name,
            path=str(proj_path),
            is_new=True,
            goal=goal,
            status="INITIALIZED",
        )
        self.projects[project_id] = metadata
        self._save_registry()
        return metadata

    def open_existing_project(
        self,
        folder_path: str,
        goal: str = ""
    ) -> ProjectMetadata:
        """Opens and registers an existing directory as a managed project workspace."""
        path_obj = Path(folder_path).resolve()
        if not path_obj.exists() or not path_obj.is_dir():
            raise ValueError(f"Đường dẫn thư mục không tồn tại: {folder_path}")

        name = path_obj.name
        slug = self._slugify(name)
        # Check if already registered
        for proj in self.projects.values():
            if Path(proj.path).resolve() == path_obj:
                if goal:
                    proj.goal = goal
                proj.updated_at = time.time()
                self._save_registry()
                return proj

        project_id = f"PROJ-{int(time.time())}-{slug[:12]}"
        meta_dir = path_obj / ".tuikarma"
        meta_dir.mkdir(parents=True, exist_ok=True)

        metadata = ProjectMetadata(
            id=project_id,
            name=name,
            path=str(path_obj),
            is_new=False,
            goal=goal or f"Phát triển và bảo trì codebase tại {name}",
            status="INITIALIZED",
        )
        self.projects[project_id] = metadata
        self._save_registry()
        return metadata

    def list_projects(self) -> List[ProjectMetadata]:
        """Returns all registered projects sorted by most recently updated."""
        sorted_list = sorted(self.projects.values(), key=lambda p: p.updated_at, reverse=True)
        return sorted_list

    def get_project(self, project_id: str) -> Optional[ProjectMetadata]:
        return self.projects.get(project_id)

    def scan_project_codebase(self, project_path: str) -> Dict[str, Any]:
        """Scans project directory and builds codebase summary for LLM context injection."""
        base = Path(project_path).resolve()
        if not base.exists() or not base.is_dir():
            return {"error": "Invalid directory", "files": [], "total_files": 0}

        ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache", ".idea", ".vscode", "dist", "build"}
        collected_files = []
        key_configs = []

        for p in base.rglob("*"):
            # Check ignore
            if any(part in ignore_dirs for part in p.parts):
                continue
            if p.is_file():
                rel = p.relative_to(base).as_posix()
                collected_files.append(rel)
                if p.name.lower() in ("pyproject.toml", "requirements.txt", "package.json", "dockerfile", "readme.md", "setup.py", "go.mod", "cargo.toml"):
                    key_configs.append(rel)

        # Detect primary languages
        suffixes = [Path(f).suffix for f in collected_files if Path(f).suffix]
        from collections import Counter
        counts = Counter(suffixes)

        # Code Knowledge Graph extraction via Graphify
        graph_summary = None
        try:
            from tuikarma.graph.engine import CodeKnowledgeGraphEngine
            graph_engine = CodeKnowledgeGraphEngine(base)
            graph_summary = graph_engine.get_summary()
        except Exception as e:
            logger.debug(f"Code Knowledge Graph scan skipped: {e}")

        return {
            "root_path": str(base),
            "project_name": base.name,
            "total_files": len(collected_files),
            "files_sample": collected_files[:60],
            "key_configs": key_configs,
            "file_types": dict(counts.most_common(5)),
            "code_graph": graph_summary,
        }

    @staticmethod
    def browse_local_directories(current_path: Optional[str] = None) -> Dict[str, Any]:
        """Allows safe local directory browsing for web UI folder picker."""
        if not current_path or current_path.strip() in ("", ".", "/"):
            target = Path.cwd().resolve()
        else:
            target = Path(current_path).resolve()

        if not target.exists() or not target.is_dir():
            target = Path.cwd().resolve()

        folders = []
        try:
            for item in sorted(target.iterdir()):
                if item.is_dir() and not item.name.startswith("."):
                    folders.append({
                        "name": item.name,
                        "path": str(item.resolve()),
                    })
        except Exception:
            pass

        parent_path = str(target.parent.resolve()) if target.parent != target else None
        return {
            "current_path": str(target),
            "parent_path": parent_path,
            "folders": folders[:100],
        }
