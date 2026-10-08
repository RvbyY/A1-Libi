from datetime import datetime, timedelta

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

    def reschedule_recurring_task(self, task: ScheduledTask):
        if task.recurrence == "daily":
            task.scheduled_at = task.scheduled_at + timedelta(days=1)
            task.status = "pending"
            self.session.commit()
            return

        if task.recurrence and task.recurrence.startswith("weekly:"):
            task.scheduled_at = task.scheduled_at + timedelta(days=7)
            task.status = "pending"
            self.session.commit()
            return

        if task.recurrence and task.recurrence.startswith("every:"):
            duration = task.recurrence.removeprefix("every:")
            task.scheduled_at = datetime.now() + self._duration_to_delta(duration)
            task.status = "pending"
            self.session.commit()
            return

        self.mark_completed(task)

    @staticmethod
    def _duration_to_delta(duration: str) -> timedelta:
        if len(duration) < 2:
            raise ValueError("Invalid recurrence duration")

        amount_part = duration[:-1]
        unit = duration[-1].lower()

        amount = int(amount_part)

        if amount <= 0:
            raise ValueError("Recurrence duration must be positive")

        if unit == "s":
            return timedelta(seconds=amount)

        if unit == "m":
            return timedelta(minutes=amount)

        if unit == "h":
            return timedelta(hours=amount)

        if unit == "d":
            return timedelta(days=amount)

        raise ValueError("Invalid recurrence unit")