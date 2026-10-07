"""
Module commands/general.py
Commandes générales : aide et sortie.
"""
import logging

from src.commands.base import Command, CommandResult
from src.commands.registry import PREFIX

logger = logging.getLogger("sensai.commands")


class HelpCommand(Command):
    name = "help"
    aliases = ("h", "?")
    description = "Affiche les commandes."
    requires_profile = False

    def execute(self, app, args):
        commands = app.commands.all()
        rows = []
        for cmd in commands:
            label = f"{PREFIX}{cmd.name}" + (f" {cmd.usage}" if cmd.usage else "")
            alias = ", ".join(f"{PREFIX}{a}" for a in cmd.aliases)
            rows.append((label, cmd.description, alias))

        w_label = max(len(r[0]) for r in rows)
        w_desc = max(len(r[1]) for r in rows)
        w_alias = max(len(r[2]) for r in rows)
        width = w_label + w_desc + w_alias + 6

        print("\n╔" + "═" * width + "╗")
        print("║" + " Commandes Disponibles".center(width) + "║")
        print("╠" + "═" * width + "╣")
        for label, desc, alias in rows:
            print(f"║ {label:<{w_label}}  {desc:<{w_desc}}  {alias:<{w_alias}} ║")
        print("╚" + "═" * width + "╝\n")
        return CommandResult.CONTINUE


class QuitCommand(Command):
    name = "quit"
    aliases = ("exit", "q")
    description = "Quitter le programme."
    requires_profile = False

    def execute(self, app, args):
        logger.info("Fermeture du programme demandée par l'utilisateur.")
        print("Au revoir !\n")
        return CommandResult.QUIT
