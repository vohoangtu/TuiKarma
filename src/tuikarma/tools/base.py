"""Base Tool abstraction and Tool Registry for TUIKarma."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None


class BaseTool(ABC):
    """Abstract base class for all tools available to agents."""

    name: str
    description: str
    requires_approval: bool = False

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Executes the tool with the given arguments."""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Returns JSON-schema compatible specification of the tool."""
        return {
            "name": self.name,
            "description": self.description,
            "requires_approval": self.requires_approval,
        }


class ToolRegistry:
    """Central registry of executable tools accessible to agents."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Registers a tool instance."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieves a registered tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> Dict[str, Dict[str, Any]]:
        """Lists metadata of all registered tools."""
        return {name: tool.get_schema() for name, tool in self._tools.items()}

    def contains(self, name: str) -> bool:
        return name in self._tools
