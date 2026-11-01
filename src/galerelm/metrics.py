"""
Module metrics.py
Calcul des métriques (EV3) à partir du journal des échanges (InteractionLog) :
volume, latence, taux d'erreur, tokens, outils, et leur évolution jour par jour.
"""
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

from src.galerelm.models.interaction_log import InteractionLog


def _percentile(values: list[float], pct: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return round(ordered[index], 2)


def _mean(values: list[float]) -> Optional[float]:
    return round(statistics.mean(values), 2) if values else None


def summarize(rows: list[InteractionLog]) -> dict[str, Any]:
    """Indicateurs d'un ensemble d'échanges."""
    latencies = [r.latency_s for r in rows if r.latency_s is not None and r.status in ("ok", "blocked")]
    firsts = [r.first_token_s for r in rows if r.first_token_s is not None]
    errors = sum(1 for r in rows if r.status == "error")
    tool_calls = sum(len(r.tools or []) for r in rows)
    tool_failures = sum(r.tool_failures or 0 for r in rows)
    return {
        "calls": len(rows),
        "errors": errors,
        "error_rate": round(100 * errors / len(rows), 1) if rows else 0.0,
        "blocked": sum(1 for r in rows if r.status == "blocked"),
        "latency_mean": _mean(latencies),
        "latency_p50": _percentile(latencies, 50),
        "latency_p95": _percentile(latencies, 95),
        "first_token_mean": _mean(firsts),
        "prompt_tokens_mean": _mean([r.prompt_tokens for r in rows if r.prompt_tokens]),
        "gen_tokens_mean": _mean([r.gen_tokens for r in rows if r.gen_tokens]),
        "tool_calls": tool_calls,
        "tool_failures": tool_failures,
    }


def load(session, days: int = 7, profile_id: Optional[str] = None, now: Optional[datetime] = None) -> list[InteractionLog]:
    since = (now or datetime.now()) - timedelta(days=days)
    query = session.query(InteractionLog).filter(InteractionLog.created_at >= since)
    if profile_id is not None:
        query = query.filter(InteractionLog.profile_id == profile_id)
    return query.order_by(InteractionLog.created_at).all()


def report(session, days: int = 7, profile_id: Optional[str] = None, now: Optional[datetime] = None) -> dict[str, Any]:
    """Résumé global, par jour (pour suivre la dérive) et par modèle."""
    rows = load(session, days, profile_id, now)
    by_day: dict[str, list] = defaultdict(list)
    by_model: dict[str, list] = defaultdict(list)
    for row in rows:
        by_day[row.created_at.strftime("%Y-%m-%d")].append(row)
        by_model[row.model or "?"].append(row)
    return {
        "days": days,
        "total": summarize(rows),
        "per_day": {day: summarize(items) for day, items in sorted(by_day.items())},
        "per_model": {model: summarize(items) for model, items in sorted(by_model.items())},
    }


def fmt(value: Any, unit: str = "") -> str:
    return "-" if value is None else f"{value}{unit}"


def format_report(data: dict[str, Any]) -> str:
    """Rapport texte (commande /stats)."""
    total = data["total"]
    if not total["calls"]:
        return f"Aucun échange enregistré sur les {data['days']} derniers jours."
    lines = [
        f"Échanges sur {data['days']} jours : {total['calls']} (erreurs : {total['errors']}, soit {total['error_rate']} % ; "
        f"bloqués par le guardrail : {total['blocked']})",
        f"Latence : moyenne {fmt(total['latency_mean'], ' s')}, médiane {fmt(total['latency_p50'], ' s')}, "
        f"p95 {fmt(total['latency_p95'], ' s')} ; premier morceau : {fmt(total['first_token_mean'], ' s')}",
        f"Tokens moyens : {fmt(total['prompt_tokens_mean'])} lus, {fmt(total['gen_tokens_mean'])} générés",
        f"Outils : {total['tool_calls']} appel(s), {total['tool_failures']} échec(s)",
        "",
        "Par jour       appels  erreurs  latence moy.  p95     tokens lus",
    ]
    for day, s in data["per_day"].items():
        lines.append(f"{day}  {s['calls']:>6}  {s['error_rate']:>6} %  {fmt(s['latency_mean'], ' s'):>12}  "
                     f"{fmt(s['latency_p95'], ' s'):>6}  {fmt(s['prompt_tokens_mean']):>10}")
    if len(data["per_model"]) > 1:
        lines += ["", "Par modèle :"]
        for model, s in data["per_model"].items():
            lines.append(f"  {model} : {s['calls']} appel(s), latence moy. {fmt(s['latency_mean'], ' s')}")
    return "\n".join(lines)
