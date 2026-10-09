"""Sandboxed File System Tools for TUIKarma."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any, List, Optional
from tuikarma.tools.base import BaseTool


def resolve_sandboxed_path(path_str: str, root_dir: Path) -> Path:
    """Safely resolve path within sandbox root directory, preventing directory traversal."""
    root_resolved = root_dir.resolve()
    clean_path = path_str.lstrip("/\\")
    target_path = (root_resolved / clean_path).resolve()
    try:
        target_path.relative_to(root_resolved)
    except ValueError:
        raise PermissionError(f"Access denied: path '{path_str}' is outside sandbox root '{root_resolved}'.")
    return target_path


class ReadFileTool(BaseTool):
    """Tool to safely read file content within the sandbox workspace."""

    name = "read_file"
    description = "Đọc nội dung của một file văn bản trong thư mục sandbox làm việc."
    requires_approval = False

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.workspace_root = workspace_root or Path.cwd()

    async def execute(self, filepath: str, **kwargs: Any) -> str:
        safe_path = resolve_sandboxed_path(filepath, self.workspace_root)
        if not safe_path.exists():
            return f"Error: File '{filepath}' does not exist."
        if not safe_path.is_file():
            return f"Error: Path '{filepath}' is not a regular file."
        
        try:
            content = safe_path.read_text(encoding="utf-8")
            return content
        except Exception as e:
            return f"Error reading file '{filepath}': {e}"


class WriteFileTool(BaseTool):
    """Tool to safely write content to a file within the sandbox workspace."""

    name = "write_file"
    description = "Ghi nội dung mã nguồn hoặc văn bản vào file trong thư mục sandbox làm việc."
    requires_approval = False

    def __init__(self, workspace_root: Optional[Path] = None, requires_approval: bool = False) -> None:
        self.workspace_root = workspace_root or Path.cwd()
        self.requires_approval = requires_approval

    async def execute(self, filepath: str, content: str, **kwargs: Any) -> str:
        safe_path = resolve_sandboxed_path(filepath, self.workspace_root)
        try:
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            safe_path.write_text(content, encoding="utf-8")
            line_count = len(content.splitlines())
            return f"Successfully wrote {len(content)} bytes ({line_count} lines) to '{filepath}'."
        except Exception as e:
            return f"Error writing file '{filepath}': {e}"


class ListDirTool(BaseTool):
    """Tool to list directory contents within the sandbox workspace."""

    name = "list_dir"
    description = "Liệt kê danh sách các file và thư mục con trong đường dẫn sandbox."
    requires_approval = False

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.workspace_root = workspace_root or Path.cwd()

    async def execute(self, path: str = ".", **kwargs: Any) -> str:
        safe_path = resolve_sandboxed_path(path, self.workspace_root)
        if not safe_path.exists():
            return f"Error: Directory '{path}' does not exist."
        if not safe_path.is_dir():
            return f"Error: Path '{path}' is not a directory."
        
        try:
            entries = sorted(os.listdir(safe_path))
            results = []
            for entry in entries:
                sub_path = safe_path / entry
                if sub_path.is_dir():
                    results.append(f"[DIR]  {entry}/")
                else:
                    results.append(f"[FILE] {entry} ({sub_path.stat().st_size} bytes)")
            return "\n".join(results) if results else "(Empty directory)"
        except Exception as e:
            return f"Error listing directory '{path}': {e}"
