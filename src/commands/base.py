"""
Module commands/base.py
Classe abstraite Command : contrat commun à toutes les commandes du terminal.
"""
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.main import SensAI


class CommandResult(Enum):
    """Indique à la boucle du terminal quoi faire après une commande."""
    CONTINUE = auto()
    QUIT = auto()


class Command(ABC):
    """
    Classe mère de toutes les commandes.

    Pour créer une commande :
        1. Hériter de Command.
        2. Renseigner name, description (et éventuellement aliases, usage).
        3. Implémenter execute().
        4. L'enregistrer dans commands/__init__.py.
    """

    # ── Attributs à surcharger ───────────────────────────────────────
    name: str = ""
    aliases: tuple[str, ...] = ()
    description: str = ""
    usage: str = ""
    requires_profile: bool = True

    # ── Contrat ──────────────────────────────────────────────────────

    @abstractmethod
    def execute(self, app: "SensAI", args: str) -> CommandResult:
        """Exécute la commande. Retourne CONTINUE ou QUIT."""

    # ── Utilitaires partagés ─────────────────────────────────────────

    ROLE_ICONS = {"system": "⚙️", "user": "👤", "assistant": "🤖", "tool": "🔧"}

    @property
    def triggers(self) -> tuple[str, ...]:
        """Tous les mots-clés qui déclenchent la commande (nom + alias)."""
        return (self.name, *self.aliases)

    @classmethod
    def icon(cls, role: str) -> str:
        return cls.ROLE_ICONS.get(role, "❓")

    @staticmethod
    def preview(text: str, length: int = 80) -> str:
        """Tronque un texte sur une seule ligne pour l'affichage."""
        flat = text.replace("\n", "↵")
        return flat if len(flat) <= length else flat[:length] + "..."

    @staticmethod
    def title(text: str):
        print(f"\n── {text} ──")

    @staticmethod
    def info(text: str):
        print(f"\n[i] {text}\n")

    @staticmethod
    def success(text: str):
        print(f"\n[✓] {text}\n")

    @staticmethod
    def error(text: str):
        print(f"\n[!] {text}\n")
