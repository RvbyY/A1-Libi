from src.galerelm.intent_classifier import IntentGuardrail


class SequencedFakeAPI:
    """Simule une séquence de réponses NDJSON d'Ollama pour tester le classifieur et la résolution d'ambiguïté."""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)

    def stream_ndjson(self, endpoint: str, data=None, json_data=None, **kwargs):
        text = self.responses.pop(0) if self.responses else ""
        yield {
            "message": {"role": "assistant", "content": text},
            "done": True,
            "model": "llama3.2",
            "eval_count": 5,
            "eval_duration": 1000,
        }


def test_extract_json_and_parse_simple_category():
    raw = 'Voici le JSON:\n{\n  "controlled_substance": false,\n  "criminal_activity": true,\n  "dangerous_activity": false,\n  "category": "LEGAL"\n}'
    parsed = IntentGuardrail.extract_json(raw)
    assert parsed is not None
    assert parsed["criminal_activity"] is True

    assert IntentGuardrail.parse_simple_category("  illegal ") == "ILLEGAL"
    assert IntentGuardrail.parse_simple_category("LEGAL") == "LEGAL"
    assert IntentGuardrail.parse_simple_category("unknown") == "AMBIGUOUS"


def test_classify_boolean_overrides_category():
    api = SequencedFakeAPI([
        '{"controlled_substance": true, "criminal_activity": false, "dangerous_activity": false, "category": "LEGAL"}'
    ])
    guardrail = IntentGuardrail(api=api)
    assert guardrail.classify("Recette suspecte") == "ILLEGAL"


def test_classify_triggers_resolve_ambiguity_on_ambiguous_or_invalid_json():
    api = SequencedFakeAPI([
        '{"controlled_substance": false, "criminal_activity": false, "dangerous_activity": false, "category": "AMBIGUOUS"}',
        "LEGAL",
    ])
    guardrail = IntentGuardrail(api=api)
    assert guardrail.classify("Question idiomatique") == "LEGAL"

    api_invalid = SequencedFakeAPI([
        "Réponse non JSON du modèle",
        "ILLEGAL",
    ])
    guardrail_invalid = IntentGuardrail(api=api_invalid)
    assert guardrail_invalid.classify("Requête mal formée") == "ILLEGAL"


def test_evaluate_policies():
    api_safety = SequencedFakeAPI([
        '{"controlled_substance": false, "criminal_activity": true, "dangerous_activity": false, "category": "ILLEGAL"}'
    ])
    guardrail_safety = IntentGuardrail(api=api_safety, policy="safety")
    decision_safety = guardrail_safety.evaluate("Action criminelle")
    assert decision_safety.category == "ILLEGAL"
    assert decision_safety.allowed is False
    assert decision_safety.refusal_message is not None

    api_alibi = SequencedFakeAPI([
        '{"controlled_substance": false, "criminal_activity": false, "dangerous_activity": false, "category": "LEGAL"}'
    ])
    guardrail_alibi = IntentGuardrail(api=api_alibi, policy="alibi")
    decision_alibi = guardrail_alibi.evaluate("Recette de crêpes")
    assert decision_alibi.category == "LEGAL"
    assert decision_alibi.allowed is False
    assert "nulle part" in decision_alibi.refusal_message
