from src.galerelm.graph import HallucinationGrade
from src.main import SensAI
from src.tools import SelfTestTool
from src.tools.registry import ToolRegistry


def tool_call_chunk(content="Je lance le test."):
    return {
        "message": {
            "role": "assistant",
            "content": content,
            "tool_calls": [{"function": {"name": "tools_selftest", "arguments": {"message": "ping"}}}],
        },
        "done": True,
        "model": "llama3.2",
    }


def text_chunk(content):
    return {"message": {"role": "assistant", "content": content}, "done": True, "model": "llama3.2"}


class ScriptedOllama:
    """Faux Ollama : renvoie les réponses prévues dans l'ordre et mémorise chaque requête de chat."""
    base_url = "http://fake-ollama"

    def __init__(self, *responses, repeat_last=False):
        self.responses = list(responses)
        self.repeat_last = repeat_last
        self.requests: list[list[dict]] = []

    def stream_ndjson(self, endpoint, data=None, json_data=None, **kwargs):
        self.requests.append(json_data["messages"])
        if len(self.responses) > 1 or not self.repeat_last:
            yield self.responses.pop(0)
        else:
            yield self.responses[0]

    def post(self, endpoint, data=None, json=None, **kwargs):
        return {"embeddings": [[0.1, 0.2, 0.3]]}


class CountingSelfTest(SelfTestTool):
    def __init__(self):
        self.calls = 0

    def execute(self, context, arguments):
        self.calls += 1
        return super().execute(context, arguments)


def make_app(fake, **kwargs):
    tool = CountingSelfTest()
    app = SensAI(db_url="sqlite:///:memory:", tool_registry=ToolRegistry([tool]), **kwargs)
    app.api = app.chat_engine.api = fake
    app.load_or_create_profile(email="followup@test.com", name="FollowUp")
    return app, tool


def roles(app):
    return [m.role for m in app.context.messages]


# ── Mode normal (streaming) ──────────────────────────────────────────

def test_model_is_reprompted_with_tool_results():
    fake = ScriptedOllama(tool_call_chunk(), text_chunk("Le test a réussi : ping."))
    app, tool = make_app(fake)

    reply = app.chat("Teste les outils avec ping")

    assert reply == "Je lance le test.\n\nLe test a réussi : ping."
    assert tool.calls == 1
    assert roles(app) == ["user", "assistant", "tool", "assistant"]
    # La relance contient le résultat de l'outil, avec le même prompt système
    followup = fake.requests[1]
    assert followup[-1] == {"role": "tool", "content": "[tools_selftest] Selftest OK: ping"}
    assert followup[0]["role"] == "system" and followup[0]["content"] == fake.requests[0][0]["content"]


def test_no_separator_when_tool_call_has_no_text():
    fake = ScriptedOllama(tool_call_chunk(content=""), text_chunk("Le test a réussi."))
    app, _ = make_app(fake)
    assert app.chat("Teste les outils") == "Le test a réussi."


def test_no_followup_without_tool_call():
    fake = ScriptedOllama(text_chunk("Paris."))
    app, tool = make_app(fake)
    assert app.chat("Capitale de la France ?") == "Paris."
    assert len(fake.requests) == 1 and tool.calls == 0


def test_json_arguments_emitted_as_text_are_executed():
    fake = ScriptedOllama(
        text_chunk('```json\n{"message": "ping"}\n```'),
        text_chunk("Le test a réussi."),
    )
    app, tool = make_app(fake)

    assert app.chat("Teste les outils") == "Le test a réussi."
    assert tool.calls == 1
    assert roles(app) == ["user", "assistant", "tool", "assistant"]
    assert app.context.messages[1].content == ""


def test_discord_json_arguments_can_recover_explicit_recipient():
    from src.tools import Discord

    class FakeDiscordAPI:
        def post(self, endpoint, json=None, **kwargs):
            if endpoint == "users/@me/channels":
                return {"id": "channel"}
            return {"content": json["content"]}

    discord = Discord(token="fake-token", api_client=FakeDiscordAPI())
    fake = ScriptedOllama(
        text_chunk('{"content": "chupa chups il veut pas du deli"}'),
        text_chunk("Le message a été envoyé."),
    )
    app = SensAI(db_url="sqlite:///:memory:", tool_registry=ToolRegistry([discord]))
    app.api = app.chat_engine.api = fake
    app.load_or_create_profile(email="discord@test.com", name="Discord")
    app.chat_engine.confirm_tool = lambda name, arguments: True

    assert app.chat(
        "Use the discord tool to send exactly "
        '"chupa chups il veut pas du deli" to user ID 374505575683457044.'
    ) == "Le message a été envoyé."
    assert roles(app) == ["user", "assistant", "tool", "assistant"]
    assert app.context.messages[1].content == ""


def test_discord_request_executes_when_model_returns_planning_prose():
    from src.tools import Discord

    class FakeDiscordAPI:
        def __init__(self):
            self.messages = []

        def post(self, endpoint, json=None, **kwargs):
            if endpoint == "users/@me/channels":
                return {"id": "channel"}
            self.messages.append(json)
            return {"id": "message"}

    discord_api = FakeDiscordAPI()
    discord = Discord(token="fake-token", api_client=discord_api)
    fake = ScriptedOllama(
        text_chunk("I should analyze the request before using the tool."),
        text_chunk("The message was sent."),
    )
    app = SensAI(db_url="sqlite:///:memory:", tool_registry=ToolRegistry([discord]))
    app.api = app.chat_engine.api = fake
    app.load_or_create_profile(email="discord-prose@test.com", name="Discord")
    app.chat_engine.confirm_tool = lambda name, arguments: True

    app.chat(
        'Use the discord tool to send exactly "hello from A1-Libi" '
        "to user ID 374505575683457044."
    )

    assert discord_api.messages == [{"content": "hello from A1-Libi"}]
    assert roles(app) == ["user", "assistant", "tool", "assistant"]


def test_wrapped_textual_tool_call_is_executed_after_tool_result():
    from src.tools import Discord

    class FakeDiscordAPI:
        def post(self, endpoint, json=None, **kwargs):
            if endpoint == "users/@me/channels":
                return {"id": "channel"}
            return {"id": "message"}

    discord = Discord(token="fake-token", api_client=FakeDiscordAPI())
    fake = ScriptedOllama(
        text_chunk(
            '```json\n{"tool_call": {"name": "discord", "arguments": '
            '{"recipient": "374505575683457044", "content": "hello"}}}\n```\n'
            "The message was sent."
        ),
        text_chunk("The message was sent."),
    )
    app = SensAI(db_url="sqlite:///:memory:", tool_registry=ToolRegistry([discord]))
    app.api = app.chat_engine.api = fake
    app.load_or_create_profile(email="discord-wrapper@test.com", name="Discord")
    app.chat_engine.confirm_tool = lambda name, arguments: True

    assert app.chat("Send a Discord message.") == "The message was sent."


def test_discord_reference_uses_latest_assistant_response():
    from src.tools import Discord

    class FakeDiscordAPI:
        def __init__(self):
            self.messages = []

        def post(self, endpoint, json=None, **kwargs):
            if endpoint == "users/@me/channels":
                return {"id": "channel"}
            self.messages.append(json["content"])
            return {"id": "message"}

    discord_api = FakeDiscordAPI()
    discord = Discord(token="fake-token", api_client=discord_api)
    fake = ScriptedOllama(
        text_chunk("I need to use the Discord tool."),
        text_chunk("The referenced response was sent."),
        text_chunk("The referenced response was sent."),
    )
    app = SensAI(db_url="sqlite:///:memory:", tool_registry=ToolRegistry([discord]))
    app.api = app.chat_engine.api = fake
    app.load_or_create_profile(email="discord-reference@test.com", name="Discord")
    app.chat_engine.confirm_tool = lambda name, arguments: True

    app.chat("Remember this neutral response.")
    app.chat(
        "Use the discord tool to send your last response message "
        "to user ID 374505575683457044."
    )

    assert discord_api.messages == ["I need to use the Discord tool."]


def test_discord_textual_json_array_sends_to_all_recipients():
    from src.tools import Discord

    class FakeDiscordAPI:
        def __init__(self):
            self.messages = []

        def post(self, endpoint, json=None, **kwargs):
            if endpoint == "users/@me/channels":
                return {"id": f"channel-{len(self.messages)}"}
            self.messages.append(json["content"])
            return {"id": "message"}

    discord_api = FakeDiscordAPI()
    discord = Discord(token="fake-token", api_client=discord_api)
    fake = ScriptedOllama(
        text_chunk(
            '[{"action":"discord","parameters":{"recipient":"1288067527112396892",'
            '"content":"hello"}},{"action":"discord","parameters":'
            '{"recipient":"521302266959888394","content":"hello"}}]'
        ),
        text_chunk("The messages were sent."),
    )
    app = SensAI(db_url="sqlite:///:memory:", tool_registry=ToolRegistry([discord]))
    app.api = app.chat_engine.api = fake
    app.load_or_create_profile(email="discord-batch@test.com", name="Discord")
    app.chat_engine.confirm_tool = lambda name, arguments: True

    assert app.chat("Send hello to two Discord users.") == "The messages were sent."
    assert discord_api.messages == ["hello", "hello"]


def test_tool_rounds_are_bounded():
    fake = ScriptedOllama(tool_call_chunk(), repeat_last=True)  # le modèle rappelle l'outil sans fin
    app, tool = make_app(fake)
    app.chat_engine.max_tool_rounds = 2

    app.chat("Boucle")
    assert tool.calls == 3          # 1 appel initial + 2 relances
    assert len(fake.requests) == 3


def test_zero_rounds_disables_followup():
    fake = ScriptedOllama(tool_call_chunk(), text_chunk("jamais lu"))
    app, tool = make_app(fake)
    app.chat_engine.max_tool_rounds = 0

    app.chat("Teste")
    assert tool.calls == 1 and len(fake.requests) == 1


# ── Mode anti-hallucination (graphe) ─────────────────────────────────

class FixedGrader:
    def __init__(self, grounded):
        self.grounded = grounded
        self.calls = 0

    def grade(self, user_input, candidate, facts=None):
        self.calls += 1
        self.facts = facts
        return HallucinationGrade(grounded=self.grounded, critique="" if self.grounded else "invente")


def test_workflow_reprompts_after_tools_and_grades_final_answer():
    fake = ScriptedOllama(tool_call_chunk(), text_chunk("Le test a réussi : ping."))
    app, tool = make_app(fake, hallucination_grader=FixedGrader(grounded=True))

    reply = app.chat("Teste les outils avec ping")

    assert reply == "Le test a réussi : ping."
    assert tool.calls == 1
    assert roles(app) == ["user", "assistant", "tool", "assistant"]
    assert "[tools_selftest] Selftest OK: ping" in app.chat_engine.hallucination_grader.facts
    assert app.chat_engine.last_graph_state["execution_trace"] == ["retrieve", "generate", "tools", "generate", "grade"]


def test_workflow_regeneration_never_reruns_tools():
    fake = ScriptedOllama(tool_call_chunk(), text_chunk("v1"), tool_call_chunk("v2"), text_chunk("v3"))
    grader = FixedGrader(grounded=False)
    app, tool = make_app(fake, hallucination_grader=grader, max_hallucination_retries=1)

    app.chat("Teste")

    assert tool.calls == 1
    # La relance après outils ne consomme pas d'essai : une seule régénération a lieu
    assert app.chat_engine.last_graph_state["execution_trace"] == [
        "retrieve", "generate", "tools", "generate", "grade", "generate", "grade",
    ]
