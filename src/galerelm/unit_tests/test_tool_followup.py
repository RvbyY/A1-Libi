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
