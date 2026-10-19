"""
Module commands/registry.py
Registre des commandes : enregistrement, recherche par nom/alias, et dispatch.
"""
import logging
from typing import TYPE_CHECKING, Optional

from src.commands.base import Command, CommandResult

if TYPE_CHECKING:
    from src.main import SensAI

logger = logging.getLogger("sensai.commands")

PREFIX = "/"


class CommandRegistry:
    """Associe chaque mot-clé (/help, /q, ...) à une instance de Command."""

    def __init__(self):
        self._commands: list[Command] = []
        self._index: dict[str, Command] = {}

    def register(self, command: Command) -> "CommandRegistry":
        """Enregistre une commande. Lève une erreur si un mot-clé est déjà pris."""
        for trigger in command.triggers:
            key = trigger.lower()
            if key in self._index:
                raise ValueError(f"Mot-clé de commande déjà utilisé : {PREFIX}{key}")
            self._index[key] = command
        self._commands.append(command)
        return self

    def get(self, trigger: str) -> Optional[Command]:
        return self._index.get(trigger.lower().lstrip(PREFIX))

    def all(self) -> list[Command]:
        """Liste des commandes uniques, dans l'ordre d'enregistrement."""
        return list(self._commands)

    @staticmethod
    def is_command(line: str) -> bool:
        return line.startswith(PREFIX)

    def dispatch(self, line: str, app: "SensAI") -> CommandResult:
        """Analyse une ligne '/cmd args' et exécute la commande correspondante."""
        parts = line[len(PREFIX):].split(maxsplit=1)
        trigger = parts[0] if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        command = self.get(trigger)
        if command is None:
            Command.error(f"Commande inconnue : {PREFIX}{trigger}. Tapez {PREFIX}help pour la liste.")
            return CommandResult.CONTINUE

        if command.requires_profile and (app.profile is None or app.context is None):
            Command.error("Aucun profil chargé.")
            return CommandResult.CONTINUE

        logger.info(f"[Command] {PREFIX}{command.name} (args={args!r})")
        try:
            result = command.execute(app, args)
        except Exception as e:
            logger.exception(f"[Command] Échec de {PREFIX}{command.name}")
            Command.error(f"Erreur pendant {PREFIX}{command.name} : {e}")
            return CommandResult.CONTINUE

        return result or CommandResult.CONTINUE
