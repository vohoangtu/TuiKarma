"""Sandboxed Execution & Subprocess Tools for TUIKarma."""

from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from typing import Any, Optional
from tuikarma.tools.base import BaseTool


class ExecutePythonTool(BaseTool):
    """Tool to execute Python code in an isolated subprocess."""

    name = "execute_python"
    description = "Thực thi đoạn mã Python trong tiến trình con cô lập và thu thập kết quả stdout/stderr."
    requires_approval = False

    def __init__(self, workspace_root: Optional[Path] = None, timeout: float = 15.0) -> None:
        self.workspace_root = workspace_root or Path.cwd()
        self.timeout = timeout

    async def execute(self, code: str, **kwargs: Any) -> str:
        python_exe = sys.executable
        try:
            process = await asyncio.create_subprocess_exec(
                python_exe,
                "-c",
                code,
                cwd=str(self.workspace_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"Error: Execution timed out after {self.timeout}s."

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode

            output = []
            if stdout:
                output.append(f"STDOUT:\n{stdout}")
            if stderr:
                output.append(f"STDERR:\n{stderr}")
            output.append(f"Exit code: {exit_code}")
            return "\n".join(output)
        except Exception as e:
            return f"Error executing python code: {e}"


class RunCommandTool(BaseTool):
    """Tool to run shell/terminal commands within the sandbox."""

    name = "run_command"
    description = "Chạy một lệnh shell/CLI trong thư mục làm việc (Yêu cầu phê duyệt HITL)."
    requires_approval = True  # Security gate

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        timeout: float = 30.0,
        requires_approval: bool = True
    ) -> None:
        self.workspace_root = workspace_root or Path.cwd()
        self.timeout = timeout
        self.requires_approval = requires_approval

    async def execute(self, command: str, **kwargs: Any) -> str:
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(self.workspace_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"Error: Command timed out after {self.timeout}s."

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode

            output = []
            if stdout:
                output.append(f"STDOUT:\n{stdout}")
            if stderr:
                output.append(f"STDERR:\n{stderr}")
            output.append(f"Exit code: {exit_code}")
            return "\n".join(output)
        except Exception as e:
            return f"Error executing command '{command}': {e}"
