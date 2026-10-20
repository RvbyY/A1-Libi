"""
Module memory_tools.py
Outils orientés objet permettant au LLM d'interagir avec la mémoire court terme
et long terme (RAG) de la session active.
"""
from src.galerelm.models.message import MessageList
from ..ITools import ToolContext, ToolResult, ToolsInterface


class SearchMemoryTool(ToolsInterface):
    """Recherche dans la mémoire à long terme (RAG / DeepContext) de l'utilisateur."""

    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return "Search long-term persisted memory (RAG) for relevant past conversations."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to look up in long-term memory.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of relevant memories to return (default: 5).",
                },
            },
            "required": ["query"],
        }

    def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        query = str(arguments.get("query", "")).strip()
        top_k = int(arguments.get("top_k", 5))

        if not query:
            return ToolResult(False, "query is required to search memory.")

        profile = context.profile
        deep = getattr(profile, "deep_context", None) if profile else None
        if not deep or not getattr(deep, "memories", None):
            return ToolResult(True, "No long-term memories stored yet.", [])

        try:
            results = deep.search(query, context.api, top_k=top_k)
        except Exception as exc:
            return ToolResult(False, f"Memory search failed: {exc}")

        formatted = [
            {"id": mem.id, "role": mem.role, "content": mem.content, "score": score}
            for score, mem in results
        ]
        return ToolResult(
            True,
            f"Found {len(formatted)} relevant memory entries.",
            formatted,
        )


class ClearSessionTool(ToolsInterface):
    """Réinitialise la mémoire court terme (messages du contexte courant)."""

    @property
    def name(self) -> str:
        return "clear_session"

    @property
    def description(self) -> str:
        return "Clear the current short-term conversation context."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        del arguments
        chat_ctx = context.context
        if chat_ctx is None:
            return ToolResult(False, "No active conversation context available.")

        count = len(chat_ctx.messages)
        chat_ctx.messages = MessageList([])
        if context.session is not None:
            context.session.commit()

        return ToolResult(True, f"Cleared {count} messages from current session.")


class SummarizeSessionTool(ToolsInterface):
    """Génère un condensé structuré des messages présents dans la mémoire court terme."""

    @property
    def name(self) -> str:
        return "summarize_session"

    @property
    def description(self) -> str:
        return "Compress the current conversation history into a concise summary."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum character length per message preview (default: 120).",
                }
            },
            "required": [],
        }

    def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        max_chars = int(arguments.get("max_chars", 120))
        chat_ctx = context.context
        if chat_ctx is None or not getattr(chat_ctx, "messages", None):
            return ToolResult(True, "Current session is empty.", "")

        lines = []
        for idx, msg in enumerate(chat_ctx.messages, start=1):
            flat = msg.content.replace("\n", " ").strip()
            preview = flat if len(flat) <= max_chars else flat[:max_chars] + "..."
            lines.append(f"{idx}. [{msg.role}] {preview}")

        summary = "\n".join(lines)
        return ToolResult(
            True,
            f"Summarized {len(lines)} message(s): {summary}",
            summary,
        )