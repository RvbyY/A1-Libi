from collections.abc import Callable
from datetime import datetime
from typing import Any

from ..ITools import ToolContext, ToolResult, ToolsInterface
from ...galerelm.models import ScheduledTask


class CreateTask(ToolsInterface):
    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    @property
    def name(self) -> str:
        return "create_task"

    @property
    def description(self) -> str:
        return "Create a scheduled task."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Prompt to execute when the task is due.",
                },
                "scheduled_at": {
                    "type": "string",
                    "description": "Execution date in ISO 8601 format.",
                },
                "recurrence": {
                    "type": "string",
                    "description": "Optional recurrence: daily, weekly:<day>, or every:<duration>.",
                },
            },
            "required": ["prompt", "scheduled_at"],
        }

    def create_task(
        self,
        context: ToolContext,
        prompt: str,
        scheduled_at: str,
        recurrence: str | None = None,
    ) -> dict:
        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string.")
        if not prompt.strip():
            raise ValueError("prompt is required.")

        try:
            schedule = datetime.fromisoformat(scheduled_at)
        except ValueError as exc:
            raise ValueError("scheduled_at must be a valid ISO 8601 date.") from exc

        with self._session_factory() as session:
            task = ScheduledTask(
                profile_id=context.user_id,
                prompt=prompt.strip(),
                scheduled_at=schedule,
                recurrence=recurrence,
                status="pending",
            )
            session.add(task)
            session.commit()
            return self._serialize(task)

    def execute(self, context: ToolContext, payload: dict) -> ToolResult:
        try:
            prompt = payload.get("prompt")
            scheduled_at = payload.get("scheduled_at")
            recurrence = payload.get("recurrence")
            if not isinstance(prompt, str):
                raise TypeError("prompt is required.")
            if not isinstance(scheduled_at, str):
                raise TypeError("scheduled_at is required.")
            if recurrence is not None and not isinstance(recurrence, str):
                raise ValueError("recurrence must be a string.")

            task = self.create_task(context, prompt, scheduled_at, recurrence)
            return ToolResult(True, f"Task {task['id']} created.", task)
        except (TypeError, ValueError) as exc:
            return ToolResult(False, str(exc))

    @staticmethod
    def _serialize(task: ScheduledTask) -> dict:
        return {
            "id": task.id,
            "profile_id": task.profile_id,
            "prompt": task.prompt,
            "scheduled_at": task.scheduled_at.isoformat(),
            "recurrence": task.recurrence,
            "status": task.status,
        }
