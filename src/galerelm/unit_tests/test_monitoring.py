from datetime import datetime, timedelta

import pytest

from src.commands import StatsCommand
from src.galerelm import metrics
from src.galerelm.models import InteractionLog
from src.galerelm.ollama import OllamaError
from src.main import SensAI


class FakeOllama:
    base_url = "http://fake"

    def __init__(self, fail=False, tool=False):
        self.fail = fail
        self.tool = tool

    def stream_ndjson(self, endpoint, json_data=None, **kwargs):
        if self.fail:
            raise OllamaError("Ollama injoignable")
        last = json_data["messages"][-1]
        if self.tool and last["role"] == "user":
            yield {"message": {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "tools_selftest", "arguments": {"message": "ping"}}},
            ]}, "done": True, "model": "m", "prompt_eval_count": 50, "eval_count": 3}
            return
        yield {"message": {"role": "assistant", "content": "Bonjour"}, "done": False}
        yield {"message": {"role": "assistant", "content": " !"}, "done": True, "model": "m",
               "prompt_eval_count": 120, "eval_count": 4}

    def post(self, endpoint, json=None, **kwargs):
        inputs = json["input"]
        return {"embeddings": [[1.0, 0.0]] * (1 if isinstance(inputs, str) else len(inputs))}


def make_app(**fake):
    app = SensAI(db_url="sqlite:///:memory:")
    app.api = app.chat_engine.api = FakeOllama(**fake)
    app.load_or_create_profile(email="monitor@test.com", name="Monitor")
    return app


def logs(app):
    return app.session.query(InteractionLog).order_by(InteractionLog.id).all()


# ── Journalisation de chaque échange ─────────────────────────────────

def test_each_turn_is_logged_with_its_metrics():
    app = make_app()
    app.chat("Salut")
    (row,) = logs(app)
    assert row.status == "ok" and row.error is None
    assert (row.prompt_tokens, row.gen_tokens) == (120, 4)
    assert row.latency_s >= 0 and row.first_token_s is not None
    assert row.model == app.model and row.persona == "alibi"
    assert row.user_prompt == "Salut" and row.answer == "Bonjour !"
    assert row.system_prompt_chars > 0 and row.context_id == app.context.id


def test_tool_calls_and_failures_are_logged():
    app = make_app(tool=True)
    app.chat("Teste les outils")
    row = logs(app)[-1]
    assert row.tools == ["tools_selftest"] and row.tool_failures == 0


def test_errors_are_logged_and_still_raised():
    app = make_app(fail=True)
    with pytest.raises(OllamaError):
        app.chat("Salut")
    row = logs(app)[-1]
    assert row.status == "error" and "injoignable" in row.error


def test_guardrail_refusal_is_logged_as_blocked():
    class Blocking:
        def evaluate(self, text):
            from types import SimpleNamespace
            return SimpleNamespace(category="ILLEGAL", allowed=False, refusal_message="Non.")

    app = make_app()
    app.chat_engine.guardrail = Blocking()
    assert app.chat("Demande interdite") == "Non."
    assert logs(app)[-1].status == "blocked"


def test_interrupted_generation_is_logged():
    app = make_app()
    stream = app.stream_chat("Salut")
    next(stream)
    stream.close()
    assert logs(app)[-1].status == "interrupted"


# ── Calcul des métriques ─────────────────────────────────────────────

def make_row(day, latency, status="ok", tokens=100, tools=None, model="m"):
    return InteractionLog(created_at=day, latency_s=latency, status=status, prompt_tokens=tokens, gen_tokens=10,
                          tools=tools or [], tool_failures=0, model=model, first_token_s=0.1)


def test_report_per_day_and_model():
    app = make_app()
    now = datetime(2026, 11, 2, 12, 0)
    d1, d2 = now - timedelta(days=1), now
    app.session.add_all([
        make_row(d1, 1.0), make_row(d1, 3.0, model="autre"),
        make_row(d2, 2.0, tools=["calendar"]), make_row(d2, None, status="error"),
        make_row(now - timedelta(days=30), 9.0),        # hors période
    ])
    app.session.commit()

    data = metrics.report(app.session, days=7, now=now)
    total = data["total"]
    assert total["calls"] == 4 and total["errors"] == 1 and total["error_rate"] == 25.0
    assert total["latency_mean"] == 2.0 and total["latency_p50"] == 2.0 and total["latency_p95"] == 3.0
    assert total["tool_calls"] == 1
    assert list(data["per_day"]) == ["2026-11-01", "2026-11-02"]
    assert data["per_day"]["2026-11-02"]["error_rate"] == 50.0
    assert set(data["per_model"]) == {"m", "autre"}
    text = metrics.format_report(data)
    assert "Échanges sur 7 jours : 4" in text and "2026-11-01" in text and "Par modèle" in text


def test_empty_report():
    app = make_app()
    data = metrics.report(app.session, days=7)
    assert metrics.format_report(data) == "Aucun échange enregistré sur les 7 derniers jours."


def test_stats_command(capsys):
    app = make_app()
    app.chat("Salut")
    app.chat("Encore")
    StatsCommand().execute(app, "")
    out = capsys.readouterr().out
    assert "Échanges sur 7 jours : 2" in out and "Tokens moyens : 120 lus" in out
    StatsCommand().execute(app, "zéro")
    assert "Usage" in capsys.readouterr().out


def test_webapp_monitoring_panel():
    from src.webapp.utils import WebAppController
    ctrl = WebAppController(db_url="sqlite:///:memory:")
    ctrl.api.core.api = ctrl.api.engine.api = FakeOllama()
    ctrl.api.create_profile(email="web@test.com", name="Web")
    chat_id = ctrl.api.list_chats("web@test.com")[0].id
    list(ctrl.stream_message("Salut", [], "web@test.com", chat_id, False, False, False))
    text, table = ctrl.monitoring("web@test.com")
    assert "Échanges sur 7 jours : 1" in text
    assert list(table.columns) == ["jour", "appels", "latence_moyenne_s", "latence_p95_s", "erreurs_pct", "tokens_lus"]
    assert table["appels"].sum() == 1
