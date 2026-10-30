"""
Module registry.py
Contient ToolRegistry (registre unifié avec ToolsList) et ToolExecutor
(exécuteur des appels d'outils demandés par le LLM).
"""
import logging
import time
from typing import Any, Callable, Optional

from src.galerelm.models.message import Message
from src.galerelm.models.tools import ToolsList
from .ITools import ToolContext, ToolResult, ToolsInterface

logger = logging.getLogger("sensai.tools")

# Callback de confirmation : reçoit (nom de l'outil, arguments) et renvoie True si l'utilisateur accepte.
ConfirmCallback = Callable[[str, dict], bool]

# Callback d'observation : reçoit (nom de l'outil, arguments, résultat, durée en ms) après chaque appel.
ToolCallObserver = Callable[[str, dict, "ToolResult", float], None]


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

    def __init__(
        self,
        registry: ToolRegistry,
        confirm: Optional[ConfirmCallback] = None,
        on_call: Optional[ToolCallObserver] = None,
    ):
        self.registry = registry
        self.confirm = confirm
        self.on_call = on_call

    def refusal_for(self, name: str, arguments: dict) -> Optional[ToolResult]:
        """
        Vérifie la confirmation des outils marqués requires_confirmation.
        Retourne un ToolResult d'échec si l'action est refusée (ou si personne ne peut la confirmer),
        None si l'exécution peut continuer.
        """
        tool = self.registry.get(name)
        if tool is None or not tool.requires_confirmation:
            return None

        approved = False
        if self.confirm is not None:
            try:
                approved = bool(self.confirm(name, arguments))
            except Exception as exc:
                logger.error(f"[ToolExecutor] Échec de la demande de confirmation pour {name}: {exc}")

        if approved:
            return None
        logger.info(f"[ToolExecutor] Outil {name} non confirmé par l'utilisateur : exécution annulée.")
        return ToolResult(False, f"Action '{name}' annulée : l'utilisateur ne l'a pas confirmée.")

    def _report_call(self, name: str, arguments: dict, result: ToolResult, duration_ms: float) -> None:
        """Journalise l'appel et le transmet à l'observateur (affichage CLI, visualiseur...)."""
        logger.info(
            f"[ToolExecutor] {name} args={arguments} success={result.success} "
            f"durée={duration_ms:.0f}ms message={result.message!r}"
        )
        if self.on_call is None:
            return
        try:
            self.on_call(name, arguments, result, duration_ms)
        except Exception as exc:
            logger.error(f"[ToolExecutor] Échec de l'observateur d'appels pour {name}: {exc}")

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
                started = time.perf_counter()
                res = self.refusal_for(func.name, func.arguments or {})
                if res is None:
                    try:
                        res = self.registry.execute(
                            func.name,
                            tool_context,
                            func.arguments or {},
                        )
                    except Exception as exc:
                        logger.error(f"[ToolExecutor] Échec de l'outil {func.name}: {exc}")
                        res = ToolResult(False, f"Erreur: {exc}")

                duration_ms = (time.perf_counter() - started) * 1000
                self._report_call(func.name, func.arguments or {}, res, duration_ms)
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
        return tool.execute(context, arguments)
