"""Filesystem Transactional Snapshot & Rollback Manager for Sandboxed Workspace."""

from __future__ import annotations
import shutil
from pathlib import Path
from typing import Dict, List, Set, Optional


class SandboxSnapshotManager:
    """Manages transactional snapshots of the sandbox workspace for physical rollback."""

    IGNORE_PATTERNS = {
        "__pycache__",
        ".pytest_cache",
        ".git",
        ".venv",
        ".DS_Store",
    }

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.checkpoints: Dict[str, Dict[str, bytes]] = {}

    def _should_ignore(self, path: Path) -> bool:
        """Checks if a path belongs to an ignored directory or file pattern."""
        for part in path.parts:
            if part in self.IGNORE_PATTERNS or part.endswith(".pyc"):
                return True
        return False

    def capture_snapshot(self) -> Dict[str, bytes]:
        """Captures the current state of all files in workspace as relative_path -> bytes."""
        snapshot: Dict[str, bytes] = {}
        if not self.workspace_root.exists():
            return snapshot

        for file_path in self.workspace_root.rglob("*"):
            if file_path.is_file() and not self._should_ignore(file_path):
                try:
                    rel_path = file_path.relative_to(self.workspace_root).as_posix()
                    snapshot[rel_path] = file_path.read_bytes()
                except (OSError, PermissionError):
                    continue

        return snapshot

    def create_checkpoint(self, checkpoint_id: str) -> None:
        """Creates and stores a named checkpoint representing current workspace state."""
        self.checkpoints[checkpoint_id] = self.capture_snapshot()

    def restore_checkpoint(self, checkpoint_id: str) -> List[str]:
        """Reverts the workspace to the exact state saved in checkpoint_id.
        
        Returns a list of actions performed (e.g. 'restored: app.py', 'removed: bad.py').
        """
        if checkpoint_id not in self.checkpoints:
            raise KeyError(f"Checkpoint '{checkpoint_id}' not found in snapshot manager.")

        target_state = self.checkpoints[checkpoint_id]
        actions_taken: List[str] = []

        # 1. Identify current files
        current_state = self.capture_snapshot()

        # 2. Delete files that did not exist in target checkpoint
        for rel_path in current_state.keys():
            if rel_path not in target_state:
                abs_path = self.workspace_root / rel_path
                try:
                    if abs_path.exists():
                        abs_path.unlink()
                        actions_taken.append(f"removed: {rel_path}")
                except OSError as e:
                    actions_taken.append(f"failed_to_remove: {rel_path} ({e})")

        # 3. Clean up empty directories
        for dir_path in sorted(self.workspace_root.rglob("*"), reverse=True):
            if dir_path.is_dir() and not self._should_ignore(dir_path):
                try:
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                except OSError:
                    pass

        # 4. Restore or overwrite files from target checkpoint
        for rel_path, file_bytes in target_state.items():
            abs_path = self.workspace_root / rel_path
            current_bytes = current_state.get(rel_path)

            if current_bytes != file_bytes:
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_bytes(file_bytes)
                if rel_path not in current_state:
                    actions_taken.append(f"restored_created: {rel_path}")
                else:
                    actions_taken.append(f"restored_modified: {rel_path}")

        return actions_taken

    def get_diff(self, checkpoint_id: str) -> Dict[str, List[str]]:
        """Returns differences between checkpoint and current workspace state."""
        if checkpoint_id not in self.checkpoints:
            return {"added": [], "modified": [], "deleted": []}

        saved_state = self.checkpoints[checkpoint_id]
        current_state = self.capture_snapshot()

        added = [p for p in current_state if p not in saved_state]
        deleted = [p for p in saved_state if p not in current_state]
        modified = [p for p in saved_state if p in current_state and saved_state[p] != current_state[p]]

        return {"added": added, "modified": modified, "deleted": deleted}

    def clear(self) -> None:
        """Clears all stored checkpoints."""
        self.checkpoints.clear()
