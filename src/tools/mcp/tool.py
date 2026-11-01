"""
Module tools/mcp/tool.py
McpTool : présente un outil d'un serveur MCP comme un tool SensAI (ToolsInterface),
et McpManager : lance les serveurs déclarés dans config.yaml (section mcp_servers) et enregistre leurs outils.
"""
import logging
from typing import Optional

from ..ITools import ToolContext, ToolResult, ToolsInterface
from ..registry import ToolRegistry
from .client import McpClient, McpError

logger = logging.getLogger("sensai.tools.mcp")


class McpTool(ToolsInterface):
    """Un outil distant : le schéma vient du serveur MCP, l'exécution passe par tools/call."""

    def __init__(self, client: McpClient, spec: dict, exposed_name: Optional[str] = None,
                 requires_confirmation: bool = True):
        self.client = client
        self.remote_name = spec["name"]
        self._name = exposed_name or spec["name"]
        self._description = spec.get("description") or f"Outil MCP {spec['name']} du serveur {client.name}."
        self._parameters = spec.get("inputSchema") or {"type": "object", "properties": {}}
        # Un serveur MCP externe peut agir sur des fichiers, des comptes... : confirmation par défaut.
        self.requires_confirmation = requires_confirmation

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict:
        return self._parameters

    def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        if not isinstance(arguments, dict):
            return ToolResult(False, "arguments must be an object.")
        try:
            result = self.client.call_tool(self.remote_name, arguments)
        except McpError as exc:
            return ToolResult(False, str(exc))
        texts = [item.get("text", "") for item in result.get("content", []) if item.get("type") == "text"]
        message = "\n".join(text for text in texts if text) or "(résultat sans texte)"
        return ToolResult(not result.get("isError", False), message, result)


class McpManager:
    """Connecte chaque serveur MCP configuré et ajoute ses outils au registre de SensAI."""

    def __init__(self, servers: dict[str, dict]):
        self.servers = servers
        self.clients: dict[str, McpClient] = {}
        self.errors: dict[str, str] = {}

    def register_all(self, registry: ToolRegistry) -> list[str]:
        """Retourne les noms des outils ajoutés. Un serveur en panne est signalé sans bloquer les autres."""
        added = []
        for server, spec in self.servers.items():
            if not spec.get("enabled", True):
                continue
            client = McpClient(spec["command"], env=spec.get("env"), cwd=spec.get("cwd"),
                               timeout=float(spec.get("timeout", 30)), name=server)
            try:
                client.start()
                tools = client.list_tools()
            except McpError as exc:
                client.close()
                self.errors[server] = str(exc)
                logger.warning(f"[MCP] {exc}")
                continue
            self.clients[server] = client
            for tool_spec in tools:
                # Un nom déjà pris (outil intégré ou autre serveur) est préfixé par le nom du serveur
                exposed = tool_spec["name"] if registry.get(tool_spec["name"]) is None else f"{server}__{tool_spec['name']}"
                registry.register(McpTool(client, tool_spec, exposed, bool(spec.get("confirm", True))))
                added.append(exposed)
        return added

    def close(self) -> None:
        for client in self.clients.values():
            client.close()
        self.clients.clear()
