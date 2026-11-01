"""
Mesure des améliorations : chaque amélioration est comparée à sa baseline (le comportement d'avant),
sur le même jeu de référence et avec le même modèle.

Protocole complet et résultats : docs/17-ameliorations-mesurees.md.

Lancement (Ollama doit tourner) :
    PYTHONPATH=. .venv/bin/python -m benchmark.quality
    PYTHONPATH=. .venv/bin/python -m benchmark.quality --experiments description_outils --reps 3

Expériences :
    relance_outils     : sans relance du modèle après un outil (baseline) / avec relance
    memoire_inter_chats: nouveau chat sans archivage (baseline) / avec archivage des chats précédents
    description_outils : outils décrits en signatures complètes (baseline) / noms seulement / aucune liste
"""
import argparse
import json
import statistics
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from src.commands.session import NewCommand
from src.config import PROJECT_ROOT, config

DATASET = PROJECT_ROOT / "benchmark" / "datasets" / "quality.yaml"


# ── Évaluation des réponses ──────────────────────────────────────────

def normalize(text: str) -> str:
    """Minuscules sans accents : « Lyon », « LYON » et « lyon » se valent, comme « Préféré » et « prefere »."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def contains_all(answer: str, expected: list[str]) -> bool:
    text = normalize(answer)
    return bool(text.strip()) and all(normalize(word) in text for word in expected)


def tool_choice_correct(called: list[str], expected: Optional[str]) -> bool:
    """Bon outil appelé, ou aucun outil quand la demande n'en demande pas."""
    return expected in called if expected else not called


# ── Instrumentation ──────────────────────────────────────────────────

class RecordingAPI:
    """Enveloppe le client Ollama et garde les compteurs de chaque génération (taille du prompt, tokens)."""

    def __init__(self, api: Any):
        self._api = api
        self.generations: list[dict] = []

    def stream_ndjson(self, endpoint: str, *args, **kwargs):
        for chunk in self._api.stream_ndjson(endpoint, *args, **kwargs):
            if endpoint == "api/chat" and chunk.get("done"):
                self.generations.append({"prompt_tokens": chunk.get("prompt_eval_count"),
                                         "gen_tokens": chunk.get("eval_count")})
            yield chunk

    def __getattr__(self, name: str) -> Any:
        return getattr(self._api, name)


@dataclass
class Session:
    """Une instance SensAI neuve par cas : aucun souvenir ne passe d'un cas à l'autre."""
    app: Any
    api: RecordingAPI
    tool_calls: list[str] = field(default_factory=list)
    tool_results: list[str] = field(default_factory=list)


def default_app_factory():
    from src.main import SensAI
    return SensAI(db_url="sqlite:///:memory:")


def open_session(app_factory: Callable, email: str = "eval@sensai.test") -> Session:
    app = app_factory()
    recording = RecordingAPI(app.api)
    app.api = app.chat_engine.api = recording
    session = Session(app=app, api=recording)
    # Les outils à effet de bord (email, Telegram...) sont refusés : l'appel est compté, rien n'est envoyé.
    app.chat_engine.confirm_tool = lambda name, arguments: False
    def record(name, arguments, result, ms):
        session.tool_calls.append(name)
        session.tool_results.append(result.message)

    app.chat_engine.on_tool_call = record
    app.load_or_create_profile(email=email, name="Évaluation")
    return session


def timed_chat(session: Session, prompt: str) -> tuple[str, float]:
    start = time.perf_counter()
    answer = session.app.chat(prompt)
    return answer, time.perf_counter() - start


# ── Variantes : comportement d'avant (baseline) et d'après ──────────

def apply_variant(session: Session, experiment: str, variant: str) -> None:
    engine = session.app.chat_engine
    if experiment == "relance_outils":
        engine.max_tool_rounds = 0 if variant == "sans relance" else 3
    elif experiment == "description_outils":
        config.TOOLS_LISTING = {"signatures complètes": "full", "noms seulement": "names", "aucune liste": "none"}[variant]


EXPERIMENTS: dict[str, dict[str, Any]] = {
    "relance_outils": {
        "cases": "tool_answer",
        "variants": ["sans relance", "avec relance"],
        "baseline": "sans relance",
        "metric": "Réponse qui reprend le résultat renvoyé par l'outil (ex : « Selftest OK: kiwi »)",
    },
    "memoire_inter_chats": {
        "cases": "memory",
        "variants": ["sans archivage", "avec archivage"],
        "baseline": "sans archivage",
        "metric": "Fait d'un chat précédent retrouvé dans un nouveau chat",
    },
    "description_outils": {
        "cases": "tool_choice",
        "variants": ["signatures complètes", "noms seulement", "aucune liste"],
        "baseline": "signatures complètes",
        "metric": "Bon outil appelé (ou aucun quand il n'en faut pas)",
    },
}


def run_case(experiment: str, variant: str, case: dict, app_factory: Callable) -> dict:
    session = open_session(app_factory)
    apply_variant(session, experiment, variant)
    result: dict[str, Any] = {"experiment": experiment, "variant": variant}

    if experiment == "memoire_inter_chats":
        timed_chat(session, case["fact"])
        if variant == "avec archivage":
            NewCommand().execute(session.app, "")
        else:
            app = session.app
            app.context = app.session_manager.create_new_context(app.session, profile_id=app.profile.id)
        first_generation = len(session.api.generations)
        answer, seconds = timed_chat(session, case["question"])
        result.update(case=case["question"], expected=case["expected"], answer=answer,
                      success=contains_all(answer, case["expected"]))
        generations = session.api.generations[first_generation:]
    else:
        answer, seconds = timed_chat(session, case["prompt"])
        generations = session.api.generations
        result.update(case=case["prompt"], expected=case["expected"], answer=answer, tools=list(session.tool_calls))
        if experiment == "relance_outils":
            # La réponse doit reprendre le résultat renvoyé par l'outil (ex : "Selftest OK: kiwi"),
            # pas seulement le mot : recopier l'appel {"message": "kiwi"} ne compte pas.
            returned = [msg for msg in session.tool_results if case["expected"] in normalize(msg)]
            result["success"] = bool(returned) and contains_all(answer, [returned[0]])
            result["tool_called"] = "tools_selftest" in session.tool_calls
        else:
            result["success"] = tool_choice_correct(session.tool_calls, case["expected"])

    result["seconds"] = round(seconds, 2)
    result["prompt_tokens"] = generations[0]["prompt_tokens"] if generations else None
    result["generations"] = len(generations)
    return result


def run(experiments: list[str], dataset: dict, reps: int, app_factory: Callable = default_app_factory,
        log: Callable[[str], None] = print) -> list[dict]:
    """Lance chaque variante de chaque expérience sur ses cas, avec des paramètres de génération fixes."""
    saved_generation = config.generation_options("chat")
    saved_listing = config.TOOLS_LISTING
    # Température 0 et graine fixe : deux variantes ne diffèrent que par le changement mesuré
    config.set_generation("chat", "temperature", 0.0)
    config.set_generation("chat", "seed", 42)
    rows: list[dict] = []
    try:
        for experiment in experiments:
            spec = EXPERIMENTS[experiment]
            for variant in spec["variants"]:
                log(f"== {experiment} | {variant}")
                for rep in range(1, reps + 1):
                    for case in dataset[spec["cases"]]:
                        row = run_case(experiment, variant, case, app_factory)
                        row["rep"] = rep
                        rows.append(row)
                        mark = "OK " if row["success"] else "NON"
                        log(f"   [{mark}] {row['case'][:60]} -> {row.get('tools', '')} {row['answer'][:60]!r}")
                config.TOOLS_LISTING = saved_listing
    finally:
        config.GENERATION["chat"] = saved_generation
        config.TOOLS_LISTING = saved_listing
    return rows


# ── Rapport ──────────────────────────────────────────────────────────

def summarize_variant(rows: list[dict]) -> dict[str, Any]:
    tokens = [r["prompt_tokens"] for r in rows if r["prompt_tokens"] is not None]
    return {
        "success": sum(r["success"] for r in rows),
        "total": len(rows),
        "rate": round(100 * sum(r["success"] for r in rows) / len(rows), 1) if rows else 0.0,
        "prompt_tokens": round(statistics.mean(tokens)) if tokens else None,
        "seconds": round(statistics.mean(r["seconds"] for r in rows), 2) if rows else None,
    }


def build_report(rows: list[dict], model: str, reps: int) -> str:
    lines = [f"# Améliorations mesurées : résultats du {datetime.now():%Y-%m-%d %H:%M}", "",
             "Protocole et analyse : [docs/17-ameliorations-mesurees.md](../../docs/17-ameliorations-mesurees.md).", "",
             f"- Modèle : {model}", f"- Répétitions : {reps}, température 0, graine 42", ""]
    for experiment, spec in EXPERIMENTS.items():
        exp_rows = [r for r in rows if r["experiment"] == experiment]
        if not exp_rows:
            continue
        lines += [f"## {experiment}", "", f"Mesure : {spec['metric']}.", "",
                  "| Variante | Réussite | Taux | Prompt moyen (tokens) | Durée moyenne (s) | Écart au baseline |",
                  "|----------|----------|------|-----------------------|-------------------|-------------------|"]
        baseline = summarize_variant([r for r in exp_rows if r["variant"] == spec["baseline"]])
        for variant in spec["variants"]:
            s = summarize_variant([r for r in exp_rows if r["variant"] == variant])
            delta = "baseline" if variant == spec["baseline"] else f"{s['rate'] - baseline['rate']:+.1f} points"
            lines.append(f"| {variant} | {s['success']}/{s['total']} | {s['rate']} % | {s['prompt_tokens']} | "
                         f"{s['seconds']} | {delta} |")
        lines += ["", "Détail par cas :", "", "| Variante | Cas | Attendu | Outils appelés | Réussite | Réponse (début) |",
                  "|----------|-----|---------|----------------|----------|-----------------|"]
        for r in exp_rows:
            answer = " ".join((r["answer"] or "").split())[:70].replace("|", "/")
            lines.append(f"| {r['variant']} | {r['case']} | {r['expected']} | {', '.join(r.get('tools', [])) or '-'} | "
                         f"{'oui' if r['success'] else 'non'} | {answer or '(vide)'} |")
        lines.append("")
    return "\n".join(lines)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mesure des améliorations de SensAI contre leur baseline.")
    parser.add_argument("--experiments", nargs="+", choices=list(EXPERIMENTS), default=list(EXPERIMENTS))
    parser.add_argument("--reps", type=int, default=3,
                        help="Répétitions de chaque cas (les résultats varient un peu, même à température 0).")
    parser.add_argument("--model", help="Modèle à évaluer (défaut : celui de la config).")
    parser.add_argument("--dataset", default=str(DATASET))
    parser.add_argument("--out", default=str(PROJECT_ROOT / "benchmark" / "results"))
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    if args.model:
        config.apply_overrides(DEFAULT_MODEL=args.model)
    dataset = yaml.safe_load(Path(args.dataset).read_text(encoding="utf-8"))
    rows = run(args.experiments, dataset, args.reps)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    (out / f"{stamp}_quality.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    report = out / f"{stamp}_quality.md"
    report.write_text(build_report(rows, config.DEFAULT_MODEL, args.reps), encoding="utf-8")
    print(f"\nRapport : {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
