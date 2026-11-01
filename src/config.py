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
import shlex
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
    ("prompt", "persona"): "DEFAULT_PERSONA",
    ("guardrails", "input"): "GUARDRAIL_INPUT",
    ("guardrails", "output"): "GUARDRAIL_OUTPUT",
    ("guardrails", "pii"): "GUARDRAIL_PII",
}

# Valeurs acceptées pour les réglages à choix fermés
CHOICES: dict[str, tuple[str, ...]] = {
    "GUARDRAIL_INPUT": ("off", "safety", "alibi"),
    "GUARDRAIL_OUTPUT": ("off", "anonymize", "refuse"),
}
PII_CATEGORIES = ("email", "iban", "card", "ssn", "phone")

# ── Personas (A5) ────────────────────────────────────────────────────
# Un persona définit le nom, le ton, le rôle et le périmètre de l'agent. Il se choisit dans config.yaml
# (prompt.persona), avec --persona, ou pendant la session avec /persona, sans effacer l'historique.
# "instructions" vide : les instructions du profil utilisateur sont gardées (comportement par défaut).
DEFAULT_PERSONAS: dict[str, dict[str, str]] = {
    "alibi": {
        "name": "Alibi",
        "description": "Assistant général (instructions du profil).",
        "instructions": "",
    },
    "tuteur": {
        "name": "Tuteur de mathématiques",
        "description": "Explique les mathématiques pas à pas, avec un exemple.",
        "instructions": (
            "Tu es {persona}, patient et encourageant.\n"
            "Explique chaque notion étape par étape, avec un exemple chiffré, puis pose une question "
            "pour vérifier que l'élève a compris.\n"
            "Tu ne réponds qu'aux questions de mathématiques : pour tout autre sujet, dis-le poliment et propose de revenir aux maths."
        ),
    },
    "juriste": {
        "name": "Assistant juridique",
        "description": "Vulgarise le droit français, sans remplacer un avocat.",
        "instructions": (
            "Tu es {persona}. Tu expliques le droit français simplement, en citant le texte ou le principe concerné.\n"
            "Tu rappelles que ta réponse est une information générale, pas un conseil juridique, "
            "et tu orientes vers un professionnel pour un cas précis."
        ),
    },
}
PERSONA_FIELDS = ("name", "description", "instructions")

# ── Serveurs MCP (T1) ────────────────────────────────────────────────
# Chaque serveur est un programme lancé par SensAI (transport stdio) ; ses outils rejoignent ceux de SensAI.
MCP_SERVER_FIELDS = ("command", "env", "cwd", "timeout", "confirm", "enabled")

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

    # ── Guardrails (EV2) ──
    # Entrée : classification d'intention avant le modèle (off, safety, alibi)
    GUARDRAIL_INPUT: str = os.getenv("GUARDRAIL_INPUT", "off")
    # Sortie : données personnelles dans les réponses (off, anonymize, refuse)
    GUARDRAIL_OUTPUT: str = os.getenv("GUARDRAIL_OUTPUT", "off")
    # Catégories surveillées par le filtre de sortie
    GUARDRAIL_PII: list = list(PII_CATEGORIES)

    # ── Persona (A5) ──
    DEFAULT_PERSONA: str = os.getenv("PERSONA", "alibi")

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
        self.PERSONAS: dict[str, dict[str, str]] = copy.deepcopy(DEFAULT_PERSONAS)
        self.MCP_SERVERS: dict[str, dict[str, Any]] = {}
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
        if attr in CHOICES and value is False:
            value = "off"  # en YAML, `off` sans guillemets est lu comme le booléen false
        if attr in CHOICES and value not in CHOICES[attr]:
            raise ConfigError(f"{source} : valeur invalide '{value}' (attendu : {', '.join(CHOICES[attr])}).")
        if attr == "GUARDRAIL_PII":
            items = [v.strip() for v in value.split(",")] if isinstance(value, str) else value
            if not isinstance(items, list) or not items or any(item not in PII_CATEGORIES for item in items):
                raise ConfigError(f"{source} : liste invalide {value!r} (catégories : {', '.join(PII_CATEGORIES)}).")
            setattr(self, attr, list(items))
            return
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
            if section == "personas":
                self._load_personas(values, path)
                continue
            if section == "mcp_servers":
                self._load_mcp_servers(values, path)
                continue
            for key, value in values.items():
                attr = YAML_KEYS.get((section, key))
                if attr is None:
                    raise ConfigError(f"{path} : clé inconnue '{section}.{key}'.")
                if value is not None:
                    self._set(attr, value, f"{path} [{section}.{key}]")

        if self.DEFAULT_PERSONA not in self.PERSONAS:
            raise ConfigError(f"{path} : persona inconnu '{self.DEFAULT_PERSONA}' (connus : {', '.join(self.PERSONAS)}).")
        self.loaded_file = str(path)
        return self

    def _load_personas(self, personas: dict, path: Path) -> None:
        """Section 'personas' : ajoute ou remplace des personas (clé -> name, description, instructions)."""
        for key, spec in personas.items():
            if not isinstance(spec, dict):
                raise ConfigError(f"{path} : 'personas.{key}' doit être un dictionnaire (name, description, instructions).")
            unknown = set(spec) - set(PERSONA_FIELDS)
            if unknown:
                raise ConfigError(f"{path} : champ inconnu dans 'personas.{key}' : {', '.join(sorted(unknown))}.")
            if not isinstance(spec.get("name"), str) or not spec["name"].strip():
                raise ConfigError(f"{path} : 'personas.{key}.name' est obligatoire.")
            self.PERSONAS[str(key)] = {field: str(spec.get(field) or "") for field in PERSONA_FIELDS}

    def _load_mcp_servers(self, servers: dict, path: Path) -> None:
        """Section 'mcp_servers' : nom -> command (liste ou chaîne), env, cwd, timeout, confirm, enabled."""
        for name, spec in servers.items():
            where = f"{path} [mcp_servers.{name}]"
            if not isinstance(spec, dict):
                raise ConfigError(f"{where} : doit être un dictionnaire (command, env, cwd, timeout, confirm, enabled).")
            unknown = set(spec) - set(MCP_SERVER_FIELDS)
            if unknown:
                raise ConfigError(f"{where} : champ inconnu {', '.join(sorted(unknown))}.")
            command = spec.get("command")
            if isinstance(command, str):
                command = shlex.split(command)
            if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
                raise ConfigError(f"{where} : 'command' est obligatoire (liste ou chaîne).")
            env = spec.get("env") or {}
            if not isinstance(env, dict):
                raise ConfigError(f"{where} : 'env' doit être un dictionnaire.")
            self.MCP_SERVERS[str(name)] = {
                "command": command,
                "env": {str(k): str(v) for k, v in env.items()},
                "cwd": spec.get("cwd"),
                "timeout": float(spec.get("timeout", 30)),
                "confirm": bool(spec.get("confirm", True)),
                "enabled": bool(spec.get("enabled", True)),
            }

    def persona(self, key: Optional[str] = None) -> dict[str, str]:
        """Retourne un persona (par défaut : DEFAULT_PERSONA). Lève ConfigError s'il est inconnu."""
        key = key or self.DEFAULT_PERSONA
        if key not in self.PERSONAS:
            raise ConfigError(f"Persona inconnu '{key}' (connus : {', '.join(self.PERSONAS)}).")
        return {"key": key, **self.PERSONAS[key]}

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
