import argparse
import subprocess

from benchmark import resources
from benchmark.resources import (
    build_report,
    gpu_memory_used_mb,
    metrics_from_chunk,
    model_memory,
    ollama_rss_mb,
    run_benchmark,
    summarize,
    timed_chat,
)


def test_metrics_from_ollama_counters():
    chunk = {
        "done": True,
        "load_duration": 2_500_000_000,
        "prompt_eval_count": 1500, "prompt_eval_duration": 500_000_000,
        "eval_count": 128, "eval_duration": 1_600_000_000,
    }
    m = metrics_from_chunk(chunk, ttft_s=0.61234, total_s=2.5)
    assert m == {"load_s": 2.5, "ttft_s": 0.612, "answer_ttft_s": None, "thinking_chunks": 0, "total_s": 2.5,
                 "prompt_tokens": 1500, "prompt_tps": 3000.0, "gen_tokens": 128, "gen_tps": 80.0}


def test_metrics_tolerate_missing_counters():
    m = metrics_from_chunk({}, ttft_s=None, total_s=1.0)
    assert m["prompt_tps"] is None and m["gen_tps"] is None and m["ttft_s"] is None


def test_summarize_ignores_missing_values():
    assert summarize([3, None, 1, 2]) == {"mean": 2, "median": 2, "min": 1, "max": 3}
    assert summarize([None]) == {"mean": None, "median": None, "min": None, "max": None}


def test_model_memory_reports_gpu_share():
    ps = {"models": [{"name": "qwen:latest", "size": 2 * 2**30, "size_vram": 2**30}]}
    assert model_memory(ps, "qwen") == {"model_size_mb": 2048, "model_vram_mb": 1024, "gpu_share_pct": 50.0}
    assert model_memory({"models": []}, "qwen")["gpu_share_pct"] is None


def test_ollama_rss_sums_only_ollama_processes(tmp_path):
    for pid, name, rss in (("10", "ollama", 1024), ("11", "llama-server", 2048), ("12", "python3", 4096)):
        (tmp_path / pid).mkdir()
        (tmp_path / pid / "status").write_text(f"Name:\t{name}\nVmRSS:\t{rss} kB\n")
    assert ollama_rss_mb(tmp_path) == 3
    assert ollama_rss_mb(tmp_path / "vide") is None


def test_gpu_memory_handles_missing_nvidia_smi():
    def missing(*args, **kwargs):
        raise FileNotFoundError

    assert gpu_memory_used_mb(run=missing) is None
    ok = lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="1234\n")
    assert gpu_memory_used_mb(run=ok) == 1234.0


class FakeOllama:
    """Faux Ollama : génère 3 morceaux puis des compteurs fixes, et mémorise les requêtes."""
    base_url = "http://fake"

    def __init__(self):
        self.chat_payloads = []
        self.loaded = set()

    def stream_ndjson(self, endpoint, json_data=None, **kwargs):
        self.chat_payloads.append(json_data)
        self.loaded.add(json_data["model"])
        yield {"message": {"content": ""}, "done": False}
        if json_data.get("think") is not False:
            yield {"message": {"content": "", "thinking": "Je réfléchis"}, "done": False}
        yield {"message": {"content": "Bonjour"}, "done": False}
        yield {"done": True, "load_duration": 1e9, "prompt_eval_count": 10, "prompt_eval_duration": 1e8,
               "eval_count": 20, "eval_duration": 4e8}

    def post(self, endpoint, json=None, **kwargs):
        if endpoint == "api/generate" and json.get("keep_alive") == 0:
            self.loaded.discard(json["model"])
        return {}

    def get(self, endpoint, **kwargs):
        if endpoint == "api/ps":
            return {"models": [{"name": m, "size": 100 * 2**20, "size_vram": 100 * 2**20} for m in self.loaded]}
        return {}


def test_timed_chat_separates_thinking_from_visible_answer():
    ticks = iter([0.0, 0.25, 0.75, 1.0])
    m = timed_chat(FakeOllama(), "m", "salut", {"num_ctx": 2048}, clock=lambda: next(ticks))
    assert m["ttft_s"] == 0.25         # premier token généré : la réflexion (le morceau vide ne compte pas)
    assert m["answer_ttft_s"] == 0.75  # premier token de la réponse visible
    assert m["thinking_chunks"] == 1
    assert m["total_s"] == 1.0
    assert m["gen_tps"] == 50.0


def test_benchmark_thinking_compares_default_and_disabled():
    fake = FakeOllama()
    rows = resources.benchmark_thinking(fake, "m", reps=2, log=lambda *_: None)
    assert [r["thinking"] for r in rows] == ["par défaut"] * 2 + ["désactivée"] * 2
    assert all(r["thinking_chunks"] == 1 for r in rows[:2]) and all(r["thinking_chunks"] == 0 for r in rows[2:])
    assert [p.get("think") for p in fake.chat_payloads].count(False) == 3   # chauffe + 2 mesures


def test_run_benchmark_protocol(monkeypatch):
    monkeypatch.setattr(resources, "gpu_memory_used_mb", lambda: 500.0)
    monkeypatch.setattr(resources, "ollama_rss_mb", lambda: 800)
    fake = FakeOllama()

    rows = run_benchmark(fake, ["m"], ["gpu", "cpu"], [2048], reps=2, num_predict=64, log=lambda *_: None)

    # Par configuration : 1 démarrage à froid + 2 mesures "court" + 2 mesures "long" (la chauffe "long" est écartée)
    assert len(rows) == 2 * 5
    assert sum(r["cold_start"] for r in rows) == 2
    cpu_options = [p["options"] for p in fake.chat_payloads if p["options"].get("num_gpu") == 0]
    assert cpu_options and all(o["num_ctx"] == 2048 and o["num_predict"] == 64 for o in cpu_options)
    prompts = [p["messages"][0]["content"] for p in fake.chat_payloads]
    assert len(set(prompts)) == len(prompts)   # préfixe unique : pas de cache de prompt entre mesures
    assert fake.loaded == set()                # modèle déchargé à la fin


def test_report_contains_every_section():
    rows = [
        {"model": "m", "backend": "gpu", "num_ctx": 2048, "prompt": "court", "run": 0, "cold_start": True,
         "load_s": 2.0, "ttft_s": 2.1, "answer_ttft_s": 2.5, "thinking_chunks": 0, "total_s": 3.0, "prompt_tokens": 10, "prompt_tps": 100.0, "gen_tokens": 20,
         "gen_tps": 50.0, "ram_ollama_mb": 800, "vram_used_mb": 1200, "model_size_mb": 1500, "model_vram_mb": 1500,
         "gpu_share_pct": 100.0},
        {"model": "m", "backend": "gpu", "num_ctx": 2048, "prompt": "court", "run": 1, "cold_start": False,
         "load_s": 0.0, "ttft_s": 0.1, "answer_ttft_s": 0.2, "thinking_chunks": 0, "total_s": 0.5, "prompt_tokens": 10, "prompt_tps": 120.0, "gen_tokens": 20,
         "gen_tps": 60.0, "ram_ollama_mb": 800, "vram_used_mb": 1200, "model_size_mb": 1500, "model_vram_mb": 1500,
         "gpu_share_pct": 100.0},
    ]
    embed = [{"model": "e", "batch": "1 texte", "run": 1, "total_s": 0.05}]
    args = argparse.Namespace(models=["m"], backends=["gpu"], num_ctx=[2048], reps=1, num_predict=128)
    thinking = [{"model": "m", "thinking": "par défaut", "run": 1, "answer_ttft_s": 2.0, "thinking_chunks": 300, "total_s": 3.0}]
    report = build_report(rows, embed, {"cpu": "test"}, args, thinking)
    for section in ("## Machine", "## Démarrage à froid", "## Vitesse à chaud", "## Mémoire", "## Réflexion", "## Embeddings"):
        assert section in report
    assert "| m | gpu | 2048 | court | 120 (120-120) | 60 (60-60) |" in report
