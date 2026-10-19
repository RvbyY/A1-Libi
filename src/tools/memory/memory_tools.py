from collections.abc import Callable
from typing import Any
from ..ITools import ToolContext, ToolResult, ToolsInterface
from ...galerelm.models import Context, DeepContext


class Memory(ToolsInterface):
    def __init__(
        self,
        session_factory: Callable[[], Any],
        api_client: Any | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._api_client = api_client

    @property
    def name(self) -> str:
        return "memory"

    @property
    def description(self) -> str:
        return "Summarize, search, or clear a conversation's memory."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["summarize", "search", "clear"],
                    "description": "Memory operation to perform.",
                },
                "session_id": {
                    "type": "string",
                    "description": "Database id of the conversation context.",
                },
                "query": {
                    "type": "string",
                    "description": "Search text, required for the search operation.",
                },
            },
            "required": ["action", "session_id"],
        }

    def summarize_session(self, session_id: str) -> str:
        with self._session_factory() as session:
            context = self._get_context(session, session_id)
            if not context.messages:
                return "La session ne contient aucun message."

            return "\n".join(
                f"{message.role}: {message.content}" for message in context.messages
            )

    def search_memory(self, session_id: str, query: str) -> list[dict]:
        if not query.strip():
            raise ValueError("query ne peut pas être vide.")

        with self._session_factory() as session:
            context = self._get_context(session, session_id)
            deep_context = (
                session.query(DeepContext)
                .filter_by(profile_id=context.profile_id)
                .first()
            )

            if deep_context is None:
                return []
            if self._api_client is not None:
                results = deep_context.search(query, self._api_client)
                if results:
                    return [
                        {
                            "id": memory.id,
                            "role": memory.role,
                            "content": memory.content,
                            "score": score,
                        }
                        for score, memory in results
                    ]
            query_lower = query.casefold()
            return [
                {
                    "id": memory.id,
                    "role": memory.role,
                    "content": memory.content,
                    "score": None,
                }
                for memory in deep_context.memories
                if query_lower in memory.content.casefold()
            ]

    def clear_session(self, session_id: str) -> bool:
        with self._session_factory() as session:
            context = self._get_context(session, session_id)
            context.messages.clear()
            session.commit()
            return True

    @staticmethod
    def _get_context(session: Any, session_id: str) -> Context:
        try:
            context_id = int(session_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("session_id doit être un identifiant numérique.") from exc

        context = session.query(Context).filter_by(id=context_id).first()
        if context is None:
            raise ValueError(f"Session introuvable: {session_id}")
        return context

    def execute(self, context: ToolContext, payload: dict) -> ToolResult:
        try:
            action = payload.get("action")
            session_id = payload.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                raise ValueError("session_id est obligatoire.")

            self._check_ownership(context, session_id)
            if action == "summarize":
                summary = self.summarize_session(session_id)
                return ToolResult(True, "Session résumée.", summary)
            if action == "search":
                query = payload.get("query")
                if not isinstance(query, str):
                    raise ValueError("query est obligatoire pour une recherche.")
                results = self.search_memory(session_id, query)
                return ToolResult(True, f"{len(results)} mémoire(s) trouvée(s).", results)
            if action == "clear":
                self.clear_session(session_id)
                return ToolResult(True, "Mémoire courte réinitialisée.")

            raise ValueError("action doit être summarize, search ou clear.")
        except (ValueError, TypeError) as exc:
            return ToolResult(False, str(exc))

    def _check_ownership(self, tool_context: ToolContext, session_id: str) -> None:
        with self._session_factory() as session:
            stored_context = self._get_context(session, session_id)
            if stored_context.profile_id != tool_context.user_id:
                raise ValueError("La session n'appartient pas à l'utilisateur courant.")
