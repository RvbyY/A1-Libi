from pathlib import Path
from types import SimpleNamespace
from src.galerelm.models import Chat, LongTermMemory, Message, MessageList, ToolCalls, ToolCallsFunction, ToolsList
from src.main import SensAI
from src.rapideAPI import RapideAPI
from src.tools import (
    BUILTIN_TOOLS,
    ClearSessionTool,
    CompleteTaskTool,
    CreateTaskTool,
    Discord,
    Telegram,
    Email,
    NotificationTool,
    SearchMemoryTool,
    SendTaskFileTool,
    SummarizeSessionTool,
    ToolExecutor,
    ToolRegistry,
    default_tool_registry,
)


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
        def __init__(self):
           self.sent = []

        def post(self, endpoint, json=None, **kwargs):
            if endpoint == "users/@me/channels":
                return {"id": "chan_999"}
            if endpoint == "channels/chan_999/messages":
                self.sent.append(json.get("content"))
                return {"id": "msg_1", "content": json.get("content")}
            return {}

    discord_api = FakeDiscordAPI()  
    discord_tool = Discord(token="fake-discord-token", api_client=discord_api)
    ctx = ToolExecutor(ToolRegistry([discord_tool])).build_tool_context(profile=None)

    res = discord_tool.execute(
        ctx,
        {"recipient": "123456789012345678", "content": "Hello Discord"},
    )
    assert res.success is True
    assert discord_api.sent == ["Hello Discord"]

    class FakeTelegramAPI:
        def __init__(self):
            self.sent = [] 

        def get(self, url, **kwargs):
            return '<html><head><meta property="og:title" content="User"/></head></html>'

        def post(self, endpoint, json=None, **kwargs):
            self.sent.append((json.get("chat_id"), json.get("text")))
            return {"ok": True, "result": {"text": json.get("text")}}

    tg_api = FakeTelegramAPI()
    tg_tool = Telegram(token="fake-tg-token", api_client=tg_api)
    res_tg = tg_tool.execute(ctx, {"recipient": "someuser", "content": "Hello Telegram"})
    assert res_tg.success is True
    assert tg_api.sent == [("someuser", "Hello Telegram")]


def test_discord_rejects_bad_input():
    ctx = ToolExecutor(ToolRegistry([])).build_tool_context(profile=None)
    ok_id = "123456789012345678"

    # pas de token
    assert Discord(token="").execute(ctx, {"recipient": ok_id, "content": "x"}).success is False
    # ID invalide
    assert Discord(token="t").execute(ctx, {"recipient": "abc", "content": "x"}).success is False  
    # message vide
    assert Discord(token="t").execute(ctx, {"recipient": ok_id, "content": ""}).success is False   


def test_email_tool_with_fake_smtp(monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, host, port):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ehlo(self):
            pass

        def starttls(self):
            pass

        def sendmail(self, sender, recipients, raw_message):
            sent.append((sender, recipients))

    monkeypatch.setattr("src.tools.communication.email.smtplib.SMTP", FakeSMTP)

    profile = SimpleNamespace(id=1, email="test@test.com")
    ctx = ToolExecutor(ToolRegistry([])).build_tool_context(profile=profile)
    tool = Email(smtp_host="fake", smtp_port=25)

    res = tool.execute(ctx, {"recipient": "res@test.com", "subject": "Salut", "content": "Hello Email"})
    assert res.success is True
    assert sent == [("test@test.com", ["res@test.com"])]

    bad = tool.execute(ctx, {"recipient": "not-a-mail", "subject": "x", "content": "x"})
    assert bad.success is False


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

    export_res = SendTaskFileTool().execute(t_ctx, {"task_id": str(task_id)})
    assert export_res.success is True
    assert export_res.data["task"]["prompt"] == "Rappel réunion"


    complete_res = CompleteTaskTool().execute(t_ctx, {"task_id": task_id, "action": "complete"})
    assert complete_res.success is True
    assert complete_res.data["status"] == "completed"
