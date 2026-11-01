"""
Module commands/persona.py
Commande /persona : lister les agents disponibles et changer d'agent en cours de session (A5).
L'historique de la conversation est gardé : seul le prompt système des prochains messages change.
"""
from src.commands.base import Command, CommandResult
from src.config import ConfigError, config


class PersonaCommand(Command):
    name = "persona"
    aliases = ("agent",)
    description = "Lister les agents ou changer d'agent."
    usage = "[nom]"
    requires_profile = False

    def execute(self, app, args):
        key = (args or "").strip()
        if not key:
            self.show(app)
            return CommandResult.CONTINUE
        try:
            persona = app.set_persona(key)
        except ConfigError as exc:
            self.error(str(exc))
            return CommandResult.CONTINUE
        self.success(f"Agent : {persona['name']}. L'historique de la conversation est conservé.")
        return CommandResult.CONTINUE

    @staticmethod
    def show(app) -> None:
        current = (app.chat_engine.persona or {}).get("key")
        print("\nAgents disponibles (/persona <nom> pour changer) :")
        width = max(len(key) for key in config.PERSONAS)
        for key, spec in config.PERSONAS.items():
            marker = "*" if key == current else " "
            print(f"  {marker} {key.ljust(width)}  {spec['name']} : {spec['description']}")
        print()
