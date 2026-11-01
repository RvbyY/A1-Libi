"""
Module chat.py
Contient la logique de construction et d'exécution d'une requête de chat vers un LLM.
Pour une documentation détaillée, voir chat.md.
"""
import json
import logging
import re
from typing import Literal, Optional, Union

from src.galerelm.models.message import Message, MessageList, ToolCalls
from src.galerelm.models.options import Options
from src.galerelm.models.prompt import Prompt
from src.galerelm.models.tools import ToolsList
from src.galerelm.models.response import ChatResponse
from src.galerelm.ollama import OllamaError
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
        system_prompt: Union[str, Prompt] = None,
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
        if tools is None:
            self.tools = ToolsList([])
        elif hasattr(tools, "to_tools_list") and callable(tools.to_tools_list):
            self.tools = tools.to_tools_list()
        else:
            self.tools = tools
        self.options = options if options is not None else Options()
        self.stream = stream
        self.think = think
        self.keep_alive = keep_alive
        self.logprobs = logprobs
        self.top_logprobs = top_logprobs
        self.request_format = request_format
        self.last_response: Optional[ChatResponse] = None

        if system_prompt:
            self._set_system_prompt(str(system_prompt))

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
        accumulated_tool_calls = []
        final_chunk = None
        logger.info(f"[Chat] Démarrage de la génération avec le modèle {self.model}...")

        for chunk in client.stream_ndjson("api/chat", json_data=self.format()):
            if "error" in chunk:
                # Ollama peut signaler une erreur au milieu du flux avec un statut HTTP 200
                raise OllamaError(f"Erreur Ollama pendant la génération : {chunk['error']}")
            msg_chunk = chunk.get("message", {})
            token = msg_chunk.get("content", "")
            if token:
                full_response.append(token)

            chunk_tools = msg_chunk.get("tool_calls")
            if chunk_tools:
                accumulated_tool_calls.extend(chunk_tools)

            if chunk.get("done", False):
                final_chunk = chunk

        if final_chunk:
            if "message" not in final_chunk:
                final_chunk["message"] = {}
            final_chunk["message"]["role"] = "assistant"
            final_chunk["message"]["content"] = "".join(full_response)
            textual_tool_call = None
            if accumulated_tool_calls:
                final_chunk["message"]["tool_calls"] = accumulated_tool_calls
            else:
                textual_tool_call = self._parse_textual_tool_call(final_chunk["message"]["content"])
                if textual_tool_call:
                    final_chunk["message"]["tool_calls"] = [textual_tool_call]
                    final_chunk["message"]["content"] = ""
            if textual_tool_call is None and full_response:
                yield "".join(full_response)
            self.last_response = ChatResponse.from_format(final_chunk)
            logger.info(
                f"[Chat] Génération terminée. "
                f"(Tokens: {self.last_response.eval_count}, "
                f"Durée: {self.last_response.eval_duration / 1e9:.2f}s)"
            )

    def _parse_textual_tool_call(self, content: str) -> Optional[dict]:
        """Convertit un appel JSON produit en texte par les modèles sans tool-calling natif."""
        candidate = content.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", candidate, re.IGNORECASE | re.DOTALL)
        if fenced:
            candidate = fenced.group(1).strip()
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict) and isinstance(payload.get("tool_calls"), list):
            payload = payload["tool_calls"][0] if payload["tool_calls"] else None
        elif isinstance(payload, dict) and isinstance(payload.get("tool_call"), dict):
            payload = payload["tool_call"]

        if isinstance(payload, dict) and isinstance(payload.get("function"), dict):
            payload = payload["function"]

        if isinstance(payload, dict) and isinstance(payload.get("arguments"), dict):
            name = payload.get("name") or payload.get("tool")
            arguments = payload["arguments"]
        elif isinstance(payload, dict):
            name = None
            arguments = payload
        else:
            name, arguments = self._infer_explicit_tool_call()
            if name is None:
                return None

        if name:
            if not isinstance(name, str) or not any(
                tool.tool_function and tool.tool_function.name == name
                for tool in self.tools
            ):
                return None
        else:
            candidates = [
                tool.tool_function
                for tool in self.tools
                if tool.tool_function
                and isinstance(tool.tool_function.parameters, dict)
                and set(arguments).issubset(tool.tool_function.parameters.get("properties", {}))
            ]
            if len(candidates) == 1:
                name = candidates[0].name
            else:
                name, arguments = self._infer_explicit_tool_call()
                if name is None:
                    return None

        definition = next(
            (tool.tool_function for tool in self.tools if tool.tool_function and tool.tool_function.name == name),
            None,
        )
        if definition is None:
            return None
        required = definition.parameters.get("required", [])
        if name == "discord" and "recipient" in required and "recipient" not in arguments:
            user_messages = [message.content for message in self.messages if message.role == "user"]
            recipient_ids = re.findall(r"\b\d{17,20}\b", "\n".join(user_messages))
            if len(recipient_ids) == 1:
                arguments = {**arguments, "recipient": recipient_ids[0]}
        if any(field not in arguments for field in required):
            return None
        return {"function": {"name": name, "arguments": arguments}}

    def _infer_explicit_tool_call(self) -> tuple[Optional[str], dict]:
        """Builds a call only when the latest user request explicitly supplies all inputs."""
        if self.messages and self.messages[-1].role == "tool":
            return None, {}
        user_messages = [message.content for message in self.messages if message.role == "user"]
        request = user_messages[-1] if user_messages else ""
        if not re.search(r"\bdiscord\b", request, re.IGNORECASE):
            return None, {}

        discord = next(
            (tool.tool_function for tool in self.tools if tool.tool_function and tool.tool_function.name == "discord"),
            None,
        )
        if discord is None:
            return None, {}

        recipient_ids = re.findall(r"\b\d{17,20}\b", request)
        content_match = re.search(r"""["“](.+?)["”]""", request, re.DOTALL)
        if len(recipient_ids) != 1 or content_match is None:
            return None, {}
        return "discord", {
            "recipient": recipient_ids[0],
            "content": content_match.group(1),
        }

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