"""
Module prompt_simplifier.py
Nettoyage léger (sans appel LLM) du message utilisateur avant le Guardrail et le LLM principal :
tics de langage, formules de politesse, ponctuation répétée et espaces en trop (FR + EN).
Les petits mots ("le", "de", "ne", "pas", "not"...) sont conservés pour ne pas perdre de sens.
"""
import re
from src.galerelm.models.message import MessageList

FILLERS_FR = [
    "s'il te plaît", "s'il te plait", "s'il vous plaît", "s'il vous plait", "merci d'avance",
    "en fait", "du coup", "tu vois", "bonjour", "bonsoir", "salut", "coucou", "merci",
    "stp", "svp", "euh", "bah", "ben", "bref", "genre", "voilà", "voila",
]

FILLERS_EN = [
    "thanks in advance", "thank you", "you know", "i mean", "basically", "actually", "literally",
    "kinda", "hello", "thanks", "please", "hey", "hi", "plz", "pls", "uhm", "um", "uh", "hmm",
]

_FILLERS = sorted(FILLERS_FR + FILLERS_EN, key=len, reverse=True)
_FILLER_RE = re.compile(
    r"\s*(?<!\w)(?:" + "|".join(re.escape(f) for f in _FILLERS) + r")(?!\w),?",
    re.IGNORECASE,
)
_REPEATED_PUNCT_RE = re.compile(r"([?!.,])\1+")
_SPACES_RE = re.compile(r"\s+")


def simplify(text: str) -> str:
    """Retourne le message allégé, ou l'original si le nettoyage ne laisse rien."""
    cleaned = _FILLER_RE.sub("", text)
    cleaned = _REPEATED_PUNCT_RE.sub(r"\1", cleaned)
    cleaned = _SPACES_RE.sub(" ", cleaned).strip(" ,;")
    if not any(c.isalnum() for c in cleaned):
        return text
    return cleaned


def replace_last_user_message(messages: MessageList, content: str) -> MessageList:
    """Remplace le contenu du dernier message 'user' d'une copie d'historique destinée au LLM."""
    for message in reversed(messages):
        if message.role == "user":
            message.content = content
            break
    return messages
