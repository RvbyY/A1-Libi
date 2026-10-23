import pytest

from src.config import Config, ConfigError
from src.main import load_config, main, parse_args


@pytest.fixture
def fresh_config(monkeypatch):
    """Remplace le singleton config par une instance neuve pour isoler chaque test."""
    cfg = Config()
    monkeypatch.setattr("src.main.config", cfg)
    return cfg


def write_yaml(tmp_path, content: str):
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_yaml_applies_known_keys(tmp_path):
    path = write_yaml(tmp_path, """
ollama:
  host: http://gpu-box:11434
  model: qwen2.5:7b
  timeout: "30"
memory:
  context_limit: 4
""")
    cfg = Config().load_yaml(path)
    assert cfg.OLLAMA_HOST == "http://gpu-box:11434"
    assert cfg.DEFAULT_MODEL == "qwen2.5:7b"
    assert cfg.OLLAMA_TIMEOUT == 30
    assert cfg.CONTEXT_LIMIT == 4
    assert cfg.loaded_file == str(path)


def test_load_yaml_empty_file_keeps_defaults(tmp_path):
    cfg = Config().load_yaml(write_yaml(tmp_path, ""))
    assert cfg.DEFAULT_MODEL == Config.DEFAULT_MODEL


@pytest.mark.parametrize("content, message", [
    ("ollama:\n  modle: llama3.2\n", "clé inconnue 'ollama.modle'"),
    ("ollama: llama3.2\n", "doit être un dictionnaire"),
    ("- a\n- b\n", "dictionnaire de sections"),
    ("memory:\n  context_limit: beaucoup\n", "valeur invalide"),
    ("ollama: [unclosed\n", "YAML invalide"),
])
def test_load_yaml_rejects_invalid_files(tmp_path, content, message):
    with pytest.raises(ConfigError, match=message):
        Config().load_yaml(write_yaml(tmp_path, content))


def test_load_yaml_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="introuvable"):
        Config().load_yaml(tmp_path / "absent.yaml")


def test_cli_overrides_yaml(tmp_path, fresh_config):
    path = write_yaml(tmp_path, "ollama:\n  model: from-yaml\n  host: http://yaml:1\n")
    load_config(parse_args(["--config", str(path), "--model", "from-cli"]))
    assert fresh_config.DEFAULT_MODEL == "from-cli"
    assert fresh_config.OLLAMA_HOST == "http://yaml:1"


def test_default_config_file_is_loaded_when_present(tmp_path, monkeypatch, fresh_config):
    write_yaml(tmp_path, "ollama:\n  model: auto-loaded\n")
    monkeypatch.chdir(tmp_path)
    load_config(parse_args([]))
    assert fresh_config.DEFAULT_MODEL == "auto-loaded"


def test_main_returns_error_code_on_invalid_config(tmp_path, fresh_config, capsys):
    path = write_yaml(tmp_path, "ollama:\n  unknown: 1\n")
    assert main(["--config", str(path)]) == 2
    assert "Configuration invalide" in capsys.readouterr().err


def test_main_stops_when_model_is_missing(fresh_config, monkeypatch, capsys):
    monkeypatch.setattr(
        "src.rapideAPI.client.RapideAPI.get",
        lambda self, endpoint, **kw: {"models": [{"name": "mistral:latest"}]},
    )
    assert main(["--model", "llama3.2", "--db", "sqlite:///:memory:"]) == 1
    err = capsys.readouterr().err
    assert "'llama3.2' n'est pas installé" in err
    assert "ollama pull llama3.2" in err
    assert "mistral:latest" in err


class RecordingREPL:
    """Remplace TerminalREPL : mémorise l'instance SensAI construite par main() sans lancer la boucle."""
    app = None

    def __init__(self, app):
        RecordingREPL.app = app

    def run(self):
        pass


def run_main_without_repl(monkeypatch, argv):
    monkeypatch.setattr("src.main.TerminalREPL", RecordingREPL)
    RecordingREPL.app = None
    assert main(argv + ["--skip-check", "--db", "sqlite:///:memory:"]) == 0
    return RecordingREPL.app


def test_anti_hallucination_disabled_by_default(fresh_config, monkeypatch):
    app = run_main_without_repl(monkeypatch, [])
    assert app.chat_engine.hallucination_grader is None


def test_anti_hallucination_flag_enables_workflow(fresh_config, monkeypatch):
    app = run_main_without_repl(monkeypatch, ["--anti-hallucination"])
    assert app.chat_engine.hallucination_grader is not None
    assert app.chat_engine.max_hallucination_retries == 2


def test_max_retries_is_forwarded(fresh_config, monkeypatch):
    app = run_main_without_repl(monkeypatch, ["--anti-hallucination", "--max-retries", "5"])
    assert app.chat_engine.max_hallucination_retries == 5


@pytest.mark.parametrize("argv, message", [
    (["--max-retries", "3"], "requiert --anti-hallucination"),
    (["--anti-hallucination", "--max-retries", "-1"], "positif ou nul"),
    (["--anti-hallucination", "--max-retries", "deux"], "invalid int value"),
])
def test_invalid_max_retries_is_rejected(argv, message, capsys):
    with pytest.raises(SystemExit) as info:
        parse_args(argv)
    assert info.value.code == 2
    assert message in capsys.readouterr().err
