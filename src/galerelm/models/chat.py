"""
Module chat.py
Contient la logique de construction et d'exécution d'une requête de chat vers un LLM.
Pour une documentation détaillée, voir chat.md.
"""
import logging
from typing import Literal, Optional, Union

from src.galerelm.models.message import Message, MessageList, ToolCalls
from src.galerelm.models.options import Options
from src.galerelm.models.tools import ToolsList
from src.galerelm.models.response import ChatResponse
from src.rapideAPI.client import RapideAPI

logger = logging.getLogger("galerelm.models.chat")

Think = Literal["high", "medium", "low", "max"]
Format = Literal["json"]


class Chat:
    """
    Objet éphémère qui encapsule une requête de chat.
    Construit le payload, exécute le stream, et stocke la réponse.
    (Voir chat.md pour la documentation complète).
    """

    def __init__(
        self,
        model: str,
        api: RapideAPI,
        messages: MessageList = None,
        tools: ToolsList = None,
        options: Options = None,
        system_prompt: str = None,
        think: Union[bool, Think] = None,
        keep_alive: Union[str, int] = "2m",
        logprobs: bool = False,
        top_logprobs: int = None,
        request_format: Format = None,
        stream: bool = True,
    ):
        self.model = model
        self.api = api
        self.messages = messages if messages is not None else MessageList([])
        self.tools = tools if tools is not None else ToolsList([])
        self.options = options if options is not None else Options()
        self.stream = stream
        self.think = think
        self.keep_alive = keep_alive
        self.logprobs = logprobs
        self.top_logprobs = top_logprobs
        self.request_format = request_format
        self.last_response: Optional[ChatResponse] = None

        if system_prompt:
            self._set_system_prompt(system_prompt)

    # ── Construction du payload ──────────────────────────────────────

    def format(self) -> dict:
        """Construit le dictionnaire JSON à envoyer à l'API Ollama."""
        res = {
            "model": self.model,
            "messages": self.messages.format() if self.messages else [],
            "stream": self.stream,
        }
        if self.tools:
            res["tools"] = self.tools.format()
        if self.request_format:
            res["format"] = self.request_format
        if self.options:
            res["options"] = self.options.format()
        if self.think is not None:
            res["think"] = self.think
        if self.keep_alive is not None:
            res["keep_alive"] = self.keep_alive
        if self.logprobs:
            res["logprobs"] = self.logprobs
        if self.top_logprobs is not None:
            res["top_logprobs"] = self.top_logprobs
        return res

    # ── Exécution ────────────────────────────────────────────────────

    def execute_stream(self, api_client: RapideAPI = None):
        """
        Envoie la requête de chat à l'API en streaming, yield chaque token
        pour un affichage en temps réel, et enregistre le résultat final
        complet dans self.last_response.
        """
        client = api_client or self.api
        full_response = []
        final_chunk = None
        logger.info(f"[Chat] Démarrage de la génération avec le modèle {self.model}...")

        for chunk in client.stream_ndjson("api/chat", json_data=self.format()):
            token = chunk.get("message", {}).get("content", "")
            if token:
                full_response.append(token)
                yield token

            if chunk.get("done", False):
                final_chunk = chunk

        if final_chunk:
            if "message" not in final_chunk:
                final_chunk["message"] = {}
            final_chunk["message"]["role"] = "assistant"
            final_chunk["message"]["content"] = "".join(full_response)
            self.last_response = ChatResponse.from_format(final_chunk)
            logger.info(
                f"[Chat] Génération terminée. "
                f"(Tokens: {self.last_response.eval_count}, "
                f"Durée: {self.last_response.eval_duration / 1e9:.2f}s)"
            )

    def ask(self, content: str, images: list[str] = None, tool_calls: list[ToolCalls] = None, think: str = None):
        """Raccourci : ajoute le prompt utilisateur, streame, et ajoute la réponse assistant."""
        self.add_user_prompt(content, images, tool_calls, think)
        for token in self.execute_stream():
            print(token, end="", flush=True)
        print()

        if self.last_response and self.last_response.message:
            response = self.last_response.message
            self.add_assistant_response(response.content, response.images, response.tool_calls)

    # ── Gestion des messages ─────────────────────────────────────────

    def add_message(self, content: str, images: list[str] = None, tool_calls: list[ToolCalls] = None,
                    thinking: str = None, role: str = "user"):
        message = Message(role, content, images, tool_calls, thinking)
        self.messages.append(message)

    def _set_system_prompt(self, content: str):
        """Injecte le prompt système à la position 0. Idempotent."""
        if self.messages and len(self.messages) > 0 and self.messages[0].role == "system":
            return
        message = Message(role="system", content=content)
        self.messages.insert(0, message)

    def add_user_prompt(self, content: str, images: list[str] = None, tool_calls: list[ToolCalls] = None,
                        thinking: str = None):
        self.add_message(content, images, tool_calls, thinking, role="user")

    def add_assistant_response(self, content: str, images: list[str] = None, tool_calls: list[ToolCalls] = None):
        self.add_message(content, images, tool_calls, role="assistant")