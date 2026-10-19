"""
Module commands/memory.py
Commandes liées à la mémoire long terme (RAG).
"""
from src.commands.base import Command, CommandResult


class RecallCommand(Command):
    name = "recall"
    usage = "<requête>"
    description = "Rechercher dans la mémoire long terme."
    top_k = 5

    def execute(self, app, args):
        if not args:
            self.error(f"Usage : /{self.name} {self.usage}")
            return CommandResult.CONTINUE

        deep = app.context.deep_context
        if not deep or not deep.memories:
            self.info("Aucune mémoire long terme enregistrée.")
            return CommandResult.CONTINUE

        results = deep.search(args, app.api, top_k=self.top_k)
        if not results:
            self.info("Aucun résultat pertinent trouvé.")
            return CommandResult.CONTINUE

        self.title(f"Résultats RAG pour \"{args}\" ({len(results)} trouvés)")
        for i, (score, mem) in enumerate(results, start=1):
            print(f"  {i}. {self.icon(mem.role)} [{mem.role}] (score: {score:.4f}) {self.preview(mem.content, 100)}")
        print()
        return CommandResult.CONTINUE
