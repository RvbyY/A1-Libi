import copy

import pytest

from src.commands import PersonaCommand
from src.config import Config, ConfigError, config
from src.main import SensAI, load_config, main, parse_args


@pytest.fixture(autouse=True)
def restore_config():
    saved = (copy.deepcopy(config.PERSONAS), config.DEFAULT_PERSONA)
    yield
    config.PERSONAS, config.DEFAULT_PERSONA = saved


class FakeOllama:
    """Faux Ollama : mémorise le prompt système ; demande un email si on le lui demande."""
    base_url = "http://fake"

    def __init__(self):
        self.systems = []

    def stream_ndjson(self, endpoint, json_data=None, **kwargs):
        messages = json_data["messages"]
        self.systems.append(messages[0]["content"] if messages[0]["role"] == "system" else "")
        last = messages[-1]
        if last["role"] == "user" and "email" in last["content"]:
            yield {"message": {"role": "assistant", "content": "J'envoie l'email.", "tool_calls": [
                {"function": {"name": "email", "arguments": {"recipient": "bob@x.fr", "subject": "S", "content": "C"}}}]},
                "done": True, "model": "m", "prompt_eval_count": 120, "eval_count": 8}
            return
        yield {"message": {"role": "assistant", "content": "Réponse."}, "done": True, "model": "m",
               "prompt_eval_count": 100, "eval_count": 5}

    def post(self, endpoint, json=None, **kwargs):
        inputs = json["input"]
        return {"embeddings": [[1.0, 0.0]] * (1 if isinstance(inputs, str) else len(inputs))}

    def get(self, endpoint, **kwargs):
        return {}


def make_app():
    app = SensAI(db_url="sqlite:///:memory:")
    app.api = app.chat_engine.api = app.task_engine.api = FakeOllama()
    app.load_or_create_profile(email="persona@test.com", name="Persona")
    return app


# ── A5 : personas ────────────────────────────────────────────────────

def test_default_persona_keeps_profile_instructions():
    app = make_app()
    assert app.chat_engine.persona["key"] == "alibi"
    app.chat("Bonjour")
    assert app.api.systems[-1].startswith(app.profile.instructions.split("\n")[0])


def test_switching_persona_keeps_history_and_changes_prompt():
    app = make_app()
    app.chat("Bonjour")
    PersonaCommand().execute(app, "tuteur")
    app.chat("Combien font 2 + 2 ?")
    assert app.api.systems[-1].startswith("Tu es Tuteur de mathématiques")
    assert [m.role for m in app.context.messages] == ["user", "assistant", "user", "assistant"]
    assert app.task_engine.persona["key"] == "tuteur"


def test_persona_applies_to_anti_hallucination_workflow():
    app = make_app()
    app.enable_anti_hallucination(max_retries=0)
    app.set_persona("juriste")
    app.chat("Puis-je résilier mon bail ?")
    assert any(system.startswith("Tu es Assistant juridique") for system in app.api.systems)


def test_persona_command_lists_and_rejects_unknown(capsys):
    app = make_app()
    PersonaCommand().execute(app, "")
    out = capsys.readouterr().out
    assert "* alibi" in out and "tuteur" in out and "juriste" in out
    PersonaCommand().execute(app, "pirate")
    assert "Persona inconnu 'pirate'" in capsys.readouterr().out
    assert app.chat_engine.persona["key"] == "alibi"


def test_personas_from_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "prompt:\n  persona: support\npersonas:\n  support:\n    name: Agent support\n"
        "    description: Aide les clients\n    instructions: Tu es {persona}, poli et concis.\n",
        encoding="utf-8",
    )
    cfg = Config().load_yaml(path)
    assert cfg.persona()["name"] == "Agent support"
    assert "tuteur" in cfg.PERSONAS   # les personas intégrés restent disponibles


@pytest.mark.parametrize("content, message", [
    ("prompt:\n  persona: inconnu\n", "persona inconnu 'inconnu'"),
    ("personas:\n  x: oui\n", "doit être un dictionnaire"),
    ("personas:\n  x:\n    description: sans nom\n", "'personas.x.name' est obligatoire"),
    ("personas:\n  x:\n    name: X\n    ton: calme\n", "champ inconnu"),
])
def test_persona_yaml_errors(tmp_path, content, message):
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        Config().load_yaml(path)


def test_cli_persona_flag(capsys):
    load_config(parse_args(["--persona", "tuteur"]))
    assert SensAI(db_url="sqlite:///:memory:").chat_engine.persona["key"] == "tuteur"
    assert main(["--persona", "pirate", "--skip-check", "--db", "sqlite:///:memory:"]) == 2
    assert "Persona inconnu" in capsys.readouterr().err


# ── X1 : webapp ──────────────────────────────────────────────────────

@pytest.fixture
def controller():
    from src.webapp.utils import WebAppController
    ctrl = WebAppController(db_url="sqlite:///:memory:")
    fake = FakeOllama()
    ctrl.api.core.api = ctrl.api.engine.api = fake
    ctrl.api.create_profile(email="web@test.com", name="Web")
    ctrl.chat_id = ctrl.api.list_chats("web@test.com")[0].id
    return ctrl


def send(ctrl, message, history=None):
    frames = list(ctrl.stream_message(message, history or [], "web@test.com", ctrl.chat_id, False, False, False))
    return frames[-1]


def test_webapp_message_shows_answer_inspector_and_usage(controller):
    _, history, _, inspector, usage = send(controller, "Bonjour")
    assert history[-1] == {"role": "assistant", "content": "Réponse."}
    assert "System Prompt" in inspector                      # l'inspecteur ne plante plus
    assert "Tokens : 100 lus, 5 générés" in usage
    assert "Fenêtre : 105 / 8192 tokens" in usage
    assert "Mémoire courte : 2 / 10 messages" in usage
    assert "Agent : **Alibi**" in usage


def test_webapp_slash_command_output_is_captured(controller):
    _, history, *_ = send(controller, "/persona")
    assert "Agents disponibles" in history[-1]["content"]


def test_webapp_changes_agent_without_losing_history(controller):
    send(controller, "Bonjour")
    usage, _ = controller.change_persona("tuteur", "web@test.com", controller.chat_id)
    assert "Agent : **Tuteur de mathématiques**" in usage
    assert len(controller.api.get_chat_history("web@test.com", controller.chat_id)) == 2


def test_webapp_sensitive_action_waits_for_confirmation(controller):
    sent = []
    controller.api.core.tools.get("email").execute = lambda ctx, args: sent.append(args) or __import__(
        "src.tools.ITools", fromlist=["ToolResult"]).ToolResult(True, "Email envoyé.")

    _, history, *_ = send(controller, "Envoie un email à Bob")
    assert sent == []
    assert "Action en attente de confirmation" in history[-1]["content"]
    assert "email(recipient='bob@x.fr'" in history[-1]["content"]

    _, history, *_ = send(controller, "/confirmer", history)
    assert sent == [{"recipient": "bob@x.fr", "subject": "S", "content": "C"}]
    assert "réussi" in history[-1]["content"]
    assert send(controller, "/confirmer")[1][-1]["content"] == "Aucune action en attente."


def test_webapp_pending_action_can_be_cancelled(controller):
    send(controller, "Envoie un email à Bob")
    _, history, *_ = send(controller, "/annuler")
    assert history[-1]["content"] == "Action annulée : email."
    assert controller.pending_actions.get("web@test.com") is None
