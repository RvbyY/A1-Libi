"""
Module config.py
Configuration centralisée de SensAI.

Ordre de priorité (du plus fort au plus faible) :
    1. Arguments CLI (--model, --host, ...) via Config.apply_overrides()
    2. Fichier YAML (--config, ou config.yaml à la racine s'il existe) via Config.load_yaml()
    3. Variables d'environnement / fichier .env
    4. Valeurs par défaut
"""
import copy
import os
from pathlib import Path
from typing import Any, Optional, Union

import yaml
from dotenv import load_dotenv

# Charge les variables d'environnement depuis le fichier .env s'il existe
load_dotenv()

# Fichier chargé automatiquement s'il est présent dans le répertoire courant
DEFAULT_CONFIG_FILE = "config.yaml"

# Racine du dépôt : les chemins SQLite relatifs y sont résolus, quel que soit le dossier de lancement
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Correspondance (section, clé) du YAML -> attribut de Config
YAML_KEYS: dict[tuple[str, str], str] = {
    ("ollama", "host"): "OLLAMA_HOST",
    ("ollama", "model"): "DEFAULT_MODEL",
    ("ollama", "embed_model"): "EMBED_MODEL",
    ("ollama", "timeout"): "OLLAMA_TIMEOUT",
    ("ollama", "keep_alive"): "KEEP_ALIVE",
    ("database", "url"): "DB_URL",
    ("memory", "context_limit"): "CONTEXT_LIMIT",
    ("memory", "deep_context_limit"): "DEEP_CONTEXT_LIMIT",
    ("prompt", "tools_listing"): "TOOLS_LISTING",
}

# Description des outils dans le prompt système (ils sont aussi envoyés à Ollama dans le champ "tools") :
#   full  : une signature par outil (paramètres, valeurs possibles) et sa description
#   names : seulement la liste des noms
#   none  : aucune liste, seulement les règles d'utilisation
# Choix mesuré : docs/17-ameliorations-mesurees.md.
TOOLS_LISTING_MODES = ("full", "names", "none")


class ConfigError(ValueError):
    """Fichier de configuration introuvable ou invalide."""


# ── Paramètres de génération ─────────────────────────────────────────
# Chaque appel au modèle utilise un profil : la conversation (chat), le juge anti-hallucination (judge)
# et le classifieur d'intention (guardrail). Documentation : docs/15-parametres-generation.md.
GENERATION_PROFILES = ("chat", "judge", "guardrail")

# Paramètre -> (type, minimum, maximum). Les bornes refusent les valeurs absurdes.
GENERATION_PARAMS: dict[str, tuple[type, Optional[float], Optional[float]]] = {
    "temperature": (float, 0.0, 2.0),
    "top_k": (int, 1, 1000),
    "top_p": (float, 0.0, 1.0),
    "min_p": (float, 0.0, 1.0),
    "num_ctx": (int, 256, 131072),
    "num_predict": (int, -1, 32768),
    "seed": (int, 0, 2**31 - 1),
    "stop": (list, None, None),
}

DEFAULT_GENERATION: dict[str, dict[str, Any]] = {
    # Conversation : un peu de variété, réponse complète (-1 = jusqu'à la fin naturelle du modèle).
    # num_ctx 8192 : le prompt réel fait ~2 300 tokens avant tout historique (outils compris) ; le benchmark
    # (docs/16-benchmark-ressources.md) mesure +104 Mo de VRAM par rapport à 4096, sans perte de vitesse.
    "chat": {
        "temperature": 0.7, "top_k": 40, "top_p": 0.9, "min_p": 0.05,
        "num_ctx": 8192, "num_predict": -1, "seed": None, "stop": [],
    },
    # Juge et classifieur : déterministes (température 0, top_k 1) et courts (une réponse JSON)
    "judge": {
        "temperature": 0.0, "top_k": 1, "top_p": 1.0, "min_p": 0.0,
        "num_ctx": 4096, "num_predict": 160, "seed": None, "stop": [],
    },
    "guardrail": {
        "temperature": 0.0, "top_k": 1, "top_p": 1.0, "min_p": 0.0,
        "num_ctx": 2048, "num_predict": 128, "seed": None, "stop": [],
    },
}


def validate_generation_value(key: str, value: Any, source: str) -> Any:
    """Convertit et vérifie la valeur d'un paramètre de génération. Lève ConfigError si elle est invalide."""
    if key not in GENERATION_PARAMS:
        known = ", ".join(GENERATION_PARAMS)
        raise ConfigError(f"{source} : paramètre de génération inconnu '{key}' (connus : {known}).")
    expected, minimum, maximum = GENERATION_PARAMS[key]

    if key == "seed" and (value is None or str(value).lower() in ("none", "null", "random", "")):
        return None  # pas de graine : génération non reproductible
    if expected is list:
        if isinstance(value, str):
            value = [part for part in value.split(",") if part]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ConfigError(f"{source} : '{key}' doit être une liste de chaînes.")
        return value

    if isinstance(value, bool):
        raise ConfigError(f"{source} : valeur invalide '{value}' pour '{key}' (attendu : {expected.__name__}).")
    try:
        converted = expected(value)
        if expected is int and isinstance(value, float) and not value.is_integer():
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{source} : valeur invalide '{value}' pour '{key}' (attendu : {expected.__name__}).") from exc
    if not minimum <= converted <= maximum:
        raise ConfigError(f"{source} : '{key}' doit être entre {minimum} et {maximum} (reçu : {converted}).")
    return converted


def resolve_db_url(url: str) -> str:
    """
    Rend absolu le chemin d'une URL SQLite relative (sqlite:///galerelm.db) par rapport à PROJECT_ROOT.
    Sans cela, lancer l'outil depuis src/ ou depuis la racine ouvrait deux bases différentes.
    Les autres URLs (absolues, :memory:, PostgreSQL...) sont renvoyées telles quelles.
    """
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    path = url[len(prefix):]
    if not path or path.startswith(":memory:") or path.startswith("file:") or Path(path).is_absolute():
        return url
    return prefix + str(PROJECT_ROOT / path)


class Config:
    # ── Base de Données ──
    DB_URL: str = os.getenv("DB_URL", "sqlite:///galerelm.db")

    # ── Ollama API ──
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    DEFAULT_MODEL: str = os.getenv("HF_MODEL", "llama3.2")
    EMBED_MODEL: str = os.getenv("EMBED_MODEL", "nomic-embed-text")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))
    # Durée pendant laquelle Ollama garde le modèle en mémoire après un appel ("30m", "1h", "-1" = toujours)
    KEEP_ALIVE: str = os.getenv("OLLAMA_KEEP_ALIVE", "30m")

    # ── Paramètres de Mémoire (Contextes) ──
    # Nombre max de messages conservés en mémoire courte (avant archivage)
    CONTEXT_LIMIT: int = int(os.getenv("CONTEXT_LIMIT", "10"))

    # Nombre max d'entrées vectorielles dans la mémoire long terme (DeepContext)
    DEEP_CONTEXT_LIMIT: int = int(os.getenv("DEEP_CONTEXT_LIMIT", "4096"))

    # ── Prompt ──
    # "names" : choix mesuré (-288 tokens par requête, aucune perte de réussite), voir docs/17-ameliorations-mesurees.md
    TOOLS_LISTING: str = os.getenv("TOOLS_LISTING", "names")

    # ── Outils de Communication (Discord, Telegram, Email) ──
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    DISCORD_ID: str = os.getenv("DISCORD_ID", "")
    TELEGRAM_TOKEN: str = os.getenv("TOKEN", os.getenv("TELEGRAM_TOKEN", ""))
    SMTP_HOST: str = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "25"))

    # Chemin du fichier YAML effectivement chargé (None si aucun)
    loaded_file: Optional[str] = None

    def __init__(self) -> None:
        # Copie par instance : modifier un profil (/params, tests) ne touche pas aux valeurs par défaut
        self.GENERATION: dict[str, dict[str, Any]] = copy.deepcopy(DEFAULT_GENERATION)
        self._startup_generation = copy.deepcopy(self.GENERATION)

    # ── Paramètres de génération ─────────────────────────────────────

    def generation_options(self, profile: str = "chat") -> dict[str, Any]:
        """Retourne une copie des paramètres de génération d'un profil."""
        if profile not in GENERATION_PROFILES:
            raise ConfigError(f"Profil de génération inconnu '{profile}' (connus : {', '.join(GENERATION_PROFILES)}).")
        return copy.deepcopy(self.GENERATION[profile])

    def set_generation(self, profile: str, key: str, value: Any, source: str = "paramètre") -> Any:
        """Valide et modifie un paramètre de génération. Retourne la valeur enregistrée."""
        if profile not in GENERATION_PROFILES:
            raise ConfigError(f"{source} : profil de génération inconnu '{profile}' (connus : {', '.join(GENERATION_PROFILES)}).")
        converted = validate_generation_value(key, value, source)
        self.GENERATION[profile][key] = converted
        return converted

    def mark_startup_generation(self) -> None:
        """Mémorise les paramètres après chargement de la config (YAML + CLI), pour /params reset."""
        self._startup_generation = copy.deepcopy(self.GENERATION)

    def reset_generation(self) -> None:
        """Revient aux paramètres du démarrage (annule les changements faits avec /params)."""
        self.GENERATION = copy.deepcopy(self._startup_generation)

    @property
    def keep_alive(self) -> Union[str, int]:
        """KEEP_ALIVE au format attendu par Ollama : un nombre de secondes, ou une durée ("30m")."""
        value = str(self.KEEP_ALIVE).strip()
        return int(value) if value.lstrip("-").isdigit() else value

    def _set(self, attr: str, value: Any, source: str) -> None:
        """Affecte une valeur en la convertissant au type de la valeur par défaut."""
        if attr == "TOOLS_LISTING" and value not in TOOLS_LISTING_MODES:
            raise ConfigError(f"{source} : valeur invalide '{value}' (attendu : {', '.join(TOOLS_LISTING_MODES)}).")
        expected = type(getattr(Config, attr))
        try:
            setattr(self, attr, expected(value))
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{source} : valeur invalide '{value}' (attendu : {expected.__name__}).") from exc

    def load_yaml(self, path: Union[str, Path]) -> "Config":
        """Charge un fichier YAML et applique les clés connues. Lève ConfigError si invalide."""
        path = Path(path)
        if not path.is_file():
            raise ConfigError(f"Fichier de configuration introuvable : {path}")

        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"YAML invalide dans {path} : {exc}") from exc

        if not isinstance(data, dict):
            raise ConfigError(f"{path} doit contenir un dictionnaire de sections (ollama, database, memory).")

        for section, values in data.items():
            if not isinstance(values, dict):
                raise ConfigError(f"{path} : la section '{section}' doit être un dictionnaire.")
            if section == "generation":
                self._load_generation(values, path)
                continue
            for key, value in values.items():
                attr = YAML_KEYS.get((section, key))
                if attr is None:
                    raise ConfigError(f"{path} : clé inconnue '{section}.{key}'.")
                if value is not None:
                    self._set(attr, value, f"{path} [{section}.{key}]")

        self.loaded_file = str(path)
        return self

    def _load_generation(self, profiles: dict, path: Path) -> None:
        """Section 'generation' : un sous-dictionnaire par profil (chat, judge, guardrail)."""
        for profile, params in profiles.items():
            if not isinstance(params, dict):
                raise ConfigError(f"{path} : 'generation.{profile}' doit être un dictionnaire de paramètres.")
            for key, value in params.items():
                self.set_generation(profile, key, value, f"{path} [generation.{profile}.{key}]")

    def apply_generation_overrides(self, profile: str = "chat", **params: Any) -> "Config":
        """Applique des paramètres de génération passés en CLI (les valeurs None sont ignorées)."""
        for key, value in params.items():
            if value is not None:
                self.set_generation(profile, key, value, f"--{key.replace('_', '-')}")
        return self

    def apply_overrides(self, **overrides: Any) -> "Config":
        """Applique les valeurs passées en CLI (les valeurs None sont ignorées)."""
        for attr, value in overrides.items():
            if not hasattr(Config, attr):
                raise ConfigError(f"Paramètre de configuration inconnu : {attr}")
            if value is not None:
                self._set(attr, value, f"--{attr.lower()}")
        return self


config = Config()
