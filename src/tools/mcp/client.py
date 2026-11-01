"""
Module tools/mcp/client.py
Client MCP (Model Context Protocol) minimal, transport stdio : JSON-RPC 2.0, un message JSON par ligne.

Cycle de vie : lancement du serveur (sous-processus), initialize, notifications/initialized,
tools/list, puis tools/call à chaque appel du modèle. Aucun framework : seulement la bibliothèque standard.
"""
import json
import logging
import os
import queue
import subprocess
import threading
from typing import Any, Optional

logger = logging.getLogger("sensai.tools.mcp")

PROTOCOL_VERSION = "2024-11-05"
CLIENT_INFO = {"name": "sensai", "version": "0.1"}


class McpError(RuntimeError):
    """Erreur de communication avec un serveur MCP (lancement, délai dépassé, réponse d'erreur)."""


class McpClient:
    def __init__(self, command: list[str], env: Optional[dict[str, str]] = None, cwd: Optional[str] = None,
                 timeout: float = 30.0, name: str = "mcp"):
        if not command:
            raise McpError(f"Serveur MCP '{name}' : commande vide.")
        self.command = list(command)
        self.env = env
        self.cwd = cwd
        self.timeout = timeout
        self.name = name
        self.server_info: dict = {}
        self._process: Optional[subprocess.Popen] = None
        self._responses: "queue.Queue[dict]" = queue.Queue()
        self._lock = threading.Lock()
        self._next_id = 1

    # ── Cycle de vie ─────────────────────────────────────────────────

    def start(self) -> "McpClient":
        try:
            self._process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env={**os.environ, **(self.env or {})},
                cwd=self.cwd,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as exc:
            raise McpError(f"Serveur MCP '{self.name}' : impossible de lancer {self.command[0]!r} ({exc}).") from exc
        threading.Thread(target=self._read_loop, name=f"mcp-{self.name}", daemon=True).start()

        result = self.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": CLIENT_INFO,
        })
        self.server_info = result.get("serverInfo", {})
        self.notify("notifications/initialized")
        logger.info(f"[MCP] Connecté à '{self.name}' ({self.server_info.get('name', '?')}).")
        return self

    def close(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        try:
            process.stdin.close()
            process.wait(timeout=3)
        except Exception:
            process.kill()

    @property
    def alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    # ── JSON-RPC ─────────────────────────────────────────────────────

    def _send(self, message: dict) -> None:
        if not self.alive:
            raise McpError(f"Serveur MCP '{self.name}' arrêté.")
        self._process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self._process.stdin.flush()

    def _read_loop(self) -> None:
        """Lit la sortie du serveur. Répond aux ping, ignore les notifications, transmet les réponses."""
        for line in self._process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                logger.debug(f"[MCP] Ligne ignorée de '{self.name}' : {line[:120]}")
                continue
            if "id" in message and ("result" in message or "error" in message):
                self._responses.put(message)
            elif message.get("method") == "ping" and "id" in message:
                self._send({"jsonrpc": "2.0", "id": message["id"], "result": {}})
        # Fin de la sortie : le serveur s'est arrêté. On débloque la requête en attente au lieu d'attendre le délai.
        self._responses.put({"__closed__": True})

    def notify(self, method: str, params: Optional[dict] = None) -> None:
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)

    def request(self, method: str, params: Optional[dict] = None, timeout: Optional[float] = None) -> dict:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
            deadline = timeout or self.timeout
            while True:
                try:
                    message = self._responses.get(timeout=deadline)
                except queue.Empty:
                    raise McpError(f"Serveur MCP '{self.name}' : pas de réponse à '{method}' en {deadline} s.")
                if message.get("__closed__"):
                    self._responses.put(message)  # les requêtes suivantes échouent aussi immédiatement
                    raise McpError(f"Serveur MCP '{self.name}' arrêté (méthode '{method}'). Vérifiez sa commande.")
                if message.get("id") != request_id:
                    continue  # réponse tardive à une requête abandonnée
                if "error" in message:
                    error = message["error"]
                    raise McpError(f"Serveur MCP '{self.name}' : {error.get('message', error)} (méthode '{method}').")
                return message.get("result") or {}

    # ── Outils ───────────────────────────────────────────────────────

    def list_tools(self) -> list[dict]:
        """Liste complète des outils du serveur (suit la pagination nextCursor)."""
        tools, cursor = [], None
        while True:
            result = self.request("tools/list", {"cursor": cursor} if cursor else {})
            tools.extend(result.get("tools", []))
            cursor = result.get("nextCursor")
            if not cursor:
                return tools

    def call_tool(self, name: str, arguments: dict) -> dict:
        return self.request("tools/call", {"name": name, "arguments": arguments or {}})
