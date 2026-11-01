"""
Benchmark des ressources locales : vitesse, latence et mémoire d'un modèle servi par Ollama.

Protocole complet et lecture des résultats : docs/16-benchmark-ressources.md.

Lancement (Ollama doit tourner) :
    PYTHONPATH=. .venv/bin/python -m benchmark.resources
    PYTHONPATH=. .venv/bin/python -m benchmark.resources --models llama3.2 --num-ctx 2048 4096 --reps 5

Pour chaque combinaison (modèle, exécution GPU ou CPU, taille de contexte) :
    1. le modèle est déchargé, puis rechargé : on mesure le démarrage à froid ;
    2. chaque prompt est envoyé une fois pour chauffer, puis --reps fois pour la mesure ;
    3. la mémoire (RAM du processus Ollama, VRAM, part du modèle sur le GPU) est relevée une fois le modèle chargé.
Les durées viennent des compteurs renvoyés par Ollama (en nanosecondes), le temps avant le premier
token et la latence totale sont mesurés côté client.
"""
import argparse
import csv
import json
import os
import platform
import statistics
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from src.config import PROJECT_ROOT, config
from src.rapideAPI.client import RapideAPI

NS = 1e9

# Paragraphe neutre répété pour construire un prompt long (lecture de contexte)
FILLER = (
    "La gestion de projet logiciel repose sur des itérations courtes, des revues de code régulières "
    "et des tests automatisés qui détectent les régressions avant la mise en production. "
    "Chaque équipe documente ses choix techniques pour que les nouveaux arrivants comprennent l'architecture. "
)

PROMPTS: dict[str, str] = {
    # Question courte : mesure surtout la génération
    "court": "Explique en quelques phrases ce qu'est une base de données relationnelle.",
    # Environ 1 500 tokens de contexte : mesure surtout la lecture du prompt
    "long": FILLER * 30 + "\nRésume le texte ci-dessus en trois phrases.",
}

# Processus d'Ollama : le serveur, et le moteur qui exécute le modèle (llama-server selon les versions)
OLLAMA_PROCESS_NAMES = ("ollama", "llama-server", "ollama_llama_se")

CSV_FIELDS = [
    "model", "backend", "num_ctx", "prompt", "run", "cold_start",
    "load_s", "ttft_s", "answer_ttft_s", "thinking_chunks", "total_s", "prompt_tokens", "prompt_tps", "gen_tokens", "gen_tps",
    "ram_ollama_mb", "vram_used_mb", "model_size_mb", "model_vram_mb", "gpu_share_pct",
]


# ── Mesures ──────────────────────────────────────────────────────────

def metrics_from_chunk(chunk: dict, ttft_s: Optional[float], total_s: float,
                       answer_ttft_s: Optional[float] = None, thinking_chunks: int = 0) -> dict[str, Any]:
    """
    Convertit le dernier chunk d'Ollama (durées en ns) en métriques lisibles.
    ttft_s : premier token généré (réflexion ou réponse) ; answer_ttft_s : premier token de la réponse visible.
    """
    prompt_tokens = chunk.get("prompt_eval_count") or 0
    prompt_ns = chunk.get("prompt_eval_duration") or 0
    gen_tokens = chunk.get("eval_count") or 0
    gen_ns = chunk.get("eval_duration") or 0
    return {
        "load_s": round((chunk.get("load_duration") or 0) / NS, 3),
        "ttft_s": round(ttft_s, 3) if ttft_s is not None else None,
        "answer_ttft_s": round(answer_ttft_s, 3) if answer_ttft_s is not None else None,
        "thinking_chunks": thinking_chunks,
        "total_s": round(total_s, 3),
        "prompt_tokens": prompt_tokens,
        "prompt_tps": round(prompt_tokens / (prompt_ns / NS), 1) if prompt_ns else None,
        "gen_tokens": gen_tokens,
        "gen_tps": round(gen_tokens / (gen_ns / NS), 1) if gen_ns else None,
    }


def summarize(values: Iterable[Optional[float]]) -> dict[str, Optional[float]]:
    """Moyenne, médiane, minimum et maximum (les valeurs absentes sont ignorées)."""
    data = [v for v in values if v is not None]
    if not data:
        return {"mean": None, "median": None, "min": None, "max": None}
    return {
        "mean": round(statistics.mean(data), 2),
        "median": round(statistics.median(data), 2),
        "min": round(min(data), 2),
        "max": round(max(data), 2),
    }


def model_memory(ps: dict, model: str) -> dict[str, Optional[float]]:
    """Taille du modèle chargé et part en VRAM, d'après GET /api/ps."""
    for entry in ps.get("models", []):
        if entry.get("name") == model or entry.get("model") == model or entry.get("name", "").split(":")[0] == model:
            size = entry.get("size") or 0
            vram = entry.get("size_vram") or 0
            return {
                "model_size_mb": round(size / 2**20),
                "model_vram_mb": round(vram / 2**20),
                "gpu_share_pct": round(100 * vram / size, 1) if size else None,
            }
    return {"model_size_mb": None, "model_vram_mb": None, "gpu_share_pct": None}


def ollama_rss_mb(proc: Path = Path("/proc")) -> Optional[float]:
    """Mémoire résidente (RSS) cumulée des processus Ollama (serveur + runner), Linux uniquement."""
    total_kb = 0
    found = False
    for status in proc.glob("[0-9]*/status"):
        try:
            text = status.read_text()
        except OSError:
            continue
        name = next((line.split()[1] for line in text.splitlines() if line.startswith("Name:")), "")
        if name not in OLLAMA_PROCESS_NAMES:
            continue
        rss = next((line.split()[1] for line in text.splitlines() if line.startswith("VmRSS:")), None)
        if rss:
            total_kb += int(rss)
            found = True
    return round(total_kb / 1024) if found else None


def gpu_memory_used_mb(run: Callable = subprocess.run) -> Optional[float]:
    """VRAM utilisée sur la carte (tous processus), via nvidia-smi. None si indisponible."""
    try:
        out = run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                  capture_output=True, text=True, timeout=10)
        return float(out.stdout.strip().splitlines()[0])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def machine_info(api: RapideAPI) -> dict[str, str]:
    """Description de la machine, pour que le résultat soit interprétable et reproductible."""
    info = {"os": f"{platform.system()} {platform.release()}", "python": platform.python_version(),
            "cpu_threads": str(os.cpu_count())}
    try:
        cpu = next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                   if line.startswith("model name"))
        info["cpu"] = cpu
    except (OSError, StopIteration):
        info["cpu"] = platform.processor() or "inconnu"
    try:
        kb = int(next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines()
                      if line.startswith("MemTotal")))
        info["ram"] = f"{kb / 2**20:.1f} Go"
    except (OSError, StopIteration, ValueError):
        info["ram"] = "inconnue"
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10)
        info["gpu"] = out.stdout.strip() or "aucun"
    except (OSError, subprocess.SubprocessError):
        info["gpu"] = "aucun"
    try:
        info["ollama"] = api.get("api/version").get("version", "inconnue")
    except Exception:
        info["ollama"] = "inconnue"
    return info


# ── Requêtes ─────────────────────────────────────────────────────────

def unload(api: RapideAPI, model: str) -> None:
    """Décharge le modèle de la mémoire (keep_alive à 0) pour mesurer ensuite un démarrage à froid."""
    api.post("api/generate", json={"model": model, "keep_alive": 0})
    for _ in range(50):
        if not any(m.get("name", "").startswith(model.split(":")[0]) for m in api.get("api/ps").get("models", [])):
            return
        time.sleep(0.2)


def timed_chat(api: RapideAPI, model: str, prompt: str, options: dict, clock: Callable = time.perf_counter,
               think: Optional[bool] = None) -> dict:
    """
    Envoie un message en streaming et mesure, côté client :
    le premier token généré, le premier token de réponse (après l'éventuelle réflexion) et la durée totale.
    think=None reproduit l'application : Ollama applique le comportement par défaut du modèle.
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "options": options,
        "keep_alive": "10m",
    }
    if think is not None:
        payload["think"] = think
    start = clock()
    ttft = None
    answer_ttft = None
    thinking_chunks = 0
    final: dict = {}
    for chunk in api.stream_ndjson("api/chat", json_data=payload):
        if "error" in chunk:
            raise RuntimeError(f"Ollama : {chunk['error']}")
        message = chunk.get("message", {})
        if message.get("thinking"):
            thinking_chunks += 1
        if message.get("content") or message.get("thinking"):
            now = clock()
            if ttft is None:
                ttft = now - start
            if answer_ttft is None and message.get("content"):
                answer_ttft = now - start
        if chunk.get("done"):
            final = chunk
    return metrics_from_chunk(final, ttft, clock() - start, answer_ttft, thinking_chunks)


def run_benchmark(api: RapideAPI, models: list[str], backends: list[str], ctx_values: list[int],
                  reps: int, num_predict: int, log: Callable[[str], None] = print) -> list[dict]:
    rows: list[dict] = []
    for model in models:
        for backend in backends:
            for num_ctx in ctx_values:
                options = {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": 0.0, "seed": 42}
                if backend == "cpu":
                    options["num_gpu"] = 0  # aucune couche sur le GPU : tout est calculé par le processeur
                log(f"== {model} | {backend} | num_ctx={num_ctx}")
                unload(api, model)
                vram_before = gpu_memory_used_mb()
                first = True
                for prompt_name, prompt in PROMPTS.items():
                    for run in range(reps + 1):  # le passage 0 sert de chauffe (sauf démarrage à froid)
                        # Un préfixe unique empêche Ollama de réutiliser le cache du prompt précédent
                        text = f"[Mesure {prompt_name}-{run}-{time.time_ns()}]\n{prompt}"
                        metrics = timed_chat(api, model, text, options)
                        cold = first
                        first = False
                        if run == 0 and not cold:
                            continue
                        row = {"model": model, "backend": backend, "num_ctx": num_ctx, "prompt": prompt_name,
                               "run": run, "cold_start": cold, **metrics}
                        row.update(model_memory(api.get("api/ps"), model))
                        row["ram_ollama_mb"] = ollama_rss_mb()
                        used = gpu_memory_used_mb()
                        row["vram_used_mb"] = round(used - vram_before) if used is not None and vram_before is not None else None
                        rows.append(row)
                        log(f"   {prompt_name} #{run}{' (froid)' if cold else ''} : "
                            f"{metrics['gen_tps']} tok/s, 1er token {metrics['ttft_s']} s, total {metrics['total_s']} s")
    for model in models:
        unload(api, model)
    return rows


def benchmark_thinking(api: RapideAPI, model: str, reps: int, num_predict: int = 1024,
                       log: Callable[[str], None] = print) -> list[dict]:
    """
    Coût de la réflexion (thinking) des modèles qui la proposent : même question, réflexion par défaut puis désactivée.
    La réponse visible n'arrive qu'après la réflexion : c'est l'attente réelle de l'utilisateur.
    """
    rows = []
    options = {"num_ctx": 4096, "num_predict": num_predict, "temperature": 0.0, "seed": 42}
    for label, think in (("par défaut", None), ("désactivée", False)):
        timed_chat(api, model, f"[chauffe {time.time_ns()}] Bonjour", options, think=think)
        for run in range(1, reps + 1):
            text = f"[Réflexion {label}-{run}-{time.time_ns()}]\n{PROMPTS['court']}"
            metrics = timed_chat(api, model, text, options, think=think)
            rows.append({"model": model, "thinking": label, "run": run, **metrics})
            log(f"   réflexion {label} #{run} : réponse visible après {metrics['answer_ttft_s']} s, "
                f"{metrics['thinking_chunks']} tokens de réflexion, total {metrics['total_s']} s")
    return rows


def benchmark_embeddings(api: RapideAPI, model: str, reps: int, clock: Callable = time.perf_counter) -> list[dict]:
    """Latence de l'embedding (mémoire longue / RAG) : un texte seul, puis un lot de 32 textes."""
    rows = []
    for label, texts in (("1 texte", [FILLER]), ("32 textes", [f"{i} {FILLER}" for i in range(32)])):
        api.post("api/embed", json={"model": model, "input": texts[0]})  # chauffe
        for run in range(1, reps + 1):
            start = clock()
            api.post("api/embed", json={"model": model, "input": texts})
            rows.append({"model": model, "batch": label, "run": run, "total_s": round(clock() - start, 3)})
    return rows


# ── Rapport ──────────────────────────────────────────────────────────

def write_csv(rows: list[dict], path: Path, fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:g}"


def build_report(rows: list[dict], embed_rows: list[dict], info: dict, args: argparse.Namespace,
                 thinking_rows: Optional[list[dict]] = None) -> str:
    lines = [f"# Benchmark des ressources : résultats du {datetime.now():%Y-%m-%d %H:%M}", "",
             "Protocole et analyse : [docs/16-benchmark-ressources.md](../../docs/16-benchmark-ressources.md).", "",
             "## Machine", "", "| Élément | Valeur |", "|---------|--------|"]
    lines += [f"| {key} | {value} |" for key, value in info.items()]
    lines += ["", "## Paramètres", "",
              f"- Modèles : {', '.join(args.models)}",
              f"- Exécution : {', '.join(args.backends)}",
              f"- num_ctx : {', '.join(map(str, args.num_ctx))}",
              f"- Répétitions mesurées par prompt : {args.reps} (après 1 passage de chauffe)",
              f"- num_predict : {args.num_predict}, temperature 0, seed 42", "",
              "## Démarrage à froid", "",
              "| Modèle | Exécution | num_ctx | Chargement (s) | 1er token (s) | Total (s) |",
              "|--------|-----------|---------|----------------|---------------|-----------|"]
    for row in (r for r in rows if r["cold_start"]):
        lines.append(f"| {row['model']} | {row['backend']} | {row['num_ctx']} | {fmt(row['load_s'])} | "
                     f"{fmt(row['ttft_s'])} | {fmt(row['total_s'])} |")

    lines += ["", "## Vitesse à chaud (médiane, et min-max)", "",
              "| Modèle | Exécution | num_ctx | Prompt | Lecture (tok/s) | Génération (tok/s) | 1er token (s) | Total (s) |",
              "|--------|-----------|---------|--------|-----------------|--------------------|---------------|-----------|"]
    # 1er token : premier token généré, réflexion comprise
    warm = [r for r in rows if not r["cold_start"]]
    keys = sorted({(r["model"], r["backend"], r["num_ctx"], r["prompt"]) for r in warm},
                  key=lambda k: (k[0], k[1], k[2], k[3]))
    for model, backend, num_ctx, prompt in keys:
        group = [r for r in warm if (r["model"], r["backend"], r["num_ctx"], r["prompt"]) == (model, backend, num_ctx, prompt)]
        cells = []
        for metric in ("prompt_tps", "gen_tps", "ttft_s", "total_s"):
            s = summarize(r[metric] for r in group)
            cells.append(f"{fmt(s['median'])} ({fmt(s['min'])}-{fmt(s['max'])})")
        lines.append(f"| {model} | {backend} | {num_ctx} | {prompt} | " + " | ".join(cells) + " |")

    lines += ["", "## Mémoire (modèle chargé)", "",
              "| Modèle | Exécution | num_ctx | Taille chargée (Mo) | Dont VRAM (Mo) | Part GPU (%) | VRAM ajoutée (Mo) | RAM Ollama (Mo) |",
              "|--------|-----------|---------|---------------------|----------------|--------------|-------------------|-----------------|"]
    for model, backend, num_ctx in sorted({(r["model"], r["backend"], r["num_ctx"]) for r in rows}):
        group = [r for r in rows if (r["model"], r["backend"], r["num_ctx"]) == (model, backend, num_ctx)]
        def peak(key):
            values = [r[key] for r in group if r[key] is not None]
            return max(values) if values else None
        lines.append(f"| {model} | {backend} | {num_ctx} | {fmt(peak('model_size_mb'))} | {fmt(peak('model_vram_mb'))} | "
                     f"{fmt(peak('gpu_share_pct'))} | {fmt(peak('vram_used_mb'))} | {fmt(peak('ram_ollama_mb'))} |")

    if thinking_rows:
        lines += ["", "## Réflexion du modèle (num_ctx 4096, GPU)", "",
                  "| Modèle | Réflexion | Réponse visible après (s) | Tokens de réflexion | Total (s) |",
                  "|--------|-----------|---------------------------|---------------------|-----------|"]
        for model, label in sorted({(r["model"], r["thinking"]) for r in thinking_rows}, key=lambda k: (k[0], k[1] != "par défaut")):
            group = [r for r in thinking_rows if (r["model"], r["thinking"]) == (model, label)]
            cells = [summarize(r[key] for r in group) for key in ("answer_ttft_s", "thinking_chunks", "total_s")]
            lines.append(f"| {model} | {label} | " + " | ".join(f"{fmt(c['median'])} ({fmt(c['min'])}-{fmt(c['max'])})" for c in cells) + " |")

    if embed_rows:
        lines += ["", "## Embeddings (mémoire longue)", "", "| Modèle | Lot | Durée médiane (s) | Min-max (s) |",
                  "|--------|-----|-------------------|-------------|"]
        for model, batch in sorted({(r["model"], r["batch"]) for r in embed_rows}):
            s = summarize(r["total_s"] for r in embed_rows if (r["model"], r["batch"]) == (model, batch))
            lines.append(f"| {model} | {batch} | {fmt(s['median'])} | {fmt(s['min'])}-{fmt(s['max'])} |")
    return "\n".join(lines) + "\n"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark des ressources locales (Ollama).")
    parser.add_argument("--models", nargs="+", default=[config.DEFAULT_MODEL], help="Modèles à mesurer.")
    parser.add_argument("--backends", nargs="+", choices=["gpu", "cpu"], default=["gpu", "cpu"],
                        help="gpu : placement automatique d'Ollama ; cpu : num_gpu=0.")
    parser.add_argument("--num-ctx", nargs="+", type=int, default=[2048, 4096, 8192], help="Tailles de contexte.")
    parser.add_argument("--reps", type=int, default=3, help="Répétitions mesurées par prompt.")
    parser.add_argument("--num-predict", type=int, default=128, help="Tokens générés par requête.")
    parser.add_argument("--embed-model", default=config.EMBED_MODEL, help="Modèle d'embedding ('' pour ignorer).")
    parser.add_argument("--no-thinking", dest="thinking", action="store_false",
                        help="Ne pas mesurer le coût de la réflexion (réflexion par défaut contre désactivée).")
    parser.add_argument("--host", default=config.OLLAMA_HOST)
    parser.add_argument("--out", default=str(PROJECT_ROOT / "benchmark" / "results"), help="Dossier des résultats.")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    api = RapideAPI(base_url=args.host, timeout=600)
    info = machine_info(api)
    print(json.dumps(info, ensure_ascii=False, indent=2))

    rows = run_benchmark(api, args.models, args.backends, args.num_ctx, args.reps, args.num_predict)
    thinking_rows = benchmark_thinking(api, args.models[0], args.reps) if args.thinking else []
    embed_rows = benchmark_embeddings(api, args.embed_model, args.reps) if args.embed_model else []

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    write_csv(rows, out / f"{stamp}_resources.csv", CSV_FIELDS)
    if embed_rows:
        write_csv(embed_rows, out / f"{stamp}_embeddings.csv", ["model", "batch", "run", "total_s"])
    if thinking_rows:
        write_csv(thinking_rows, out / f"{stamp}_thinking.csv",
                  ["model", "thinking", "run", "answer_ttft_s", "thinking_chunks", "ttft_s", "total_s", "gen_tokens", "gen_tps"])
    report = out / f"{stamp}_resources.md"
    report.write_text(build_report(rows, embed_rows, info, args, thinking_rows), encoding="utf-8")
    print(f"\nRapport : {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
