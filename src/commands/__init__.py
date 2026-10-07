"""
Package commands
Système de commandes du terminal SensAI (/help, /quit, ...).

Chaque commande est une classe qui hérite de Command.
default_registry() construit le registre avec toutes les commandes intégrées.
"""
from src.commands.base import Command, CommandResult
from src.commands.registry import CommandRegistry
from src.commands.general import HelpCommand, QuitCommand
from src.commands.debug import (
    ProfileCommand, ContextCommand, MessagesCommand, MemoriesCommand, PayloadCommand,
)
from src.commands.session import ClearCommand, NewCommand
from src.commands.memory import RecallCommand

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
    NewCommand,
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
    "RecallCommand", "ClearCommand", "NewCommand",
]
