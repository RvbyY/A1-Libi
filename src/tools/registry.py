"""
Module registry.py
Contient ToolRegistry (registre unifié avec ToolsList) et ToolExecutor
(exécuteur des appels d'outils demandés par le LLM).
"""
import logging
from typing import Any, Optional

from src.galerelm.models.message import Message
from src.galerelm.models.tools import ToolsList
from .ITools import ToolContext, ToolResult, ToolsInterface

logger = logging.getLogger("sensai.tools")


class ToolRegistry:
    """
    Registre central des outils disponibles pour le LLM.
    S'intègre nativement avec ToolsList via to_tools_list().
    """

    def __init__(self, tools: Optional[list[ToolsInterface]] = None) -> None:
        self._tools: dict[str, ToolsInterface] = {}
        if tools:
            for tool in tools:
                self.register(tool)

    def register(self, tool: ToolsInterface) -> "ToolRegistry":
        """Enregistre un outil dans le registre."""
        self._tools[tool.name] = tool
        return self

    def get(self, name: str) -> Optional[ToolsInterface]:
        return self._tools.get(name)

    def all(self) -> list[ToolsInterface]:
        return list(self._tools.values())

    def to_tools_list(self) -> ToolsList:
        """Convertit les outils enregistrés en instance ToolsList pour Chat."""
        return ToolsList([tool.to_model() for tool in self._tools.values()])

    def definition(self) -> list[dict]:
        """Retourne la liste des schémas JSON des outils."""
        return self.to_tools_list().format()

    def execute(self, name: str, context: ToolContext, arguments: dict) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        return tool.execute(context, arguments or {})

    def __len__(self) -> int:
        return len(self._tools)

    def __bool__(self) -> bool:
        return bool(self._tools)


class ToolExecutor:
    """
    Orchestre l'exécution des tool_calls émis par le LLM, construit le ToolContext
    et persiste les réponses de rôle 'tool' dans le Context conversationnel.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def build_tool_context(
        self,
        profile: Any,
        session: Any = None,
        context: Any = None,
        api: Any = None,
        task_manager: Any = None,
    ) -> ToolContext:
        return ToolContext(
            user_id=getattr(profile, "id", ""),
            user_email=getattr(profile, "email", None),
            session=session,
            profile=profile,
            context=context,
            api=api,
            task_manager=task_manager,
        )

    def execute_calls(
        self,
        assistant_msg: Message,
        tool_context: ToolContext,
    ) -> list[tuple[str, ToolResult]]:
        """
        Exécute chaque fonction appelée dans assistant_msg.tool_calls,
        ajoute les messages de rôle 'tool' dans tool_context.context et commit la session.
        """
        if not self.registry or not assistant_msg or not assistant_msg.tool_calls:
            return []

        results: list[tuple[str, ToolResult]] = []
        chat_context = tool_context.context
        session = tool_context.session

        for tc in assistant_msg.tool_calls:
            for func in tc.functions:
                try:
                    res = self.registry.execute(
                        func.name,
                        tool_context,
                        func.arguments or {},
                    )
                except Exception as exc:
                    logger.error(f"[ToolExecutor] Échec de l'outil {func.name}: {exc}")
                    res = ToolResult(False, f"Erreur: {exc}")

                results.append((func.name, res))
                if chat_context is not None:
                    output_text = f"[{func.name}] {res.message}"
                    chat_context.add(
                        Message(role="tool", content=output_text),
                        api_client=tool_context.api,
                    )

        if results and session is not None:
            session.commit()

        return results
