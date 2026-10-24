"""
Package src.tools
Exporte l'interface ToolsInterface, le registre ToolRegistry, l'exécuteur ToolExecutor
et l'ensemble des outils intégrés du framework SensAI.
"""
from .ITools import ToolContext, ToolResult, ToolsInterface
from .registry import ToolExecutor, ToolRegistry
from .calendar.calendar_tools import Calendar
from .communication.communication_tools import NotificationTool
from .communication.discord import Discord
from .communication.email import Email
from .communication.telegram import Telegram
from .memory.memory_tools import ClearSessionTool, SearchMemoryTool, SummarizeSessionTool
from .tasks.complete_task import CompleteTaskTool
from .tasks.create_task import CreateTaskTool
from .tasks.send_task_file import SendTaskFileTool

BUILTIN_TOOLS: tuple[type[ToolsInterface], ...] = (
    Calendar,
    Email,
    Discord,
    Telegram,
    NotificationTool,
    SearchMemoryTool,
    ClearSessionTool,
    SummarizeSessionTool,
    CreateTaskTool,
    CompleteTaskTool,
    SendTaskFileTool,
)


def default_tool_registry() -> ToolRegistry:
    """Construit un ToolRegistry pré-rempli avec tous les outils intégrés."""
    return ToolRegistry([tool_cls() for tool_cls in BUILTIN_TOOLS])


__all__ = [
    "ToolsInterface",
    "ToolContext",
    "ToolResult",
    "ToolRegistry",
    "ToolExecutor",
    "BUILTIN_TOOLS",
    "default_tool_registry",
    "Calendar",
    "Email",
    "Discord",
    "Telegram",
    "NotificationTool",
    "SearchMemoryTool",
    "ClearSessionTool",
    "SummarizeSessionTool",
    "CreateTaskTool",
    "CompleteTaskTool",
    "SendTaskFileTool",
]
