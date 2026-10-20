from src.commands.base import CommandResult
from src.galerelm.engine import ChatEngine
from src.galerelm.wrapper import SensAIWrapper
from src.main import SensAI
from src.repl import TerminalREPL
from src.tools.calendar.calendar_tools import Calendar
from src.tools.registry import ToolRegistry


class FakeRapideAPI:
    """Client API factice pour tester le flux complet sans serveur Ollama."""

    def __init__(self, chunks=None):
        self.base_url = "http://fake-ollama"
        self.chunks = chunks or [
            {"message": {"role": "assistant", "content": "Bonjour "}, "done": False},
            {
                "message": {"role": "assistant", "content": "le monde !"},
                "done": True,
                "model": "llama3.2",
                "created_at": "2026-10-19T00:00:00Z",
                "done_reason": "stop",
                "total_duration": 1000000,
                "load_duration": 100000,
                "prompt_eval_count": 10,
                "prompt_eval_cached_count": 0,
                "prompt_eval_duration": 200000,
                "eval_count": 4,
                "eval_duration": 500000,
            },
        ]

    def stream_ndjson(self, endpoint: str, data=None, json_data=None, **kwargs):
        for chunk in self.chunks:
            yield chunk

    def post(self, endpoint: str, data=None, json=None, **kwargs):
        if endpoint == "api/embed":
            inputs = json.get("input", [])
            if isinstance(inputs, str):
                return {"embeddings": [[0.1, 0.2, 0.3]]}
            return {"embeddings": [[0.1, 0.2, 0.3] for _ in inputs]}
        return {}


def test_chat_engine_stream_and_persistence():
    app = SensAI(db_url="sqlite:///:memory:")
    fake_api = FakeRapideAPI()
    app.api = fake_api
    app.chat_engine.api = fake_api
    app.load_or_create_profile(email="engine@test.com", name="EngineUser")

    reply = app.chat("Salut !")
    assert reply == "Bonjour le monde !"
    assert len(app.context.messages) == 2
    assert app.context.messages[0].role == "user"
    assert app.context.messages[0].content == "Salut !"
    assert app.context.messages[1].role == "assistant"
    assert app.context.messages[1].content == "Bonjour le monde !"


def test_chat_engine_executes_tool_calls():
    tool_chunks = [
        {
            "message": {
                "role": "assistant",
                "content": "J'ajoute l'événement.",
                "tool_calls": [
                    {
                        "function": {
                            "name": "calendar",
                            "description": "Add event",
                            "arguments": {
                                "action": "add",
                                "title": "Réunion",
                                "start": "2026-10-20T10:00:00",
                                "end": "2026-10-20T11:00:00",
                            },
                        }
                    }
                ],
            },
            "done": True,
            "model": "llama3.2",
            "eval_count": 8,
            "eval_duration": 1000000,
        }
    ]
    calendar_tool = Calendar()
    registry = ToolRegistry([calendar_tool])
    app = SensAI(db_url="sqlite:///:memory:", tool_registry=registry)
    fake_api = FakeRapideAPI(chunks=tool_chunks)
    app.api = fake_api
    app.chat_engine.api = fake_api
    app.load_or_create_profile(email="tools@test.com", name="ToolUser")

    app.chat("Planifie une réunion demain de 10h à 11h")
    assert len(calendar_tool.calendar) == 1
    roles = [m.role for m in app.context.messages]
    assert roles == ["user", "assistant", "tool"]


def test_terminal_repl_command_dispatch():
    app = SensAI(db_url="sqlite:///:memory:")
    app.load_or_create_profile(email="repl@test.com", name="ReplUser")
    repl_ui = TerminalREPL(app)

    assert repl_ui.handle_command("/context") is False
    assert repl_ui.handle_command("/memories") is False
    assert repl_ui.handle_command("/quit") is True


def test_wrapper_creates_deep_context_and_streams():
    wrapper = SensAIWrapper(db_url="sqlite:///:memory:")
    fake_api = FakeRapideAPI()
    wrapper.core.api = fake_api
    wrapper.core.chat_engine.api = fake_api

    prof_dto = wrapper.create_profile(email="web@test.com", name="WebUser")
    assert prof_dto.email == "web@test.com"
    assert wrapper.get_memories("web@test.com") == []

    completion = wrapper.chat_blocking("web@test.com", "Test wrapper")
    assert completion.message.content == "Bonjour le monde !"
    history = wrapper.get_chat_history("web@test.com")
    assert len(history) == 2


def test_chat_engine_guardrail_blocking():
    class StubGuardrail:
        def classify(self, user_input: str) -> str:
            return "AMBIGUOUS"

    app = SensAI(db_url="sqlite:///:memory:", guardrail=StubGuardrail())
    app.chat_engine.blocked_responses = {"AMBIGUOUS": "Requête ambiguë."}
    app.load_or_create_profile(email="guard@test.com", name="GuardUser")

    reply = app.chat("Requête floue")
    assert reply == "Requête ambiguë."
    assert len(app.context.messages) == 2
    assert app.context.messages[1].content == "Requête ambiguë."
    assert app.chat_engine.last_response.done_reason == "guardrail"

