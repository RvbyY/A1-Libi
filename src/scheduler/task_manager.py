from datetime import datetime
from typing import Optional

from src.galerelm.models.scheduled_task import ScheduledTask
from src.scheduler.parser import ScheduleParser


class TaskManager:
    """Gère la persistance et le cycle de vie des tâches planifiées (ScheduledTask)."""

    def __init__(self, session):
        self.session = session

    def create_task(
        self,
        profile_id: str,
        prompt: str,
        scheduled_at: datetime,
        recurrence: Optional[str] = None,
    ) -> ScheduledTask:
        task = ScheduledTask(
            profile_id=profile_id,
            prompt=prompt,
            scheduled_at=scheduled_at,
            recurrence=recurrence,
            status="pending",
        )
        self.session.add(task)
        self.session.commit()
        return task

    def get_due_tasks(self) -> list[ScheduledTask]:
        return (
            self.session.query(ScheduledTask)
            .filter(
                ScheduledTask.status == "pending",
                ScheduledTask.scheduled_at <= datetime.now(),
            )
            .all()
        )

    def cancel_task(self, task: ScheduledTask) -> None:
        task.status = "cancelled"
        self.session.commit()

    def mark_completed(self, task: ScheduledTask) -> None:
        task.status = "completed"
        self.session.commit()

    def mark_failed(self, task: ScheduledTask) -> None:
        task.status = "failed"
        self.session.commit()

    def reschedule_recurring_task(self, task: ScheduledTask) -> None:
        next_dt = ScheduleParser.next_occurrence(task.scheduled_at, task.recurrence)
        if next_dt is not None:
            task.scheduled_at = next_dt
            task.status = "pending"
            self.session.commit()
            return

        self.mark_completed(task)