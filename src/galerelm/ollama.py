"""
Module ollama.py
Erreurs Ollama typées et vérification de disponibilité du serveur et des modèles.

Les exceptions httpx brutes sont converties en erreurs explicites :
    - OllamaUnreachableError : serveur injoignable (connexion refusée, DNS, ...)
    - OllamaTimeoutError     : serveur trop lent à répondre
    - ModelNotFoundError     : modèle absent localement (404 d'Ollama)
    - OllamaError            : toute autre erreur renvoyée par l'API
"""
import json
import logging
from typing import Iterable, Optional

import httpx

logger = logging.getLogger("galerelm.ollama")


class OllamaError(RuntimeError):
    """Erreur générique de communication avec Ollama, avec une suggestion de résolution."""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return f"{self.message}\n→ {self.hint}" if self.hint else self.message


class OllamaUnreachableError(OllamaError):
    def __init__(self, host: str):
        super().__init__(
            f"Impossible de joindre Ollama sur {host}.",
            "Lancez le serveur avec `ollama serve` (ou ./script/backend.sh) et vérifiez --host / OLLAMA_HOST.",
        )
        self.host = host


class OllamaTimeoutError(OllamaError):
    def __init__(self, host: str):
        super().__init__(
            f"Ollama ({host}) n'a pas répondu à temps.",
            "Le modèle est peut-être en cours de chargement : réessayez, ou augmentez ollama.timeout.",
        )
        self.host = host


class ModelNotFoundError(OllamaError):
    def __init__(self, model: str, available: Optional[Iterable[str]] = None):
        available = sorted(available or [])
        hint = f"Téléchargez-le avec `ollama pull {model}`"
        if available:
            hint += f", ou choisissez un modèle installé avec --model : {', '.join(available)}"
        super().__init__(f"Le modèle '{model}' n'est pas installé dans Ollama.", hint + ".")
        self.model = model
        self.available = available


def _extract_error_message(response: httpx.Response) -> str:
    """Récupère le champ 'error' renvoyé par Ollama, ou le corps brut."""
    try:
        body = response.text
    except httpx.ResponseNotRead:
        return ""
    try:
        return str(json.loads(body).get("error", body))
    except (ValueError, AttributeError):
        return body


def _requested_model(request: Optional[httpx.Request]) -> Optional[str]:
    """Lit le champ 'model' dans le corps JSON de la requête envoyée."""
    if request is None:
        return None
    try:
        return json.loads(request.content or b"{}").get("model")
    except (ValueError, AttributeError, httpx.RequestNotRead):
        return None


def translate_error(exc: Exception, host: str = "", model: Optional[str] = None) -> Exception:
    """Convertit une exception httpx en OllamaError explicite. Les autres exceptions sont renvoyées telles quelles."""
    if isinstance(exc, OllamaError):
        return exc
    if isinstance(exc, httpx.TimeoutException):
        return OllamaTimeoutError(host)
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        detail = _extract_error_message(response)
        if response.status_code == 404 and "model" in detail.lower() and "not found" in detail.lower():
            return ModelNotFoundError(_requested_model(exc.request) or model or "?")
        return OllamaError(f"Ollama a renvoyé une erreur HTTP {response.status_code} : {detail or 'aucun détail'}.")
    if isinstance(exc, httpx.RequestError):
        return OllamaUnreachableError(host)
    return exc


def list_local_models(api) -> list[str]:
    """Retourne les noms des modèles installés localement (GET /api/tags)."""
    try:
        response = api.get("api/tags")
    except httpx.HTTPError as exc:
        raise translate_error(exc, host=api.base_url) from exc
    if not isinstance(response, dict):
        raise OllamaError(f"Réponse inattendue de {api.base_url}/api/tags : est-ce bien un serveur Ollama ?")
    return [m.get("name", "") for m in response.get("models", [])]


def model_is_available(model: str, installed: Iterable[str]) -> bool:
    """Compare un nom de modèle aux modèles installés ('llama3.2' correspond à 'llama3.2:latest')."""
    installed = set(installed)
    if model in installed:
        return True
    if ":" not in model:
        return f"{model}:latest" in installed
    return False


def check_ollama(api, model: str, embed_model: Optional[str] = None) -> list[str]:
    """
    Vérifie au démarrage que le serveur répond et que le modèle de chat est installé.
    Lève OllamaUnreachableError / ModelNotFoundError. Retourne la liste des avertissements
    non bloquants (ex: modèle d'embedding absent -> mémoire long terme dégradée).
    """
    installed = list_local_models(api)
    if not model_is_available(model, installed):
        raise ModelNotFoundError(model, installed)

    warnings = []
    if embed_model and not model_is_available(embed_model, installed):
        warnings.append(
            f"Modèle d'embedding '{embed_model}' absent : la mémoire long terme (RAG) est désactivée. "
            f"Installez-le avec `ollama pull {embed_model}`."
        )
    return warnings
