"""
Module commands/session.py
Commandes de gestion de session : vider ou recréer le contexte.
"""
from src.commands.base import Command, CommandResult
from src.galerelm.models import Context, MessageList


class ClearCommand(Command):
    name = "clear"
    description = "Vider le contexte courant."

    def execute(self, app, args):
        count = len(app.context.messages)
        app.context.messages = MessageList([])
        app.session.commit()
        self.success(f"{count} messages supprimés du contexte.")
        return CommandResult.CONTINUE


class NewCommand(Command):
    name = "new"
    description = "Créer un nouveau contexte vierge."

    def execute(self, app, args):
        limit = app.context.context_limit
        app.context = Context(profile_id=app.profile.id, context_limit=limit)
        app.session.add(app.context)
        app.session.commit()
        self.success(f"Nouveau contexte créé (ID {app.context.id}). Historique vierge.")
        return CommandResult.CONTINUE
