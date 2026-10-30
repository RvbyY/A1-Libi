"""
Module commands/session.py
Commandes de gestion de session : vider ou recréer le contexte via SessionManager.
"""
from src.commands.base import Command, CommandResult


class ClearCommand(Command):
    name = "clear"
    description = "Vider le contexte courant."

    def execute(self, app, args):
        count = app.session_manager.clear_context(app.session, app.context)
        self.success(f"{count} messages supprimés du contexte.")
        return CommandResult.CONTINUE


class NewCommand(Command):
    name = "new"
    description = "Créer un nouveau contexte vierge."

    def execute(self, app, args):
        limit = app.context.context_limit
        # Rend l'ancien chat retrouvable depuis le nouveau (RAG)
        archived = app.session_manager.archive_chats(app.session, app.profile, api_client=app.api)
        app.context = app.session_manager.create_new_context(
            app.session,
            profile_id=app.profile.id,
            context_limit=limit,
        )
        self.success(
            f"Nouveau contexte créé (ID {app.context.id}). Historique vierge, "
            f"{archived} message(s) archivé(s) en mémoire longue."
        )
        return CommandResult.CONTINUE
