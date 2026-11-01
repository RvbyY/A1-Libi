"""
Module config.py
Configuration centralisée de SensAI.

Ordre de priorité (du plus fort au plus faible) :
    1. Arguments CLI (--model, --host, ...) via Config.apply_overrides()
    2. Fichier YAML (--config, ou config.yaml à la racine s'il existe) via Config.load_yaml()
    3. Variables d'environnement / fichier .env
    4. Valeurs par défaut
"""
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
    ("database", "url"): "DB_URL",
    ("memory", "context_limit"): "CONTEXT_LIMIT",
    ("memory", "deep_context_limit"): "DEEP_CONTEXT_LIMIT",
}


class ConfigError(ValueError):
    """Fichier de configuration introuvable ou invalide."""


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

    # ── Paramètres de Mémoire (Contextes) ──
    # Nombre max de messages conservés en mémoire courte (avant archivage)
    CONTEXT_LIMIT: int = int(os.getenv("CONTEXT_LIMIT", "10"))

    # Nombre max d'entrées vectorielles dans la mémoire long terme (DeepContext)
    DEEP_CONTEXT_LIMIT: int = int(os.getenv("DEEP_CONTEXT_LIMIT", "4096"))

    # ── Outils de Communication (Discord, Telegram, Email) ──
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    DISCORD_ID: str = os.getenv("DISCORD_ID", "")
    TELEGRAM_TOKEN: str = os.getenv("TOKEN", os.getenv("TELEGRAM_TOKEN", ""))
    SMTP_HOST: str = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "25"))

    # Chemin du fichier YAML effectivement chargé (None si aucun)
    loaded_file: Optional[str] = None

    def _set(self, attr: str, value: Any, source: str) -> None:
        """Affecte une valeur en la convertissant au type de la valeur par défaut."""
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
            for key, value in values.items():
                attr = YAML_KEYS.get((section, key))
                if attr is None:
                    raise ConfigError(f"{path} : clé inconnue '{section}.{key}'.")
                if value is not None:
                    self._set(attr, value, f"{path} [{section}.{key}]")

        self.loaded_file = str(path)
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
