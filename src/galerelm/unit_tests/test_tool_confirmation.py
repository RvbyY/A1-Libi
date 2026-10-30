import pytest

from src.galerelm.models.message import Message, ToolCalls
from src.main import SensAI
from src.repl import TerminalREPL
from src.tools import default_tool_registry
from src.tools.ITools import ToolContext, ToolResult, ToolsInterface
from src.tools.registry import ToolExecutor, ToolRegistry


class RecordingTool(ToolsInterface):
    """Outil factice qui mémorise ses appels."""

    def __init__(self, name: str, sensitive: bool):
        self._name = name
        self.requires_confirmation = sensitive
        self.calls: list[dict] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Fake {self._name} tool."

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {"to": {"type": "string"}}, "required": ["to"]}

    def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        self.calls.append(arguments)
        return ToolResult(True, f"{self._name} done")


def assistant_message(name: str, arguments: dict) -> Message:
    return Message(
        role="assistant",
        content="",
        tool_calls=[ToolCalls.from_format({"function": {"name": name, "arguments": arguments}})],
    )


def run(executor: ToolExecutor, name: str, arguments: dict) -> ToolResult:
    results = executor.execute_calls(assistant_message(name, arguments), ToolContext(user_id="u1"))
    assert len(results) == 1
    return results[0][1]


# ── Marquage des outils ──────────────────────────────────────────────

def test_only_side_effect_tools_require_confirmation():
    sensitive = {tool.name for tool in default_tool_registry().all() if tool.requires_confirmation}
    assert sensitive == {"email", "discord", "telegram", "notification", "clear_session"}


# ── ToolExecutor ─────────────────────────────────────────────────────

def test_safe_tool_runs_without_confirmation():
    tool = RecordingTool("lookup", sensitive=False)
    asked = []
    executor = ToolExecutor(ToolRegistry([tool]), confirm=lambda n, a: asked.append(n) or False)

    assert run(executor, "lookup", {"to": "x"}).success is True
    assert tool.calls == [{"to": "x"}]
    assert asked == []


@pytest.mark.parametrize("confirm", [
    None,                                   # personne ne peut confirmer -> refus par défaut
    lambda name, args: False,               # l'utilisateur refuse
    lambda name, args: 1 / 0,               # le callback plante -> refus
])
def test_sensitive_tool_is_refused_without_explicit_approval(confirm):
    tool = RecordingTool("send", sensitive=True)
    result = run(ToolExecutor(ToolRegistry([tool]), confirm=confirm), "send", {"to": "bob"})

    assert result.success is False
    assert "annulée" in result.message
    assert tool.calls == []


def test_sensitive_tool_runs_after_approval_with_its_arguments():
    tool = RecordingTool("send", sensitive=True)
    asked = []

    def approve(name, arguments):
        asked.append((name, arguments))
        return True

    assert run(ToolExecutor(ToolRegistry([tool]), confirm=approve), "send", {"to": "bob"}).success is True
    assert asked == [("send", {"to": "bob"})]
    assert tool.calls == [{"to": "bob"}]


# ── Pipeline complet (SensAI.chat) ───────────────────────────────────

class FakeOllama:
    """Renvoie toujours une réponse contenant un appel à l'outil 'send'."""
    base_url = "http://fake-ollama"

    def stream_ndjson(self, endpoint, data=None, json_data=None, **kwargs):
        yield {
            "message": {
                "role": "assistant",
                "content": "J'envoie le message.",
                "tool_calls": [{"function": {"name": "send", "arguments": {"to": "bob"}}}],
            },
            "done": True,
            "model": "llama3.2",
        }

    def post(self, endpoint, data=None, json=None, **kwargs):
        return {"embeddings": [[0.1, 0.2, 0.3]]}


def make_app(tool: RecordingTool, **kwargs) -> SensAI:
    app = SensAI(db_url="sqlite:///:memory:", tool_registry=ToolRegistry([tool]), **kwargs)
    app.api = app.chat_engine.api = FakeOllama()
    app.load_or_create_profile(email="confirm@test.com", name="ConfirmUser")
    return app


def tool_messages(app: SensAI) -> list[str]:
    return [m.content for m in app.context.messages if m.role == "tool"]


def test_chat_does_not_send_without_confirmation_callback():
    tool = RecordingTool("send", sensitive=True)
    app = make_app(tool)

    app.chat("Envoie un message à Bob")
    assert tool.calls == []
    assert "annulée" in tool_messages(app)[0]


def test_chat_sends_once_confirmed():
    tool = RecordingTool("send", sensitive=True)
    app = make_app(tool)
    app.chat_engine.confirm_tool = lambda name, arguments: True

    app.chat("Envoie un message à Bob")
    assert tool.calls == [{"to": "bob"}]
    assert tool_messages(app) == ["[send] send done"]


def test_anti_hallucination_workflow_also_requires_confirmation():
    tool = RecordingTool("send", sensitive=True)
    app = make_app(tool, use_anti_hallucination=True, max_hallucination_retries=0)

    app.chat("Envoie un message à Bob")
    assert tool.calls == []

    app.chat_engine.confirm_tool = lambda name, arguments: True
    app.chat("Envoie un message à Bob")
    assert tool.calls == [{"to": "bob"}]


# ── Invite de confirmation du terminal ───────────────────────────────

@pytest.mark.parametrize("typed, expected", [
    ("o", True), ("Oui", True), ("y", True),
    ("", False), ("n", False), ("non", False), (EOFError, False),
])
def test_repl_confirmation_prompt(typed, expected, monkeypatch):
    app = make_app(RecordingTool("send", sensitive=True))
    repl = TerminalREPL(app)
    assert app.chat_engine.confirm_tool == repl.confirm_tool

    def fake_input(prompt=""):
        if typed is EOFError:
            raise EOFError
        return typed

    monkeypatch.setattr(repl.console, "input", fake_input)
    assert repl.confirm_tool("send", {"to": "bob"}) is expected
