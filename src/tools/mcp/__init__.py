"""Model Context Protocol : client (outils de serveurs MCP externes) et serveur (tools SensAI exposés en MCP)."""
from .client import McpClient, McpError
from .tool import McpManager, McpTool

__all__ = ["McpClient", "McpError", "McpManager", "McpTool"]
