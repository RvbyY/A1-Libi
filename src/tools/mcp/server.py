"""
Module tools/mcp/server.py
Serveur MCP de SensAI (transport stdio) : expose des tools SensAI à n'importe quel client MCP
(un autre agent, Claude Desktop, MCP Inspector, ou SensAI lui-même via mcp_servers).

Lancement :
    PYTHONPATH=. .venv/bin/python -m src.tools.mcp.server

Outils exposés : ceux qui fonctionnent sans base ni profil SensAI (tools_selftest, calendar).
Les outils qui envoient des messages ne sont pas exposés : un client MCP ne passe pas par la confirmation de SensAI.
"""
import json
import sys
from typing import Optional, TextIO

from src.tools.ITools import ToolContext
from src.tools.calendar.calendar_tools import Calendar
from src.tools.diagnostic.selftest_tool import SelfTestTool
from src.tools.registry import ToolRegistry

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "sensai-tools", "version": "0.1"}


class McpServer:
    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or ToolRegistry([SelfTestTool(), Calendar()])
        self.context = ToolContext(user_id="mcp-client")

    def handle(self, message: dict) -> Optional[dict]:
        """Traite un message JSON-RPC. Retourne la réponse, ou None pour une notification."""
        method = message.get("method")
        if "id" not in message:
            return None  # notification (ex : notifications/initialized)
        try:
            result = self._dispatch(method, message.get("params") or {})
        except KeyError as exc:
            return {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": f"Méthode inconnue : {exc.args[0]}"}}
        except ValueError as exc:
            return {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32602, "message": str(exc)}}
        return {"jsonrpc": "2.0", "id": message["id"], "result": result}

    def _dispatch(self, method: str, params: dict) -> dict:
        if method == "initialize":
            return {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO}
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": [
                {"name": tool.name, "description": tool.description, "inputSchema": tool.parameters}
                for tool in self.registry.all()
            ]}
        if method == "tools/call":
            name = params.get("name")
            if self.registry.get(name) is None:
                raise ValueError(f"Outil inconnu : {name}")
            result = self.registry.execute(name, self.context, params.get("arguments") or {})
            content = [{"type": "text", "text": result.message}]
            if result.data is not None:
                content.append({"type": "text", "text": json.dumps(result.data, ensure_ascii=False, default=str)})
            return {"content": content, "isError": not result.success}
        raise KeyError(method)

    def serve(self, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON invalide"}}
            else:
                response = self.handle(message)
            if response is not None:
                stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                stdout.flush()


if __name__ == "__main__":
    McpServer().serve()
