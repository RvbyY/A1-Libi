"""
Module commands/schedule.py
Commande /schedule : planification de tâches IA.
"""
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandResult

if TYPE_CHECKING:
    from src.main import SensAI


class ScheduleCommand(Command):
    name = "schedule"
    description = "Planifier une tâche"
    usage = "at HH:MM <requête>"
    requires_profile = True

    def execute(self, app: "SensAI", args: str) -> CommandResult:
        if not args:
            self.error(f"Usage : {self.usage}")
            return CommandResult.CONTINUE

        parts = args.split(maxsplit=2)

        if len(parts) < 3 or parts[0].lower() != "at":
            self.error(f"Usage : {self.usage}")
            return CommandResult.CONTINUE

        time_str = parts[1]
        prompt = parts[2]

        try:
            hour, minute = map(int, time_str.split(":"))
        except ValueError:
            self.error("Heure invalide. Format attendu : HH:MM")
            return CommandResult.CONTINUE

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            self.error("Heure invalide. Format attendu : HH:MM")
            return CommandResult.CONTINUE

        now = datetime.now()
        scheduled_at = now.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )

        if scheduled_at <= now:
            scheduled_at += timedelta(days=1)

        task = app.task_manager.create_task(
            profile_id=app.profile.id,
            prompt=prompt,
            scheduled_at=scheduled_at,
        )

        self.success(
            f"Tâche planifiée pour "
            f"{task.scheduled_at.strftime('%Y-%m-%d %H:%M')} : "
            f"{task.prompt}"
        )

        return CommandResult.CONTINUE