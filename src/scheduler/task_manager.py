from datetime import datetime

from src.galerelm.models.scheduled_task import ScheduledTask


class TaskManager:
    def __init__(self, session):
        self.session = session

    def create_task(
        self,
        profile_id: str,
        prompt: str,
        scheduled_at: datetime,
        recurrence: str | None = None,
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

    def get_due_tasks(self):
        return (
            self.session.query(ScheduledTask)
            .filter(
                ScheduledTask.status == "pending",
                ScheduledTask.scheduled_at <= datetime.now(),
            )
            .all()
        )

    def cancel_task(self, task: ScheduledTask):
        task.status = "cancelled"
        self.session.commit()

    def mark_completed(self, task: ScheduledTask):
        task.status = "completed"
        self.session.commit()

    def mark_failed(self, task: ScheduledTask):
        task.status = "failed"
        self.session.commit()