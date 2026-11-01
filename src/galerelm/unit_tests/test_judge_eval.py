import json

import pytest

from benchmark import judge as judge_bench
from src.galerelm.graph import HallucinationGrade, HallucinationGrader
from src.galerelm.models import InteractionLog
from src.main import SensAI


class JudgeOllama:
    """Faux modèle juge : renvoie le texte fourni."""
    base_url = "http://fake"

    def __init__(self, output=None, fail=False):
        self.output = output
        self.fail = fail

    def stream_ndjson(self, endpoint, json_data=None, **kwargs):
        if self.fail:
            raise RuntimeError("juge injoignable")
        yield {"message": {"role": "assistant", "content": self.output}, "done": True, "model": "j"}


def test_judge_returns_scores_and_unsupported_claims():
    output = json.dumps({"grounded": False, "relevance": 4, "coherence": 7, "faithfulness": "2",
                         "unsupported_claims": ["Le prix est de 199 euros"], "critique": "Prix inventé."})
    grade = HallucinationGrader(api=JudgeOllama(output), model="j").grade("Prix ?", "199 euros.", facts=["Fiche"])
    assert (grade.grounded, grade.verified) == (False, True)
    assert grade.scores() == {"relevance": 4.0, "coherence": 5.0, "faithfulness": 2.0}   # 7 ramené à 5
    assert grade.unsupported_claims == ["Le prix est de 199 euros"]


@pytest.mark.parametrize("api", [JudgeOllama("pas du JSON"), JudgeOllama(fail=True)])
def test_judge_failure_is_marked_unverified_not_silently_accepted(api):
    grade = HallucinationGrader(api=api, model="j").grade("Q ?", "Réponse.", facts=[])
    assert grade.grounded is True and grade.verified is False


class FixedJudge:
    def __init__(self, grade):
        self.grade_value = grade

    def grade(self, user_input, candidate, facts=None):
        return self.grade_value


class AnswerOllama:
    base_url = "http://fake"

    def stream_ndjson(self, endpoint, json_data=None, **kwargs):
        yield {"message": {"role": "assistant", "content": "Le prix est de 199 euros."}, "done": True, "model": "m"}

    def post(self, endpoint, json=None, **kwargs):
        inputs = json["input"]
        return {"embeddings": [[1.0, 0.0]] * (1 if isinstance(inputs, str) else len(inputs))}


def make_app(grade):
    app = SensAI(db_url="sqlite:///:memory:")
    app.api = app.chat_engine.api = AnswerOllama()
    app.chat_engine.hallucination_grader = FixedJudge(grade)
    app.chat_engine.max_hallucination_retries = 0
    app.load_or_create_profile(email="ev1@test.com", name="Ev1")
    return app


def test_unsupported_claims_are_flagged_to_the_user_and_scores_logged():
    app = make_app(HallucinationGrade(grounded=False, relevance=4, coherence=5, faithfulness=1,
                                      unsupported_claims=["Le prix est de 199 euros"]))
    reply = app.chat("Quel est le prix ?")
    assert reply.startswith("Le prix est de 199 euros.")
    assert "[Vérification] Affirmations non appuyées par les sources : Le prix est de 199 euros" in reply
    row = app.session.query(InteractionLog).one()
    assert (row.eval_relevance, row.eval_coherence, row.eval_faithfulness, row.eval_grounded, row.eval_verified) == (4, 5, 1, False, True)


def test_unverified_answer_is_flagged():
    reply = make_app(HallucinationGrade(grounded=True, verified=False)).chat("Quel est le prix ?")
    assert "n'a pas pu être vérifiée par le juge" in reply


def test_grounded_answer_has_no_note():
    reply = make_app(HallucinationGrade(grounded=True, relevance=5, coherence=5, faithfulness=5)).chat("Quel est le prix ?")
    assert reply == "Le prix est de 199 euros."


# ── Script d'évaluation : comparaison de versions ────────────────────

class DocAwareOllama(AnswerOllama):
    """Faux modèle : cite le document s'il est dans le prompt, sinon invente."""

    def stream_ndjson(self, endpoint, json_data=None, **kwargs):
        system = json_data["messages"][0]["content"]
        text = "D'après le document : 31 heures." if "31 heures" in system else "Environ 10 heures, je crois."
        yield {"message": {"role": "assistant", "content": text}, "done": True, "model": "m"}


class KeywordJudge:
    """Faux juge : fidèle si la réponse reprend le chiffre du document."""

    def grade(self, user_input, candidate, facts=None):
        ok = "31 heures" in candidate
        return HallucinationGrade(grounded=ok, relevance=5, coherence=5, faithfulness=5 if ok else 1,
                                  unsupported_claims=[] if ok else [candidate])


def doc_app_factory(model):
    app = SensAI(db_url="sqlite:///:memory:", model=model)
    app.api = app.chat_engine.api = DocAwareOllama()
    return app


DATASET = {"cases": [{"id": "produit", "document": "Kestrel 3 : autonomie de 31 heures.",
                      "question": "Quelle est l'autonomie du Kestrel 3 ?", "answerable": True}]}


def test_judge_benchmark_compares_versions():
    rows = judge_bench.run(DATASET, ["m"], "j", list(judge_bench.VARIANTS), app_factory=doc_app_factory,
                           judge=KeywordJudge(), log=lambda *_: None)
    by_variant = {r["variant"]: r for r in rows}
    assert by_variant["sans documents"]["faithfulness"] == 1 and not by_variant["sans documents"]["grounded"]
    assert by_variant["avec documents"]["faithfulness"] == 5 and by_variant["avec documents"]["grounded"]

    report = judge_bench.build_report(rows, "j")
    assert "| m | sans documents | 5 | 5 | 1 | 0 % | 0 / 1 | 1 |" in report
    assert "| m | avec documents | 5 | 5 | 5 | 100 % | 0 / 1 | 0 |" in report


def test_summary_ignores_unverified_answers_in_scores():
    rows = [{"verified": True, "grounded": True, "relevance": 4, "coherence": 4, "faithfulness": 4, "unsupported_claims": []},
            {"verified": False, "grounded": True, "relevance": None, "coherence": None, "faithfulness": None, "unsupported_claims": []}]
    summary = judge_bench.summarize(rows)
    assert summary["unverified"] == 1 and summary["faithfulness"] == 4 and summary["grounded_rate"] == 100.0
