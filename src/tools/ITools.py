from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class ToolContext:
    user_id: str
    user_email: str | None = None
    user_token: str | None = None

@dataclass
class ToolResult:
    success: bool
    message: str
    data: Any = None

class ToolsInterface(ABC):
    """Interface for context tools"""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def parameters(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        raise NotImplementedError