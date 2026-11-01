import time
from datetime import datetime, timedelta

from src.galerelm.models.scheduled_task import ScheduledTask
from src.main import SensAI
from src.repl import TerminalREPL
from src.scheduler.runner import TaskRunner
from src.scheduler.task_manager import TaskManager


class FakeOllama:
    """Faux Ollama : répond en reprenant la demande ; demande un email si on le lui demande."""
    base_url = "http://fake"

    def stream_ndjson(self, endpoint, json_data=None, **kwargs):
        last = json_data["messages"][-1]
        if "email" in last["content"] and last["role"] == "user":
            yield {"message": {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "email", "arguments": {"recipient": "a@b.c", "subject": "s", "content": "c"}}}]},
                "done": True, "model": "m"}
            return
        yield {"message": {"role": "assistant", "content": f"Fait : {last['content']}"}, "done": True, "model": "m"}

    def post(self, endpoint, json=None, **kwargs):
        inputs = json["input"]
        return {"embeddings": [[1.0, 0.0]] * (1 if isinstance(inputs, str) else len(inputs))}


def make_app(db_url="sqlite:///:memory:"):
    app = SensAI(db_url=db_url)
    app.api = app.chat_engine.api = app.task_engine.api = FakeOllama()
    app.load_or_create_profile(email="tasks@test.com", name="Tasks")
    return app


def add_task(app, prompt, minutes=-1, recurrence=None):
    return TaskManager(app.session).create_task(app.profile.id, prompt, datetime.now() + timedelta(minutes=minutes), recurrence)


def test_runner_executes_due_task_in_a_new_chat_and_notifies():
    app = make_app()
    task = add_task(app, "dis bonjour")
    add_task(app, "plus tard", minutes=30)
    results = []
    app.on_task_result = lambda t, response, error: results.append((t.prompt, response, error))

    assert app.task_runner.run_due_tasks() == 1

    # La réponse vient du modèle (le simplificateur de prompt peut raccourcir la demande)
    assert [(p, e) for p, _, e in results] == [("dis bonjour", None)]
    assert results[0][1].startswith("Fait : [Tâche planifiée]")
    app.session.expire_all()
    assert app.session.get(ScheduledTask, task.id).status == "completed"
    contexts = app.session_manager.list_contexts(app.session, app.profile.id)
    assert len(contexts) == 2                     # le chat de la CLI + le chat de la tâche
    assert [m.role for m in contexts[0].messages] == ["user", "assistant"]
    assert app.context.messages == []             # la conversation en cours n'est pas touchée


def test_recurring_task_is_rescheduled():
    app = make_app()
    task = add_task(app, "résumé quotidien", recurrence="daily")
    before = task.scheduled_at
    app.task_runner.run_due_tasks()
    app.session.expire_all()
    task = app.session.get(ScheduledTask, task.id)
    assert task.status == "pending" and task.scheduled_at > before


def test_failed_task_is_marked_and_reported():
    app = make_app()
    task = add_task(app, "boum")
    errors = []

    def broken(task, session):
        raise RuntimeError("Ollama injoignable")

    runner = TaskRunner(app.SessionLocal, executor=broken, on_result=lambda t, r, e: errors.append(str(e)))
    runner.run_due_tasks()
    app.session.expire_all()
    assert app.session.get(ScheduledTask, task.id).status == "failed"
    assert errors == ["Ollama injoignable"]


def test_sensitive_tools_are_refused_in_scheduled_tasks():
    app = make_app()
    app.chat_engine.confirm_tool = lambda name, args: True   # la confirmation du terminal ne s'applique pas au runner
    sent = []
    app.tools.get("email").execute = lambda ctx, args: sent.append(args)
    add_task(app, "envoie un email à Bob")
    app.task_runner.run_due_tasks()
    assert sent == []


def test_background_thread_runs_tasks_and_stops(tmp_path):
    app = make_app(f"sqlite:///{tmp_path / 'tasks.db'}")
    task = add_task(app, "en arrière-plan")
    done = []
    app.on_task_result = lambda t, response, error: done.append(response)

    app.start_scheduler(interval=0.05)
    deadline = time.time() + 5
    while not done and time.time() < deadline:
        time.sleep(0.05)
    app.stop_scheduler()

    assert len(done) == 1 and done[0].startswith("Fait : [Tâche planifiée]")
    assert not app.task_runner.running
    app.session.expire_all()
    assert app.session.get(ScheduledTask, task.id).status == "completed"


def test_repl_prints_task_results(capsys):
    app = make_app()
    repl = TerminalREPL(app)
    assert app.on_task_result == repl.print_task_result
    task = add_task(app, "dis bonjour")
    app.task_runner.run_due_tasks()
    out = capsys.readouterr().out
    assert "[Tâche planifiée] dis bonjour" in out and "nouveau chat" in out
