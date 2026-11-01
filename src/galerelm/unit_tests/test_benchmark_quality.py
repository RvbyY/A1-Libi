import pytest

from benchmark import quality
from benchmark.quality import (
    RecordingAPI,
    build_report,
    contains_all,
    normalize,
    run,
    tool_choice_correct,
)
from src.config import config


def test_normalize_ignores_case_and_accents():
    assert normalize("Préféré à LYON") == "prefere a lyon"


@pytest.mark.parametrize("answer, expected, ok", [
    ("Tu habites à Lyon.", ["lyon"], True),
    ("Ton plat préféré : la RACLETTE", ["raclette"], True),
    ("Je ne sais pas.", ["lyon"], False),
    ("", ["lyon"], False),
    ("   ", [], False),
])
def test_contains_all(answer, expected, ok):
    assert contains_all(answer, expected) is ok


def test_tool_choice_correct():
    assert tool_choice_correct(["calendar"], "calendar")
    assert not tool_choice_correct(["email"], "calendar")
    assert tool_choice_correct([], None)
    assert not tool_choice_correct(["calendar"], None)


class FakeOllama:
    """
    Faux Ollama qui se comporte comme un modèle docile :
    - "Teste les outils avec le message X" : appelle tools_selftest, puis reprend le résultat après relance ;
    - une question : répond avec le souvenir s'il figure dans le prompt système, sinon "Je ne sais pas".
    """
    base_url = "http://fake"

    def stream_ndjson(self, endpoint, json_data=None, **kwargs):
        messages = json_data["messages"]
        last = messages[-1]
        system = messages[0]["content"] if messages[0]["role"] == "system" else ""
        if last["role"] == "tool":
            content, calls = f"Résultat : {last['content']}", None
        elif "Teste les outils avec le message" in last["content"]:
            word = last["content"].rstrip(".").split()[-1]
            content, calls = "", [{"function": {"name": "tools_selftest", "arguments": {"message": word}}}]
        elif "habite" in last["content"] and "?" in last["content"]:
            content, calls = ("Tu habites à Lyon." if "Lyon" in system else "Je ne sais pas."), None
        else:
            content, calls = "OK", None
        message = {"role": "assistant", "content": content}
        if calls:
            message["tool_calls"] = calls
        yield {"message": message, "done": True, "model": "m", "prompt_eval_count": len(system) // 4, "eval_count": 5}

    def post(self, endpoint, json=None, **kwargs):
        inputs = json["input"]
        count = 1 if isinstance(inputs, str) else len(inputs)
        return {"embeddings": [[1.0, 0.0, 0.0]] * count}

    def get(self, endpoint, **kwargs):
        return {}


def fake_app():
    from src.main import SensAI
    app = SensAI(db_url="sqlite:///:memory:")
    app.api = app.chat_engine.api = FakeOllama()
    return app


DATASET = {
    "tool_answer": [{"prompt": "Teste les outils avec le message abricot.", "expected": "abricot"}],
    "memory": [{"fact": "Retiens bien ceci : j'habite à Lyon.", "question": "Dans quelle ville est-ce que j'habite ?",
                "expected": ["lyon"]}],
    "tool_choice": [{"prompt": "Teste les outils avec le message ping.", "expected": "tools_selftest"},
                    {"prompt": "Bonjour", "expected": None}],
}


def by_variant(rows):
    return {row["variant"]: row for row in rows}


def test_relance_outils_baseline_has_empty_answer():
    rows = by_variant(run(["relance_outils"], DATASET, reps=1, app_factory=fake_app, log=lambda *_: None))
    assert rows["sans relance"]["tool_called"] and not rows["sans relance"]["success"]
    assert rows["sans relance"]["answer"] == ""
    assert rows["avec relance"]["success"]
    assert rows["avec relance"]["generations"] == 2


def test_memoire_inter_chats_needs_archiving():
    rows = by_variant(run(["memoire_inter_chats"], DATASET, reps=1, app_factory=fake_app, log=lambda *_: None))
    assert rows["sans archivage"]["answer"] == "Je ne sais pas." and not rows["sans archivage"]["success"]
    assert rows["avec archivage"]["success"]


def test_description_outils_changes_prompt_size_and_restores_config():
    before = (config.TOOLS_LISTING, config.generation_options("chat"))
    rows = run(["description_outils"], DATASET, reps=1, app_factory=fake_app, log=lambda *_: None)

    sizes = {r["variant"]: r["prompt_tokens"] for r in rows if r["expected"] is None}
    assert sizes["signatures complètes"] > sizes["noms seulement"] > sizes["aucune liste"]
    assert all(r["success"] for r in rows)
    assert (config.TOOLS_LISTING, config.generation_options("chat")) == before


def test_recording_api_keeps_generation_counters():
    recording = RecordingAPI(FakeOllama())
    list(recording.stream_ndjson("api/chat", json_data={"messages": [{"role": "user", "content": "Bonjour"}]}))
    assert recording.generations == [{"prompt_tokens": 0, "gen_tokens": 5}]
    assert recording.base_url == "http://fake"


def test_report_shows_baseline_and_delta():
    rows = run(["relance_outils"], DATASET, reps=1, app_factory=fake_app, log=lambda *_: None)
    report = build_report(rows, "m", 1)
    assert "| sans relance | 0/1 | 0.0 % |" in report
    assert "| avec relance | 1/1 | 100.0 % |" in report and "+100.0 points" in report
    assert "(vide)" in report


def test_relance_outils_rejects_answer_that_only_copies_the_call():
    class CopyingOllama(FakeOllama):
        def stream_ndjson(self, endpoint, json_data=None, **kwargs):
            if json_data["messages"][-1]["role"] == "tool":
                yield {"message": {"role": "assistant", "content": '{"name": "tools_selftest", "arguments": {"message": "abricot"}}'},
                       "done": True, "model": "m"}
                return
            yield from super().stream_ndjson(endpoint, json_data=json_data, **kwargs)

    def app_factory():
        app = fake_app()
        app.api = app.chat_engine.api = CopyingOllama()
        return app

    rows = by_variant(run(["relance_outils"], DATASET, reps=1, app_factory=app_factory, log=lambda *_: None))
    assert "abricot" in rows["avec relance"]["answer"] and not rows["avec relance"]["success"]
