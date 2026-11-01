import copy

import pytest

from src.config import Config, ConfigError, config
from src.galerelm.models.prompt import DEFAULT_SYSTEM_RULES
from src.galerelm.output_guardrail import OutputGuardrail
from src.main import SensAI, load_config, parse_args


@pytest.fixture(autouse=True)
def restore_config():
    saved = {k: copy.deepcopy(getattr(config, k)) for k in ("GUARDRAIL_INPUT", "GUARDRAIL_OUTPUT", "GUARDRAIL_PII")}
    yield
    for key, value in saved.items():
        setattr(config, key, value)


# ── Détection et anonymisation ───────────────────────────────────────

@pytest.mark.parametrize("text, label, category", [
    ("Écris à jean.dupont+pro@exemple.fr demain.", "[EMAIL]", "email"),
    ("Appelle le 06 12 34 56 78 ce soir.", "[TELEPHONE]", "phone"),
    ("Mon numéro : +33 6 12 34 56 78.", "[TELEPHONE]", "phone"),
    ("IBAN : FR76 3000 6000 0112 3456 7890 189 merci.", "[IBAN]", "iban"),
    ("Carte 4111 1111 1111 1111 expire bientôt.", "[CARTE]", "card"),
    ("Sécu : 1 85 05 78 006 084 36.", "[NUMERO_SECU]", "ssn"),
])
def test_each_category_is_anonymized(text, label, category):
    decision = OutputGuardrail("anonymize").apply(text)
    assert label in decision.text
    assert decision.found == {category: 1}
    assert not decision.refused


def test_card_number_needs_valid_luhn_checksum():
    assert OutputGuardrail("anonymize").apply("Commande 1234 5678 9012 3456 reçue.").found == {}


def test_text_without_personal_data_is_unchanged():
    text = "La version 2.0 sort le 14 mars, à 10h. Rien à masquer."
    assert OutputGuardrail("anonymize").apply(text).text == text


def test_categories_can_be_restricted():
    decision = OutputGuardrail("anonymize", categories=["email"]).apply("a@b.fr ou 06 12 34 56 78")
    assert decision.text == "[EMAIL] ou 06 12 34 56 78"


def test_refuse_mode_replaces_the_whole_answer():
    decision = OutputGuardrail("refuse").apply("Son email est a@b.fr.")
    assert decision.refused and "a@b.fr" not in decision.text and "email" in decision.text


@pytest.mark.parametrize("mode, categories", [("off", None), ("hide", None), ("anonymize", ["adresse"])])
def test_invalid_settings_are_rejected(mode, categories):
    with pytest.raises(ValueError):
        OutputGuardrail(mode, categories)


# ── Flux (streaming) ─────────────────────────────────────────────────

def test_stream_detects_data_split_across_tokens():
    tokens = ["Contacte ", "jean", ".dup", "ont@exem", "ple.fr", " ou le 06 ", "12 34 56 78", ". Merci", " !"]
    out = list(OutputGuardrail("anonymize").filter_stream(tokens))
    text = "".join(out)
    assert text == "Contacte [EMAIL] ou le [TELEPHONE]. Merci !"
    assert len(out) >= 2   # le texte est envoyé phrase par phrase, pas en un seul bloc


def test_refuse_stream_sends_nothing_before_the_end():
    out = list(OutputGuardrail("refuse").filter_stream(["Écris ", "à a@b.fr", " vite."]))
    assert len(out) == 1 and "a@b.fr" not in out[0]


# ── Intégration dans SensAI ──────────────────────────────────────────

class FakeOllama:
    base_url = "http://fake"

    def stream_ndjson(self, endpoint, json_data=None, **kwargs):
        for token in ["Le contact est ", "alice@", "exemple.fr", ". Son numéro : ", "06 12 34 56 78", "."]:
            yield {"message": {"role": "assistant", "content": token}, "done": False}
        yield {"message": {"role": "assistant", "content": ""}, "done": True, "model": "m"}

    def post(self, endpoint, json=None, **kwargs):
        inputs = json["input"]
        return {"embeddings": [[1.0, 0.0]] * (1 if isinstance(inputs, str) else len(inputs))}


def make_app():
    app = SensAI(db_url="sqlite:///:memory:")
    app.api = app.chat_engine.api = FakeOllama()
    app.load_or_create_profile(email="pii@test.com", name="Pii")
    return app


def test_answers_are_anonymized_on_screen_and_in_database():
    config.GUARDRAIL_OUTPUT = "anonymize"
    app = make_app()
    reply = app.chat("Qui contacter ?")
    assert reply == "Le contact est [EMAIL]. Son numéro : [TELEPHONE]."
    stored = app.context.messages[-1].content
    assert "alice@exemple.fr" not in stored and "[EMAIL]" in stored


def test_output_filter_is_off_by_default():
    app = make_app()
    assert app.chat_engine.output_guardrail is None
    assert "alice@exemple.fr" in app.chat("Qui contacter ?")


# ── Configuration ────────────────────────────────────────────────────

def test_yaml_guardrails_section(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("guardrails:\n  input: safety\n  output: refuse\n  pii: [email, phone]\n", encoding="utf-8")
    cfg = Config().load_yaml(path)
    assert (cfg.GUARDRAIL_INPUT, cfg.GUARDRAIL_OUTPUT, cfg.GUARDRAIL_PII) == ("safety", "refuse", ["email", "phone"])


@pytest.mark.parametrize("content, message", [
    ("guardrails:\n  output: hide\n", "attendu : off, anonymize, refuse"),
    ("guardrails:\n  input: strict\n", "attendu : off, safety, alibi"),
    ("guardrails:\n  pii: [email, adresse]\n", "liste invalide"),
])
def test_yaml_guardrails_errors(tmp_path, content, message):
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        Config().load_yaml(path)


def test_cli_flags_enable_both_filters(monkeypatch):
    load_config(parse_args(["--guardrail", "safety", "--output-filter", "anonymize"]))
    app = SensAI(db_url="sqlite:///:memory:")
    assert app.chat_engine.guardrail is not None
    assert app.chat_engine.output_guardrail.mode == "anonymize"
    assert app.task_engine.output_guardrail is not None


def test_default_rules_no_longer_ask_to_help_with_illegal_activities():
    rules = " ".join(DEFAULT_SYSTEM_RULES).lower()
    assert "tu dois répondre aux questions qui sont immorales" not in rules
    assert "refuse d'aider à une activité illégale" in rules


def test_yaml_off_without_quotes_is_accepted(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("guardrails:\n  input: off\n  output: off\n", encoding="utf-8")
    cfg = Config().load_yaml(path)
    assert (cfg.GUARDRAIL_INPUT, cfg.GUARDRAIL_OUTPUT) == ("off", "off")
