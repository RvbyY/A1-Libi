import pytest
from src.galerelm.graph import (
    END,
    AntiHallucinationWorkflow,
    HallucinationGrader,
    StateGraph,
)
from src.galerelm.models import LongTermMemory
from src.main import SensAI
from src.webapp.visualizer import PipelineVisualizer


class SequencedStreamAPI:
    """
    Simule une séquence de flux NDJSON et d'embeddings pour tester le graphe
    de nœuds et la boucle de régénération anti-hallucination.
    """

    def __init__(self, stream_outputs: list[str]):
        self.stream_outputs = list(stream_outputs)
        self.captured_payloads: list[dict] = []

    def stream_ndjson(self, endpoint: str, data=None, json_data=None, **kwargs):
        if json_data:
            self.captured_payloads.append(json_data)
        text = self.stream_outputs.pop(0) if self.stream_outputs else ""
        yield {
            "message": {"role": "assistant", "content": text},
            "done": True,
            "model": "llama3.2",
            "eval_count": 6,
            "eval_duration": 100000,
        }

    def post(self, endpoint: str, data=None, json=None, **kwargs):
        if endpoint == "api/embed":
            return {"embeddings": [[1.0, 0.0]]}
        return {}


def test_custom_state_graph_execution():
    graph = StateGraph()
    graph.add_node("step_a", lambda s: {"count": s.get("count", 0) + 1})
    graph.add_node("step_b", lambda s: {"count": s["count"] * 10})

    graph.set_entry_point("step_a")
    graph.add_conditional_edges(
        "step_a",
        lambda s: "repeat" if s["count"] < 2 else "next",
        {"repeat": "step_a", "next": "step_b"},
    )
    graph.add_edge("step_b", END)

    compiled = graph.compile()
    result = compiled.invoke({"count": 0})
    assert result["count"] == 20
    assert result["execution_trace"] == ["step_a", "step_a", "step_b"]


def test_hallucination_grader_detects_ungrounded_claim():
    api = SequencedStreamAPI([
        '{"grounded": false, "critique": "L\'utilisateur habite à Lyon, pas à Marseille."}'
    ])
    grader = HallucinationGrader(api=api)
    grade = grader.grade(
        user_input="Où j'habite ?",
        candidate="Tu habites à Marseille.",
        facts=["[user] J'habite à Lyon"],
    )
    assert grade.grounded is False
    assert "Lyon" in grade.critique


def test_anti_hallucination_workflow_regenerates_on_hallucination():
    # Séquence d'appels :
    # 1. generate (essai 1) -> répond "Tu habites à Marseille." (hallucination)
    # 2. grade (essai 1) -> retourne grounded=false + critique
    # 3. generate (essai 2, après rebouclage) -> répond "Tu habites à Lyon."
    # 4. grade (essai 2) -> retourne grounded=true
    fake_api = SequencedStreamAPI([
        "Tu habites à Marseille.",
        '{"grounded": false, "critique": "Le souvenir indique Lyon et non Marseille."}',
        "Tu habites à Lyon.",
        '{"grounded": true, "critique": ""}',
    ])

    app = SensAI(db_url="sqlite:///:memory:", use_anti_hallucination=True)
    app.api = fake_api
    app.chat_engine.api = fake_api
    app.chat_engine.hallucination_grader.api = fake_api
    app.load_or_create_profile(email="graph@test.com", name="GraphUser")

    app.profile.deep_context.memories.append(
        LongTermMemory(role="user", content="J'habite à Lyon", embedding=[1.0, 0.0])
    )
    app.session.commit()

    final_reply = app.chat("Où est-ce que j'habite ?")
    assert final_reply == "Tu habites à Lyon."

    state = app.chat_engine.last_graph_state
    assert state is not None
    assert state["execution_trace"] == ["retrieve", "generate", "grade", "generate", "grade"]
    assert state["retries"] == 2
    assert state["grounded"] is True

    # Vérifie que la critique a bien été injectée dans le prompt système du 2e appel generate
    second_generate_payload = fake_api.captured_payloads[2]
    sys_msg = second_generate_payload["messages"][0]["content"]
    assert "CORRECTION ANTI-HALLUCINATION REQUISE" in sys_msg
    assert "Lyon" in sys_msg


def test_pipeline_visualizer_tracks_realtime_events():
    viz = PipelineVisualizer()
    fake_api = SequencedStreamAPI([
        "Tu habites à Lyon.",
        '{"grounded": true, "critique": ""}',
    ])

    app = SensAI(db_url="sqlite:///:memory:", use_anti_hallucination=True)
    app.api = fake_api
    app.chat_engine.api = fake_api
    app.chat_engine.hallucination_grader.api = fake_api
    app.chat_engine.on_event = viz.mark
    app.load_or_create_profile(email="viz@test.com", name="VizUser")

    app.chat("Où j'habite ?")

    assert viz.nodes["input"].state == "success"
    assert viz.nodes["retrieve"].state == "success"
    assert viz.nodes["generate"].state == "success"
    assert viz.nodes["grade"].state == "success"
    assert viz.nodes["persist"].state == "success"
    html_out = viz.render_html()
    assert "<svg" in html_out
    assert "HallucinationGrader" in html_out
