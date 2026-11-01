"""
Module commands/stats.py
Commande /stats : métriques des derniers échanges (EV3), calculées depuis le journal interaction_logs.
"""
from src.commands.base import Command, CommandResult
from src.galerelm import metrics


class StatsCommand(Command):
    name = "stats"
    description = "Métriques des échanges : volume, latence, erreurs, tokens."
    usage = "[jours]"

    def execute(self, app, args):
        days = (args or "").strip() or "7"
        if not days.isdigit() or int(days) < 1:
            self.error(f"Usage : /{self.name} {self.usage}  (nombre de jours, 7 par défaut)")
            return CommandResult.CONTINUE
        data = metrics.report(app.session, days=int(days), profile_id=app.profile.id)
        self.title(f"Statistiques ({app.profile.name})")
        print(metrics.format_report(data))
        print()
        return CommandResult.CONTINUE
