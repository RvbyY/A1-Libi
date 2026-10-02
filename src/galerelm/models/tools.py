"""
Modèles Tools pour le function calling.
"""
from collections import UserList

from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

from src.galerelm.models.base import Base


class ToolsFunction(Base):
    __tablename__ = "tools_functions"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    tool_id: int = Column(Integer, ForeignKey("tools.id"))

    name: str = Column(String, nullable=False)
    parameters: dict = Column(JSON, nullable=True)
    description: str = Column(Text, nullable=True)

    def __init__(self, name: str, parameters: dict, description: str):
        self.name = name
        self.parameters = parameters
        self.description = description

    def format(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            parameters=data.get("parameters", {})
        )


class Tools(Base):
    __tablename__ = "tools"
    id: int = Column(Integer, primary_key=True, autoincrement=True)

    tool_type: str = Column(String, nullable=False)
    tool_function = relationship("ToolsFunction", uselist=False, backref="tool", cascade="all, delete-orphan")

    def __init__(self, tool_type: str, tool_function: ToolsFunction):
        self.tool_type = tool_type
        self.tool_function = tool_function

    def format(self) -> dict:
        return {
            "type": self.tool_type,
            "function": self.tool_function.format() if self.tool_function else None
        }

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(
            tool_type=data.get("type", "function"),
            tool_function=ToolsFunction.from_format(data.get("function", {}))
        )


class ToolsList(UserList):
    """Collection typée réservée aux objets Tools."""

    def format(self) -> list[dict]:
        return [t.format() for t in self.data]

    @classmethod
    def from_format(cls, data: list[dict]):
        if data is None:
            return cls([])
        return cls([Tools.from_format(t) for t in data])
