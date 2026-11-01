import json
from pathlib import Path

import pytest

from src.galerelm.models import Chat, LongTermMemory, Message, MessageList, ToolCalls, ToolCallsFunction, ToolsList
from src.main import SensAI
from src.rapideAPI import RapideAPI
from src.tools import (
    BUILTIN_TOOLS,
    ClearSessionTool,
    CompleteTaskTool,
    CreateTaskTool,
    Discord,
    NotificationTool,
    SearchMemoryTool,
    SelfTestTool,
    SendTaskFileTool,
    SummarizeSessionTool,
    Telegram,
    ToolExecutor,
    ToolRegistry,
    default_tool_registry,
)
from src.tools.ITools import ToolContext


def test_default_tool_registry_and_to_tools_list():
    registry = default_tool_registry()
    assert len(registry) == len(BUILTIN_TOOLS)

    tools_list = registry.to_tools_list()
    assert isinstance(tools_list, ToolsList)
    assert len(tools_list) == len(BUILTIN_TOOLS)

    chat = Chat(
        model="llama3.2",
        api=RapideAPI(base_url="http://fake"),
        messages=MessageList([Message(role="user", content="Hi")]),
        tools=registry,
    )
    payload = chat.format()
    assert "tools" in payload
    assert len(payload["tools"]) == len(BUILTIN_TOOLS)


def test_notification_tool():
    tool = NotificationTool()
    ctx = ToolExecutor(ToolRegistry([tool])).build_tool_context(profile=None)

    res_sms = tool.execute(
        ctx,
        {
            "channel": "sms",
            "recipient_to": "+33612345678",
            "recipient_from": "+33687654321",
            "message": "Hello SMS",
        },
    )
    assert res_sms.success is True

    res_slack = tool.execute(
        ctx,
        {
            "channel": "slack",
            "recipient_to": "U12345",
            "recipient_from": "#general",
            "message": "Hello Slack",
        },
    )
    assert res_slack.success is True

    res_bad = tool.execute(
        ctx,
        {
            "channel": "sms",
            "recipient_to": "invalid_phone",
            "recipient_from": "+33687654321",
            "message": "Fail",
        },
    )
    assert res_bad.success is False


def test_discord_and_telegram_tools_with_fake_api():
    class FakeDiscordAPI:
        def post(self, endpoint, json=None, **kwargs):
            if endpoint == "users/@me/channels":
                return {"id": "chan_999"}
            if endpoint == "channels/chan_999/messages":
                return {"id": "msg_1", "content": json.get("content")}
            return {}

    discord_tool = Discord(token="fake-discord-token", api_client=FakeDiscordAPI())
    ctx = ToolExecutor(ToolRegistry([discord_tool])).build_tool_context(profile=None)

    res = discord_tool.execute(
        ctx,
        {"recipient": "123456789012345678", "content": "Hello Discord"},
    )
    assert res.success is True

    class FakeTelegramAPI:
        def get(self, url, **kwargs):
            return '<html><head><meta property="og:title" content="User"/></head></html>'

        def post(self, endpoint, json=None, **kwargs):
            return {"ok": True, "result": {"text": json.get("text")}}

    tg_tool = Telegram(token="fake-tg-token", api_client=FakeTelegramAPI())
    res_tg = tg_tool.execute(ctx, {"recipient": "someuser", "content": "Hello Telegram"})
    assert res_tg.success is True


def test_memory_tools():
    app = SensAI(db_url="sqlite:///:memory:")
    app.load_or_create_profile(email="memtools@test.com", name="MemUser")

    app.context.messages.append(Message(role="user", content="Premier message"))
    app.context.messages.append(Message(role="assistant", content="Réponse assistant"))
    app.profile.deep_context.memories.append(
        LongTermMemory(role="user", content="Souvenir important", embedding=[1.0, 0.0])
    )
    app.session.commit()

    class FakeEmbedAPI:
        def post(self, endpoint, json=None, **kwargs):
            return {"embeddings": [[1.0, 0.0]]}

    executor = ToolExecutor(app.tools)
    t_ctx = executor.build_tool_context(
        profile=app.profile,
        session=app.session,
        context=app.context,
        api=FakeEmbedAPI(),
    )

    summary_res = SummarizeSessionTool().execute(t_ctx, {})
    assert summary_res.success is True
    assert "Premier message" in summary_res.data

    search_res = SearchMemoryTool().execute(t_ctx, {"query": "Souvenir", "top_k": 2})
    assert search_res.success is True
    assert len(search_res.data) == 1
    assert search_res.data[0]["content"] == "Souvenir important"

    clear_res = ClearSessionTool().execute(t_ctx, {})
    assert clear_res.success is True
    assert len(app.context.messages) == 0


def test_task_tools_and_tool_executor(tmp_path: Path):
    app = SensAI(db_url="sqlite:///:memory:")
    app.load_or_create_profile(email="tasktools@test.com", name="TaskUser")

    executor = ToolExecutor(app.tools)
    t_ctx = executor.build_tool_context(
        profile=app.profile,
        session=app.session,
        context=app.context,
        api=app.api,
        task_manager=app.task_manager,
    )

    create_res = CreateTaskTool().execute(
        t_ctx,
        {
            "prompt": "Rappel réunion",
            "scheduled_at": "2026-10-25T09:00:00",
            "recurrence": "daily",
        },
    )
    assert create_res.success is True
    task_id = create_res.data["id"]

    export_file = tmp_path / "tasks.json"
    export_res = SendTaskFileTool().execute(t_ctx, {"file_path": str(export_file)})
    assert export_res.success is True
    assert export_file.exists()
    assert export_res.data["count"] == 1

    complete_res = CompleteTaskTool().execute(t_ctx, {"task_id": task_id, "action": "complete"})
    assert complete_res.success is True
    assert complete_res.data["status"] == "completed"


# ── tools_selftest ───────────────────────────────────────────────────

def selftest(arguments, user_id="u1"):
    return SelfTestTool().execute(ToolContext(user_id=user_id), arguments)


def test_selftest_is_registered_and_safe():
    tool = default_tool_registry().get("tools_selftest")
    assert isinstance(tool, SelfTestTool)
    assert tool.requires_confirmation is False
    assert tool.parameters["required"] == ["message"]


def test_selftest_echo_nominal():
    res = selftest({"message": "  ping ", "repeat": 3})
    assert res.success is True
    assert res.message == "Selftest OK: ping ping ping"
    assert res.data["echo"] == "ping ping ping"
    assert res.data["repeat"] == 3
    assert res.data["user_id"] == "u1"
    json.dumps(res.data)  # sérialisable en JSON


def test_selftest_defaults_to_single_echo():
    res = selftest({"message": "ping"})
    assert res.success is True and res.data["echo"] == "ping"


def test_selftest_fail_mode_simulates_an_error():
    res = selftest({"message": "ping", "mode": "fail"})
    assert res.success is False
    assert "Simulated failure" in res.message


@pytest.mark.parametrize("arguments, error", [
    ({}, "message is required"),
    ({"message": ""}, "message is required"),
    ({"message": "   "}, "message is required"),
    ({"message": 42}, "message is required"),
    ({"message": "x" * 201}, "at most 200"),
    ({"message": "ping", "mode": "explode"}, "mode must be one of"),
    ({"message": "ping", "repeat": 0}, "repeat must be"),
    ({"message": "ping", "repeat": 6}, "repeat must be"),
    ({"message": "ping", "repeat": "2"}, "repeat must be"),
    ({"message": "ping", "repeat": True}, "repeat must be"),
    ("ping", "arguments must be an object"),
])
def test_selftest_rejects_invalid_arguments(arguments, error):
    res = selftest(arguments)
    assert res.success is False
    assert error in res.message


def test_selftest_only_exposes_the_caller():
    assert selftest({"message": "a"}, user_id="alice").data["user_id"] == "alice"
    assert selftest({"message": "b"}, user_id="bob").data["user_id"] == "bob"


class SelfTestOllama:
    """Faux Ollama : demande un appel à tools_selftest (aucun appel réseau)."""
    base_url = "http://fake-ollama"

    def stream_ndjson(self, endpoint, data=None, json_data=None, **kwargs):
        if (json_data or {}).get("messages", [{}])[-1].get("role") == "tool":
            # Relance après exécution d'outils : le modèle répond en texte
            yield {"message": {"role": "assistant", "content": "C'est fait."}, "done": True, "model": "llama3.2"}
            return
        yield {
            "message": {
                "role": "assistant",
                "content": "Je teste les outils.",
                "tool_calls": [{"function": {"name": "tools_selftest", "arguments": {"message": "ping"}}}],
            },
            "done": True,
            "model": "llama3.2",
        }

    def post(self, endpoint, data=None, json=None, **kwargs):
        return {"embeddings": [[0.1, 0.2, 0.3]]}


@pytest.mark.parametrize("anti_hallucination", [False, True])
def test_selftest_through_full_pipeline(anti_hallucination):
    app = SensAI(
        db_url="sqlite:///:memory:",
        use_anti_hallucination=anti_hallucination,
        max_hallucination_retries=0,
    )
    app.api = app.chat_engine.api = SelfTestOllama()
    app.load_or_create_profile(email="selftest@test.com", name="SelfTestUser")

    app.chat("Teste les outils avec ping")
    tool_messages = [m.content for m in app.context.messages if m.role == "tool"]
    assert tool_messages == ["[tools_selftest] Selftest OK: ping"]
