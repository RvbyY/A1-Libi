"""
Modèle Message et collection MessageList.
Représente un message dans une conversation (user, assistant, system, tool).
"""
import logging
from typing import Optional
from collections import UserList

from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

from src.galerelm.models.base import Base

logger = logging.getLogger("galerelm.models.message")


class ToolCallsFunction(Base):
    __tablename__ = "tool_calls_functions"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    tool_call_id: int = Column(Integer, ForeignKey("tool_calls.id"))

    name: str = Column(String, nullable=False)
    description: str = Column(Text, nullable=True)
    arguments: dict = Column(JSON, nullable=True)

    def __init__(self, name: str, description: str, arguments: dict):
        self.name = name
        self.description = description
        self.arguments = arguments

    def format(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments
        }

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            arguments=data.get("arguments", {})
        )


class ToolCalls(Base):
    __tablename__ = "tool_calls"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    message_id: int = Column(Integer, ForeignKey("messages.id"))

    functions = relationship("ToolCallsFunction", backref="tool_call", cascade="all, delete-orphan")

    def __init__(self, functions: list[ToolCallsFunction] = None):
        self.functions = functions if functions is not None else []

    def format(self) -> dict:
        if isinstance(self.functions, list) and len(self.functions) > 0:
            return {"function": self.functions[0].format()}
        return {"function": getattr(self.functions, "format", lambda: {})()}

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        func_data = data.get("function")
        if func_data and isinstance(func_data, dict):
            functions = [ToolCallsFunction.from_format(func_data)]
        else:
            functions = []
        return cls(functions=functions)


class Message(Base):
    """Un message dans une conversation. Peut être rattaché à un Context (persistant) ou à une ChatResponse."""
    __tablename__ = "messages"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    response_id: int = Column(Integer, ForeignKey("chat_responses.id"), nullable=True)
    context_id: int = Column(Integer, ForeignKey("contexts.id"), nullable=True)

    role: str = Column(String, nullable=False)
    content: str = Column(Text, nullable=False)
    images: list[str] = Column(JSON, nullable=True)
    thinking: Optional[str] = Column(Text, nullable=True)

    tool_calls = relationship("ToolCalls", backref="message", cascade="all, delete-orphan")

    def __init__(self, role: str, content: str, images: list[str] = None, tool_calls: list[ToolCalls] = None,
                 thinking: str = None):
        self.role = role
        self.content = content
        self.images = images if images is not None else []
        self.tool_calls = tool_calls if tool_calls is not None else []
        self.thinking = thinking

    def format(self) -> dict:
        res = {
            "role": self.role,
            "content": self.content,
        }
        if self.images:
            res["images"] = self.images
        if self.tool_calls:
            res["tool_calls"] = [tc.format() for tc in self.tool_calls]
        return res

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        tool_calls_data = data.get("tool_calls", [])
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            images=data.get("images", []),
            tool_calls=[ToolCalls.from_format(tc) for tc in tool_calls_data] if tool_calls_data else [],
            thinking=data.get("thinking")
        )


class MessageList(UserList):
    """Collection typée réservée aux objets Message."""

    def format_all(self, separator: str = "\n---\n") -> str:
        return separator.join([m.content for m in self.data])

    def format(self) -> list[dict]:
        return [m.format() for m in self.data]

    @classmethod
    def from_format(cls, data: list[dict]):
        if data is None:
            return cls([])
        return cls([Message.from_format(m) for m in data])
