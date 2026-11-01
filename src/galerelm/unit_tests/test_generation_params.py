import copy

import pytest

from src.commands import ParamsCommand
from src.config import DEFAULT_GENERATION, Config, ConfigError, config
from src.galerelm.graph import HallucinationGrader
from src.galerelm.intent_classifier import IntentGuardrail
from src.galerelm.models import Chat, Options
from src.main import load_config, main, parse_args
from src.rapideAPI import RapideAPI


@pytest.fixture(autouse=True)
def restore_global_config():
    """Les tests modifient le singleton config : on le remet dans son état après chaque test."""
    saved = (copy.deepcopy(config.GENERATION), copy.deepcopy(config._startup_generation), config.KEEP_ALIVE)
    yield
    config.GENERATION, config._startup_generation, config.KEEP_ALIVE = saved


def write_yaml(tmp_path, content):
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")
    return path


class CapturingOllama:
    """Faux Ollama : mémorise la charge utile de chaque requête de chat."""
    base_url = "http://fake-ollama"

    def __init__(self, content='{"grounded": true, "critique": ""}'):
        self.content = content
        self.payloads = []

    def stream_ndjson(self, endpoint, data=None, json_data=None, **kwargs):
        self.payloads.append(json_data)
        yield {"message": {"role": "assistant", "content": self.content}, "done": True, "model": "m"}


# ── Configuration YAML ───────────────────────────────────────────────

def test_yaml_generation_section_sets_each_profile(tmp_path):
    cfg = Config().load_yaml(write_yaml(tmp_path, """
ollama:
  keep_alive: "-1"
generation:
  chat:
    temperature: 0.2
    num_ctx: 8192
    stop: ["###"]
  judge:
    num_predict: 300
"""))
    assert cfg.GENERATION["chat"]["temperature"] == 0.2
    assert cfg.GENERATION["chat"]["num_ctx"] == 8192
    assert cfg.GENERATION["chat"]["stop"] == ["###"]
    assert cfg.GENERATION["chat"]["top_k"] == DEFAULT_GENERATION["chat"]["top_k"]   # non précisé : défaut
    assert cfg.GENERATION["judge"]["num_predict"] == 300
    assert cfg.keep_alive == -1


@pytest.mark.parametrize("content, message", [
    ("generation:\n  writer:\n    temperature: 0.2\n", "profil de génération inconnu 'writer'"),
    ("generation:\n  chat:\n    temprature: 0.2\n", "paramètre de génération inconnu 'temprature'"),
    ("generation:\n  chat:\n    temperature: 3\n", "'temperature' doit être entre 0.0 et 2.0"),
    ("generation:\n  chat:\n    top_k: 2.5\n", "valeur invalide '2.5' pour 'top_k'"),
    ("generation:\n  chat:\n    num_ctx: true\n", "valeur invalide 'True' pour 'num_ctx'"),
    ("generation:\n  chat:\n    stop: 12\n", "'stop' doit être une liste"),
    ("generation:\n  chat: 0.2\n", "'generation.chat' doit être un dictionnaire"),
])
def test_yaml_generation_errors_are_explicit(tmp_path, content, message):
    with pytest.raises(ConfigError, match=message):
        Config().load_yaml(write_yaml(tmp_path, content))


def test_default_profiles_are_independent_copies():
    first, second = Config(), Config()
    first.set_generation("chat", "temperature", 0.1)
    assert second.GENERATION["chat"]["temperature"] == DEFAULT_GENERATION["chat"]["temperature"]


# ── Options CLI ──────────────────────────────────────────────────────

def test_cli_flags_override_yaml_for_chat_profile(tmp_path, monkeypatch):
    monkeypatch.setattr("src.main.config", Config())
    from src import main as main_module
    path = write_yaml(tmp_path, "generation:\n  chat:\n    temperature: 0.2\n    top_k: 10\n")

    load_config(parse_args(["--config", str(path), "--temperature", "0.9", "--seed", "42", "--keep-alive", "1h"]))

    cfg = main_module.config
    assert cfg.GENERATION["chat"]["temperature"] == 0.9   # CLI > YAML
    assert cfg.GENERATION["chat"]["top_k"] == 10          # YAML > défaut
    assert cfg.GENERATION["chat"]["seed"] == 42
    assert cfg.keep_alive == "1h"


def test_invalid_cli_value_stops_with_config_error(monkeypatch, capsys):
    monkeypatch.setattr("src.main.config", Config())
    assert main(["--num-ctx", "10", "--skip-check", "--db", "sqlite:///:memory:"]) == 2
    assert "'num_ctx' doit être entre 256" in capsys.readouterr().err


# ── Options envoyées à Ollama ────────────────────────────────────────

def test_options_take_profile_values_and_explicit_values_win():
    config.set_generation("chat", "temperature", 0.3)
    assert Options().temperature == 0.3
    assert Options(temperature=1.2).temperature == 1.2
    assert Options.from_profile("judge").temperature == 0.0
    assert Options.from_format({"top_k": 5}).temperature == 0.3


def test_options_payload_omits_random_seed_and_empty_stop():
    payload = Options().format()
    assert "seed" not in payload and "stop" not in payload
    config.set_generation("chat", "seed", 7)
    config.set_generation("chat", "stop", "###,END")
    payload = Options().format()
    assert payload["seed"] == 7
    assert payload["stop"] == ["###", "END"]


def test_chat_payload_uses_chat_profile_and_keep_alive():
    config.set_generation("chat", "num_ctx", 8192)
    config.KEEP_ALIVE = "-1"
    payload = Chat(model="m", api=RapideAPI(base_url="http://fake")).format()
    assert payload["options"]["num_ctx"] == 8192
    assert payload["options"]["num_predict"] == -1
    assert payload["keep_alive"] == -1


def test_judge_uses_judge_profile_and_follows_live_changes():
    fake = CapturingOllama()
    grader = HallucinationGrader(api=fake, model="m")

    grader.grade("question", "réponse", facts=["fait"])
    assert fake.payloads[-1]["options"]["temperature"] == 0.0
    assert fake.payloads[-1]["options"]["num_predict"] == 160

    config.set_generation("judge", "num_predict", 300)
    grader.grade("question", "réponse", facts=["fait"])
    assert fake.payloads[-1]["options"]["num_predict"] == 300


def test_guardrail_uses_guardrail_profile():
    fake = CapturingOllama(content='{"category": "LEGAL"}')
    IntentGuardrail(api=fake, model="m").classify("Bonjour")
    assert fake.payloads[0]["options"]["temperature"] == 0.0
    assert fake.payloads[0]["options"]["num_predict"] == 128
    assert fake.payloads[0]["options"]["num_ctx"] == 2048


# ── Commande /params ─────────────────────────────────────────────────

class FakeApp:
    model = "llama3.2"


def test_params_shows_every_profile(capsys):
    ParamsCommand().execute(FakeApp(), "")
    out = capsys.readouterr().out
    assert "keep_alive" in out
    for word in ("chat", "judge", "guardrail", "temperature", "num_ctx", "aléatoire"):
        assert word in out


def test_params_sets_chat_and_other_profiles(capsys):
    ParamsCommand().execute(FakeApp(), "temperature 0.2")
    ParamsCommand().execute(FakeApp(), "judge.num_predict 200")
    assert config.GENERATION["chat"]["temperature"] == 0.2
    assert config.GENERATION["judge"]["num_predict"] == 200
    assert "chat.temperature = 0.2" in capsys.readouterr().out


@pytest.mark.parametrize("args, message", [
    ("top_p 5", "'top_p' doit être entre 0.0 et 1.0"),
    ("writer.temperature 0.2", "profil de génération inconnu 'writer'"),
    ("temperature", "Usage : /params"),
])
def test_params_rejects_invalid_input(args, message, capsys):
    before = copy.deepcopy(config.GENERATION)
    ParamsCommand().execute(FakeApp(), args)
    assert message in capsys.readouterr().out
    assert config.GENERATION == before


def test_params_reset_restores_startup_values():
    config.set_generation("chat", "temperature", 0.4)
    config.mark_startup_generation()
    ParamsCommand().execute(FakeApp(), "temperature 1.5")
    ParamsCommand().execute(FakeApp(), "reset")
    assert config.GENERATION["chat"]["temperature"] == 0.4
