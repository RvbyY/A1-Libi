"""
Évaluation automatique par un LLM juge (EV1) : note les réponses de SensAI et compare des versions du système.

Chaque cas du jeu (benchmark/datasets/judge.yaml) fournit un document de référence et une question.
SensAI répond ; le juge note la réponse par rapport au document : pertinence, cohérence, fidélité (0 à 5),
affirmations non appuyées, et réponse ancrée ou non. Les scores moyens permettent de comparer des versions.

Lancement (Ollama doit tourner) :
    PYTHONPATH=. .venv/bin/python -m benchmark.judge
    PYTHONPATH=. .venv/bin/python -m benchmark.judge --models modele-a modele-b --judge-model modele-juge

Versions comparées par défaut :
    sans documents : SensAI répond sans le document (connaissances du modèle seules)
    avec documents : le document est ingéré (R1) et ses extraits sont injectés dans le prompt
"""
import argparse
import json
import statistics
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from src.config import PROJECT_ROOT, config
from src.galerelm.graph import HallucinationGrader

DATASET = PROJECT_ROOT / "benchmark" / "datasets" / "judge.yaml"
VARIANTS = ("sans documents", "avec documents")
SCORES = ("relevance", "coherence", "faithfulness")


def default_app_factory(model: str):
    from src.main import SensAI
    return SensAI(db_url="sqlite:///:memory:", model=model)


def evaluate_case(case: dict, variant: str, model: str, judge: Any, app_factory: Callable, workdir: Path) -> dict:
    app = app_factory(model)
    app.chat_engine.confirm_tool = lambda name, arguments: False
    app.load_or_create_profile(email="judge@sensai.test", name="Évaluation")
    if variant == "avec documents":
        source = workdir / f"{case['id']}.md"
        source.write_text(case["document"], encoding="utf-8")
        app.chat_engine.documents.ingest(app.session, app.profile.id, str(source), api_client=app.api)
    answer = app.chat(case["question"])
    # Le juge reçoit toujours le document de référence : il note la fidélité de la réponse à la vérité du cas
    grade = judge.grade(case["question"], answer, facts=[case["document"]])
    return {
        "case": case["id"], "variant": variant, "model": model, "answerable": case.get("answerable", True),
        "question": case["question"], "answer": answer,
        "grounded": grade.grounded, "verified": grade.verified,
        **grade.scores(),
        "unsupported_claims": grade.unsupported_claims, "critique": grade.critique,
    }


def run(dataset: dict, models: list[str], judge_model: str, variants: list[str], reps: int = 1,
        app_factory: Callable = default_app_factory, judge: Any = None, log: Callable[[str], None] = print) -> list[dict]:
    saved = config.generation_options("chat")
    config.set_generation("chat", "temperature", 0.0)
    config.set_generation("chat", "seed", 42)
    rows: list[dict] = []
    if judge is None:
        from src.rapideAPI.client import RapideAPI
        judge = HallucinationGrader(api=RapideAPI(base_url=config.OLLAMA_HOST, timeout=config.OLLAMA_TIMEOUT), model=judge_model)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for model in models:
                for variant in variants:
                    log(f"== {model} | {variant}")
                    for _ in range(reps):
                        for case in dataset["cases"]:
                            row = evaluate_case(case, variant, model, judge, app_factory, Path(tmp))
                            rows.append(row)
                            log(f"   {case['id']:<14} ancrée={row['grounded']!s:<5} pertinence={row['relevance']} "
                                f"cohérence={row['coherence']} fidélité={row['faithfulness']}")
    finally:
        config.GENERATION["chat"] = saved
    return rows


def summarize(rows: list[dict]) -> dict[str, Any]:
    verified = [r for r in rows if r["verified"]]
    summary = {"cases": len(rows), "unverified": len(rows) - len(verified),
               "grounded_rate": round(100 * sum(r["grounded"] for r in verified) / len(verified), 1) if verified else None,
               "flagged_claims": sum(len(r["unsupported_claims"]) for r in rows)}
    for score in SCORES:
        values = [r[score] for r in verified if r[score] is not None]
        summary[score] = round(statistics.mean(values), 2) if values else None
    return summary


def build_report(rows: list[dict], judge_model: str) -> str:
    def fmt(value):
        return "-" if value is None else f"{value:g}"

    lines = [f"# Évaluation par le juge : résultats du {datetime.now():%Y-%m-%d %H:%M}", "",
             "Protocole et analyse : [docs/18-evaluation-juge.md](../../docs/18-evaluation-juge.md).", "",
             f"- Juge : {judge_model} (température 0)", "- Scores de 0 à 5, moyennes sur les réponses vérifiées", "",
             "## Comparaison des versions", "",
             "| Modèle | Version | Pertinence | Cohérence | Fidélité | Réponses ancrées | Non vérifiées | Affirmations signalées |",
             "|--------|---------|------------|-----------|----------|------------------|---------------|------------------------|"]
    for model in dict.fromkeys(r["model"] for r in rows):
        for variant in dict.fromkeys(r["variant"] for r in rows):
            group = [r for r in rows if r["model"] == model and r["variant"] == variant]
            if not group:
                continue
            s = summarize(group)
            lines.append(f"| {model} | {variant} | {fmt(s['relevance'])} | {fmt(s['coherence'])} | {fmt(s['faithfulness'])} | "
                         f"{fmt(s['grounded_rate'])} % | {s['unverified']} / {s['cases']} | {s['flagged_claims']} |")
    lines += ["", "## Détail par cas", "",
              "| Modèle | Version | Cas | Réponse dans le document | Ancrée | Pertinence | Cohérence | Fidélité | Affirmations signalées | Réponse (début) |",
              "|--------|---------|-----|--------------------------|--------|------------|-----------|----------|------------------------|-----------------|"]
    for r in rows:
        answer = " ".join((r["answer"] or "").split())[:80].replace("|", "/")
        claims = "; ".join(r["unsupported_claims"])[:80].replace("|", "/") or "-"
        grounded = "non vérifiée" if not r["verified"] else ("oui" if r["grounded"] else "non")
        lines.append(f"| {r['model']} | {r['variant']} | {r['case']} | {'oui' if r['answerable'] else 'non'} | {grounded} | "
                     f"{fmt(r['relevance'])} | {fmt(r['coherence'])} | {fmt(r['faithfulness'])} | {claims} | {answer} |")
    return "\n".join(lines) + "\n"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Évaluation de SensAI par un LLM juge (EV1).")
    parser.add_argument("--models", nargs="+", default=[config.DEFAULT_MODEL], help="Modèles de SensAI à comparer.")
    parser.add_argument("--judge-model", default=config.DEFAULT_MODEL, help="Modèle utilisé comme juge.")
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--dataset", default=str(DATASET))
    parser.add_argument("--out", default=str(PROJECT_ROOT / "benchmark" / "results"))
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    dataset = yaml.safe_load(Path(args.dataset).read_text(encoding="utf-8"))
    rows = run(dataset, args.models, args.judge_model, args.variants, args.reps)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    (out / f"{stamp}_judge.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    report = out / f"{stamp}_judge.md"
    report.write_text(build_report(rows, args.judge_model), encoding="utf-8")
    print(f"\nRapport : {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
