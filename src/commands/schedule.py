"""
Module commands/schedule.py
Commande /schedule : planification de tâches IA via ScheduleParser et TaskManager.
"""
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandResult
from src.scheduler.parser import ScheduleParser

if TYPE_CHECKING:
    from src.main import SensAI


class ScheduleCommand(Command):
    name = "schedule"
    description = "Planifier une tâche"
    usage = ScheduleParser.USAGE
    requires_profile = True

    def execute(self, app: "SensAI", args: str) -> CommandResult:
        if not args:
            self.error(f"Usage : {self.usage}")
            return CommandResult.CONTINUE

        try:
            spec = ScheduleParser.parse(args)
        except ValueError as error:
            self.error(str(error))
            return CommandResult.CONTINUE

        task = app.task_manager.create_task(
            profile_id=app.profile.id,
            prompt=spec.prompt,
            scheduled_at=spec.scheduled_at,
            recurrence=spec.recurrence,
        )

        recurrence_label = f" [{task.recurrence}]" if task.recurrence else ""
        self.success(
            f"Tâche planifiée{recurrence_label} pour "
            f"{task.scheduled_at.strftime('%Y-%m-%d %H:%M:%S')} : "
            f"{task.prompt}"
        )
        return CommandResult.CONTINUE