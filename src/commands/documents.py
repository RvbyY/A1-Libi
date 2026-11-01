"""
Module commands/documents.py
Commandes /ingest et /documents : ajouter des documents locaux à la base de connaissances (R1) et les consulter.
"""
from src.commands.base import Command, CommandResult


class IngestCommand(Command):
    name = "ingest"
    description = "Ajouter un fichier ou un dossier aux documents interrogeables."
    usage = "<chemin>"

    def execute(self, app, args):
        path = (args or "").strip()
        if not path:
            self.error(f"Usage : /{self.name} {self.usage}  (fichiers .md, .txt, .rst, .csv, .json, .yaml, .py, .html)")
            return CommandResult.CONTINUE
        try:
            report = app.chat_engine.documents.ingest(app.session, app.profile.id, path, api_client=app.api)
        except FileNotFoundError as exc:
            self.error(str(exc))
            return CommandResult.CONTINUE
        if not report.files:
            self.error("Aucun fichier texte ingéré." + (" Ignorés : " + "; ".join(report.skipped) if report.skipped else ""))
            return CommandResult.CONTINUE
        message = f"{report.files} fichier(s), {report.chunks} fragment(s) ajoutés ({report.vectorized} vectorisés)."
        if report.vectorized < report.chunks:
            message += " Sans modèle d'embedding, les fragments non vectorisés ne seront pas retrouvés."
        if report.skipped:
            message += " Ignorés : " + "; ".join(report.skipped)
        self.success(message)
        return CommandResult.CONTINUE


class DocumentsCommand(Command):
    name = "documents"
    aliases = ("docs",)
    description = "Lister les documents ingérés, ou en retirer un."
    usage = "[oublier <chemin> | oublier tout]"

    def execute(self, app, args):
        store = app.chat_engine.documents
        words = (args or "").strip().split(maxsplit=1)
        if words and words[0] == "oublier":
            target = words[1] if len(words) > 1 else ""
            if not target:
                self.error(f"Usage : /{self.name} oublier <chemin> | oublier tout")
                return CommandResult.CONTINUE
            count = store.forget(app.session, app.profile.id, None if target == "tout" else target)
            self.success(f"{count} fragment(s) supprimé(s).")
            return CommandResult.CONTINUE

        sources = store.sources(app.session, app.profile.id)
        if not sources:
            self.info("Aucun document. Ajoutez-en avec /ingest <chemin>.")
            return CommandResult.CONTINUE
        self.title(f"Documents ({len(sources)})")
        for source, count in sources:
            print(f"  {source}  ({count} fragment(s))")
        print()
        return CommandResult.CONTINUE
