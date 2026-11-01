"""
Package commands
Système de commandes du terminal SensAI (/help, /quit, ...).

Chaque commande est une classe qui hérite de Command.
default_registry() construit le registre avec toutes les commandes intégrées.
"""
from src.commands.base import Command, CommandResult
from src.commands.registry import CommandRegistry
from src.commands.general import HelpCommand, QuitCommand
from src.commands.debug import (ProfileCommand, ContextCommand, MessagesCommand, MemoriesCommand, PayloadCommand,)
from src.commands.session import ClearCommand, NewCommand
from src.commands.memory import RecallCommand
from src.commands.schedule import ScheduleCommand
from src.commands.persona import PersonaCommand
from src.commands.documents import DocumentsCommand, IngestCommand
from src.commands.stats import StatsCommand
from src.commands.params import ParamsCommand

BUILTIN_COMMANDS: tuple[type[Command], ...] = (
    HelpCommand,
    QuitCommand,
    ProfileCommand,
    ContextCommand,
    MessagesCommand,
    MemoriesCommand,
    PayloadCommand,
    RecallCommand,
    ClearCommand,
    ScheduleCommand,
    NewCommand,
    ParamsCommand,
    PersonaCommand,
    IngestCommand,
    DocumentsCommand,
    StatsCommand,
)


def default_registry() -> CommandRegistry:
    """Crée un registre contenant toutes les commandes intégrées."""
    registry = CommandRegistry()
    for command_cls in BUILTIN_COMMANDS:
        registry.register(command_cls())
    return registry


__all__ = [
    "Command", "CommandResult", "CommandRegistry", "default_registry", "BUILTIN_COMMANDS",
    "HelpCommand", "QuitCommand",
    "ProfileCommand", "ContextCommand", "MessagesCommand", "MemoriesCommand", "PayloadCommand",
    "RecallCommand", "ClearCommand", "ScheduleCommand", "NewCommand", "PersonaCommand", "IngestCommand", "DocumentsCommand", "StatsCommand", "ParamsCommand",
]
