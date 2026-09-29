def summarize_session(session_id: str) -> str:
    """Compresse l'historique en résumé (utile quand la sliding window évince)."""

def search_memory(session_id: str, query: str) -> list[dict]:
    """Recherche dans l'historique long-terme persisté (pas juste RAM)."""

def clear_session(session_id: str) -> bool:
    """Réinitialise la mémoire courte."""