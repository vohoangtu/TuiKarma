"""Code Knowledge Graph Tool for TUIKarma Agents.
Provides architectural navigation, dependency path finding, and impact analysis.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, Optional

from tuikarma.tools.base import BaseTool
from tuikarma.graph.engine import CodeKnowledgeGraphEngine


class CodeGraphTool(BaseTool):
    """Tool allowing autonomous agents to query architectural graphs and perform impact analysis."""

    name: str = "code_graph"
    description: str = (
        "Truy vấn đồ thị tri thức mã nguồn (Code Knowledge Graph): tìm kiếm quan hệ phụ thuộc, "
        "hàm gọi/được gọi, phân tích tác động (impact analysis) khi sửa code, và tìm đường đi kiến trúc."
    )
    requires_approval: bool = False

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.engine = CodeKnowledgeGraphEngine(self.workspace_root)

    def set_workspace_root(self, new_root: Path) -> None:
        """Updates root directory when switching project workspaces."""
        self.workspace_root = Path(new_root).resolve()
        self.engine = CodeKnowledgeGraphEngine(self.workspace_root)

    async def execute(
        self,
        action: str = "summary",
        symbol: Optional[str] = None,
        target_symbol: Optional[str] = None,
        max_depth: int = 2,
        **kwargs: Any
    ) -> str:
        """Executes graph query action."""
        action_lower = action.lower().strip()

        if action_lower == "summary":
            summary = self.engine.get_summary()
            return json.dumps(summary, indent=2, ensure_ascii=False)

        elif action_lower == "query":
            if not symbol:
                return "Lỗi: Vui lòng cung cấp tham số 'symbol' để tra cứu."
            res = self.engine.query_symbol(symbol)
            return json.dumps(res, indent=2, ensure_ascii=False)

        elif action_lower == "path":
            if not symbol or not target_symbol:
                return "Lỗi: Vui lòng cung cấp cả 'symbol' và 'target_symbol' để tìm đường đi."
            res = self.engine.find_path(symbol, target_symbol)
            return json.dumps(res, indent=2, ensure_ascii=False)

        elif action_lower == "impact":
            if not symbol:
                return "Lỗi: Vui lòng cung cấp tham số 'symbol' để phân tích tác động."
            res = self.engine.impact_analysis(symbol, max_depth=max_depth)
            return json.dumps(res, indent=2, ensure_ascii=False)

        elif action_lower == "cycles":
            summary = self.engine.get_summary()
            cycles = summary.get("import_cycles", [])
            return json.dumps({"import_cycles": cycles, "count": len(cycles)}, indent=2, ensure_ascii=False)

        else:
            return f"Hành động không hợp lệ: '{action}'. Các hành động hỗ trợ: 'summary', 'query', 'path', 'impact', 'cycles'."
