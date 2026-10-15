"""
Module commands/debug.py
Commandes d'inspection : profil, contexte, messages, mémoires, payload.
"""
import json

from src.commands.base import Command, CommandResult
from src.galerelm.models import Chat


class ProfileCommand(Command):
    name = "profile"
    description = "Afficher le profil courant."

    def execute(self, app, args):
        p = app.profile
        self.title("Profil")
        print(f"  ID           : {p.id}")
        print(f"  Nom          : {p.name}")
        print(f"  Email        : {p.email}")
        print(f"  Instructions : {self.preview(p.instructions, 100)}")
        print()
        return CommandResult.CONTINUE


class ContextCommand(Command):
    name = "context"
    description = "Afficher les stats du contexte."

    def execute(self, app, args):
        ctx = app.context
        mem_count = len(ctx.deep_context.memories) if ctx.deep_context else 0
        self.title("Contexte")
        print(f"  ID              : {ctx.id}")
        print(f"  Profile ID      : {ctx.profile_id}")
        print(f"  Messages        : {len(ctx.messages)}/{ctx.context_limit}")
        print(f"  Mémoires LT     : {mem_count}")
        print(f"  Modèle          : {app.model}")
        print()
        return CommandResult.CONTINUE


class MessagesCommand(Command):
    name = "messages"
    aliases = ("msg",)
    description = "Lister les messages du contexte."

    def execute(self, app, args):
        messages = app.context.messages
        if not messages:
            self.info("Aucun message dans le contexte actuel.")
            return CommandResult.CONTINUE

        self.title(f"Messages en contexte ({len(messages)}/{app.context.context_limit})")
        for i, m in enumerate(messages, start=1):
            print(f"  {i}. {self.icon(m.role)} [{m.role}] {self.preview(m.content)}")
        print()
        return CommandResult.CONTINUE


class MemoriesCommand(Command):
    name = "memories"
    aliases = ("mem",)
    description = "Lister les mémoires long terme."

    def execute(self, app, args):
        deep = app.context.deep_context
        if not deep or not deep.memories:
            self.info("Aucune mémoire long terme enregistrée.")
            return CommandResult.CONTINUE

        self.title(f"Mémoires Long Terme ({len(deep.memories)} entrées)")
        for i, mem in enumerate(deep.memories, start=1):
            vec = "✓" if mem.embedding else "✗"
            print(f"  {i}. [{vec}] {self.icon(mem.role)} [{mem.role}] {self.preview(mem.content)}")
        print()
        return CommandResult.CONTINUE


class PayloadCommand(Command):
    name = "payload"
    usage = "[requête]"
    description = "Afficher le payload JSON brut."

    def execute(self, app, args):
        # Avec une requête, on montre aussi le prompt système enrichi par le RAG.
        system_prompt = app._build_augmented_prompt(args) if args else app.profile.instructions
        llm = Chat(
            model=app.model,
            api=app.api,
            messages=app.context.get_messages_copy(),
            system_prompt=system_prompt,
        )
        self.title("Payload JSON")
        print(json.dumps(llm.format(), indent=2, ensure_ascii=False))
        print()
        return CommandResult.CONTINUE
