from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from src.galerelm.models.tools import Tools, ToolsFunction


@dataclass
class ToolContext:
    """Contexte d'exécution transmis aux outils lors d'un appel par le LLM."""
    user_id: str
    user_email: Optional[str] = None
    user_token: Optional[str] = None
    session: Any = None
    profile: Any = None
    context: Any = None
    api: Any = None
    task_manager: Any = None


@dataclass
class ToolResult:
    """Résultat standardisé retourné par l'exécution d'un outil."""
    success: bool
    message: str
    data: Any = None


class ToolsInterface(ABC):
    """Contrat abstrait que chaque outil du framework SensAI doit implémenter."""

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

    def to_model(self) -> Tools:
        """Convertit l'outil en modèle Tools compatible avec Chat et ToolsList."""
        return Tools(
            tool_type="function",
            tool_function=ToolsFunction(
                name=self.name,
                parameters=self.parameters,
                description=self.description,
            ),
        )

    def to_dict(self) -> dict:
        """Retourne la définition JSON Schema au format attendu par Ollama."""
        return self.to_model().format()