from src.galerelm.prompt_simplifier import simplify
from src.galerelm.unit_tests.test_engine_and_repl import FakeRapideAPI
from src.main import SensAI


def test_simplify_removes_french_fillers_and_politeness():
    assert simplify("Salut, en fait du coup genre comment marche Python stp ?") == "comment marche Python ?"


def test_simplify_removes_english_fillers_and_politeness():
    assert simplify("Hi, um basically how does Python work please?") == "how does Python work?"


def test_simplify_keeps_negations_and_small_words():
    assert simplify("Euh comment ne pas casser le build ?") == "comment ne pas casser le build ?"


def test_simplify_collapses_repeated_punctuation_and_spaces():
    assert simplify("Pourquoi   ça plante ???   !!!") == "Pourquoi ça plante ? !"


def test_simplify_does_not_cut_words_containing_a_filler():
    # "genre" dans "genres" et "hi" dans "this" ne doivent pas être touchés
    assert simplify("Quels genres de films aime this guy ?") == "Quels genres de films aime this guy ?"


def test_simplify_returns_original_when_nothing_left():
    assert simplify("Salut !") == "Salut !"
    assert simplify("   ") == "   "


class RecordingAPI(FakeRapideAPI):
    """Mémorise les messages envoyés au LLM principal."""

    def __init__(self):
        super().__init__()
        self.sent_messages = []

    def stream_ndjson(self, endpoint: str, data=None, json_data=None, **kwargs):
        self.sent_messages.append((json_data or {}).get("messages", []))
        yield from super().stream_ndjson(endpoint, data=data, json_data=json_data, **kwargs)


def _app_with(api):
    app = SensAI(db_url="sqlite:///:memory:")
    app.api = api
    app.chat_engine.api = api
    app.load_or_create_profile(email="simplify@test.com", name="SimplifyUser")
    return app


def test_engine_sends_simplified_prompt_but_stores_original():
    api = RecordingAPI()
    app = _app_with(api)

    app.chat("Salut, en fait comment marche Python stp ?")

    assert app.context.messages[0].content == "Salut, en fait comment marche Python stp ?"
    assert api.sent_messages[-1][-1]["content"] == "comment marche Python ?"


def test_engine_simplifier_can_be_disabled():
    api = RecordingAPI()
    app = _app_with(api)
    app.chat_engine.simplify_prompt = False

    app.chat("Salut, en fait comment marche Python stp ?")

    assert api.sent_messages[-1][-1]["content"] == "Salut, en fait comment marche Python stp ?"


def test_guardrail_receives_simplified_prompt():
    seen = []

    class StubGuardrail:
        def classify(self, user_input: str) -> str:
            seen.append(user_input)
            return "LEGAL"

    app = SensAI(db_url="sqlite:///:memory:", guardrail=StubGuardrail())
    app.chat_engine.blocked_responses = {"ILLEGAL": "Non."}
    app.api = app.chat_engine.api = FakeRapideAPI()
    app.load_or_create_profile(email="guard-simplify@test.com", name="GuardUser")

    app.chat("Euh du coup comment marche Python ?")

    assert seen == ["comment marche Python ?"]


def test_workflow_sends_simplified_prompt_but_stores_original():
    api = RecordingAPI()
    app = _app_with(api)

    class AlwaysGrounded:
        def grade(self, user_input, candidate, facts):
            from src.galerelm.graph import HallucinationGrade
            return HallucinationGrade(grounded=True, critique="")

    app.chat_engine.hallucination_grader = AlwaysGrounded()

    app.chat("Salut, en fait comment marche Python stp ?")

    assert app.context.messages[0].content == "Salut, en fait comment marche Python stp ?"
    assert api.sent_messages[-1][-1]["content"] == "comment marche Python ?"


def test_sensai_use_simplifier_flag_reaches_engine():
    assert SensAI(db_url="sqlite:///:memory:").chat_engine.simplify_prompt is True
    assert SensAI(db_url="sqlite:///:memory:", use_simplifier=False).chat_engine.simplify_prompt is False
