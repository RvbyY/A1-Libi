import copy
import os
import sys
import textwrap

import pytest

from src.config import PROJECT_ROOT, Config, ConfigError, config
from src.main import SensAI
from src.tools.mcp import McpClient, McpError, McpManager, McpTool
from src.tools.mcp.server import McpServer
from src.tools.registry import ToolRegistry
from src.tools import default_tool_registry
from src.tools.ITools import ToolContext

OWN_SERVER = [sys.executable, "-m", "src.tools.mcp.server"]
ENV = {"PYTHONPATH": str(PROJECT_ROOT)}


@pytest.fixture(autouse=True)
def restore_config():
    saved = copy.deepcopy(config.MCP_SERVERS)
    yield
    config.MCP_SERVERS = saved


# ── Notre serveur MCP, sans sous-processus ───────────────────────────

def test_server_answers_the_protocol():
    server = McpServer()
    init = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "sensai-tools"
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    tools = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert {t["name"] for t in tools} == {"tools_selftest", "calendar"}
    assert all("inputSchema" in t for t in tools)


def test_server_tool_call_and_errors():
    server = McpServer()
    ok = server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                        "params": {"name": "tools_selftest", "arguments": {"message": "ping"}}})
    assert ok["result"]["isError"] is False and ok["result"]["content"][0]["text"] == "Selftest OK: ping"
    failed = server.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                            "params": {"name": "tools_selftest", "arguments": {}}})
    assert failed["result"]["isError"] is True
    assert server.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "nope"}})["error"]["code"] == -32602
    assert server.handle({"jsonrpc": "2.0", "id": 6, "method": "resources/list"})["error"]["code"] == -32601


# ── Client <-> serveur, par de vrais sous-processus ──────────────────

def test_client_talks_to_our_server_over_stdio():
    client = McpClient(OWN_SERVER, env=ENV, name="sensai").start()
    try:
        assert client.server_info["name"] == "sensai-tools"
        assert [t["name"] for t in client.list_tools()] == ["tools_selftest", "calendar"]
        result = client.call_tool("tools_selftest", {"message": "ping", "repeat": 2})
        assert result["content"][0]["text"] == "Selftest OK: ping ping"
    finally:
        client.close()
    assert not client.alive


FOREIGN_SERVER = textwrap.dedent('''
    import json, sys
    def send(m): sys.stdout.write(json.dumps(m) + "\\n"); sys.stdout.flush()
    for line in sys.stdin:
        m = json.loads(line)
        if "id" not in m or "method" not in m:
            continue  # notification, ou réponse du client (ex : à notre ping)
        if m["method"] == "initialize":
            send({"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info", "data": "hello"}})
            send({"jsonrpc": "2.0", "id": 99, "method": "ping"})
            send({"jsonrpc": "2.0", "id": m["id"], "result": {"protocolVersion": "2025-06-18", "serverInfo": {"name": "etranger"}}})
        elif m["method"] == "tools/list":
            page = (m.get("params") or {}).get("cursor")
            tool = {"name": "heure" if page else "meteo", "description": "outil " + ("2" if page else "1"),
                    "inputSchema": {"type": "object", "properties": {"ville": {"type": "string"}}}}
            send({"jsonrpc": "2.0", "id": m["id"], "result": {"tools": [tool], **({} if page else {"nextCursor": "p2"})}})
        elif m["method"] == "tools/call":
            ville = m["params"]["arguments"].get("ville")
            if not ville:
                send({"jsonrpc": "2.0", "id": m["id"], "result": {"content": [{"type": "text", "text": "ville manquante"}], "isError": True}})
            else:
                send({"jsonrpc": "2.0", "id": m["id"], "result": {"content": [{"type": "text", "text": "Soleil à " + ville}]}})
''')


@pytest.fixture
def foreign_server(tmp_path):
    script = tmp_path / "foreign_server.py"
    script.write_text(FOREIGN_SERVER, encoding="utf-8")
    return [sys.executable, str(script)]


def test_client_handles_notifications_ping_and_pagination(foreign_server):
    client = McpClient(foreign_server, name="etranger").start()
    try:
        assert client.server_info == {"name": "etranger"}
        assert [t["name"] for t in client.list_tools()] == ["meteo", "heure"]
    finally:
        client.close()


def test_mcp_tool_adapter(foreign_server):
    client = McpClient(foreign_server, name="etranger").start()
    try:
        spec = client.list_tools()[0]
        tool = McpTool(client, spec)
        assert tool.name == "meteo" and tool.parameters["properties"] == {"ville": {"type": "string"}}
        assert tool.requires_confirmation is True
        ok = tool.execute(ToolContext(user_id="u"), {"ville": "Lyon"})
        assert ok.success and ok.message == "Soleil à Lyon"
        assert not tool.execute(ToolContext(user_id="u"), {}).success
    finally:
        client.close()


def test_dead_server_fails_fast():
    with pytest.raises(McpError, match="arrêté"):
        McpClient([sys.executable, "-c", "pass"], name="mort").start()


def test_missing_command_is_reported():
    with pytest.raises(McpError, match="impossible de lancer"):
        McpClient(["commande-introuvable-sensai"], name="absent").start()


# ── Configuration et intégration dans SensAI ─────────────────────────

def test_manager_prefixes_names_already_taken_and_keeps_going(foreign_server):
    registry = default_tool_registry()
    manager = McpManager({
        "sensai": {"command": OWN_SERVER, "env": ENV, "confirm": False},
        "etranger": {"command": foreign_server},
        "absent": {"command": ["commande-introuvable-sensai"]},
        "coupe": {"command": foreign_server, "enabled": False},
    })
    try:
        added = manager.register_all(registry)
        assert added == ["sensai__tools_selftest", "sensai__calendar", "meteo", "heure"]
        assert registry.get("sensai__tools_selftest").requires_confirmation is False
        assert registry.get("meteo").requires_confirmation is True
        assert "absent" in manager.errors and "coupe" not in manager.clients
    finally:
        manager.close()


def test_yaml_mcp_servers(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("mcp_servers:\n  fs:\n    command: npx -y @modelcontextprotocol/server-filesystem /tmp\n"
                    "    confirm: true\n    env:\n      DEBUG: 1\n", encoding="utf-8")
    cfg = Config().load_yaml(path)
    assert cfg.MCP_SERVERS["fs"]["command"] == ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    assert cfg.MCP_SERVERS["fs"]["env"] == {"DEBUG": "1"} and cfg.MCP_SERVERS["fs"]["timeout"] == 30.0


@pytest.mark.parametrize("content, message", [
    ("mcp_servers:\n  x: npx\n", "doit être un dictionnaire"),
    ("mcp_servers:\n  x:\n    args: [a]\n", "champ inconnu"),
    ("mcp_servers:\n  x:\n    confirm: true\n", "'command' est obligatoire"),
])
def test_yaml_mcp_errors(tmp_path, content, message):
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        Config().load_yaml(path)


class ToolCallingOllama:
    """Faux modèle : appelle l'outil MCP 'meteo', puis reprend son résultat."""
    base_url = "http://fake"

    def stream_ndjson(self, endpoint, json_data=None, **kwargs):
        last = json_data["messages"][-1]
        if last["role"] == "tool":
            yield {"message": {"role": "assistant", "content": f"D'après l'outil : {last['content']}"}, "done": True, "model": "m"}
            return
        yield {"message": {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "meteo", "arguments": {"ville": "Lyon"}}}]}, "done": True, "model": "m"}

    def post(self, endpoint, json=None, **kwargs):
        inputs = json["input"]
        return {"embeddings": [[1.0, 0.0]] * (1 if isinstance(inputs, str) else len(inputs))}


def test_model_calls_an_mcp_tool_through_sensai(foreign_server):
    config.MCP_SERVERS = {"etranger": {"command": foreign_server, "confirm": True}}
    app = SensAI(db_url="sqlite:///:memory:")
    try:
        assert app.mcp_tools == ["meteo", "heure"]
        app.api = app.chat_engine.api = ToolCallingOllama()
        app.chat_engine.confirm_tool = lambda name, arguments: True
        app.load_or_create_profile(email="mcp@test.com", name="Mcp")
        reply = app.chat("Quel temps fait-il à Lyon ?")
        assert reply == "D'après l'outil : [meteo] Soleil à Lyon"
        assert "meteo" in [t["function"]["name"] for t in app.chat_engine._get_tools_list().format()]
    finally:
        app.close()
