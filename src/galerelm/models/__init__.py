"""
galerelm.models — Modèles de données du framework SensAI.

Importe tous les modèles pour que SQLAlchemy les enregistre dans Base.metadata.
"""
from src.galerelm.models.base import Base
from src.galerelm.models.message import Message, MessageList, ToolCalls, ToolCallsFunction
from src.galerelm.models.options import Options
from src.galerelm.models.tools import Tools, ToolsFunction, ToolsList
from src.galerelm.models.response import ChatResponse, LogProb, TopLogProb
from src.galerelm.models.context import Context
from src.galerelm.models.deep_context import DeepContext, LongTermMemory
from src.galerelm.models.profile import Profile
from src.galerelm.models.chat import Chat
from src.galerelm.models.scheduled_task import ScheduledTask

__all__ = [
    "Base",
    # Message
    "Message", "MessageList", "ToolCalls", "ToolCallsFunction",
    # Options
    "Options",
    # Tools
    "Tools", "ToolsFunction", "ToolsList",
    # Response
    "ChatResponse", "LogProb", "TopLogProb",
    # Context & Memory
    "Context", "DeepContext", "LongTermMemory",
    # Profile
    "Profile",
    # Scheduled tasks
    "ScheduledTask",
    # Chat (objet métier, pas ORM)
    "Chat",
]