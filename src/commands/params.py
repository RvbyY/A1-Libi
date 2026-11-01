"""
Module commands/params.py
Commande /params : afficher et modifier les paramètres de génération pendant la session.
Documentation : docs/15-parametres-generation.md.
"""
from src.commands.base import Command, CommandResult
from src.config import GENERATION_PARAMS, GENERATION_PROFILES, ConfigError, config


class ParamsCommand(Command):
    name = "params"
    description = "Afficher ou modifier les paramètres de génération."
    usage = "[profil.]paramètre valeur | reset"
    requires_profile = False

    def execute(self, app, args):
        args = (args or "").strip()
        if not args:
            self.show(app)
            return CommandResult.CONTINUE

        if args == "reset":
            config.reset_generation()
            self.success("Paramètres de génération du démarrage restaurés.")
            self.show(app)
            return CommandResult.CONTINUE

        parts = args.split(maxsplit=1)
        if len(parts) != 2:
            self.error(f"Usage : /params {self.usage}  (ex : /params temperature 0.2, /params judge.num_predict 200)")
            return CommandResult.CONTINUE

        target, value = parts
        profile, _, key = target.rpartition(".")
        profile = profile or "chat"
        try:
            stored = config.set_generation(profile, key, value, "/params")
        except ConfigError as exc:
            self.error(str(exc))
            return CommandResult.CONTINUE

        self.success(f"{profile}.{key} = {stored!r} (appliqué aux prochains appels du modèle).")
        return CommandResult.CONTINUE

    @staticmethod
    def show(app) -> None:
        """Tableau des paramètres : une ligne par paramètre, une colonne par profil."""
        def cell(value) -> str:
            if value is None:
                return "aléatoire"
            if isinstance(value, list):
                return ",".join(value) or "-"
            return str(value)

        rows = [("paramètre", *GENERATION_PROFILES)]
        for key in GENERATION_PARAMS:
            rows.append((key, *(cell(config.GENERATION[profile][key]) for profile in GENERATION_PROFILES)))
        widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]

        print(f"\nModèle : {app.model} | keep_alive : {config.keep_alive}")
        for index, row in enumerate(rows):
            print("  " + "  ".join(value.ljust(widths[i]) for i, value in enumerate(row)))
            if index == 0:
                print("  " + "  ".join("-" * width for width in widths))
        print()
