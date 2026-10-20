from collections.abc import Callable
from contextlib import nullcontext
from typing import Any

from ..ITools import ToolContext, ToolResult, ToolsInterface
from ...galerelm.models import ScheduledTask


class CompleteTask(ToolsInterface):
    def __init__(self, session_factory: Callable[[], Any] | None = None) -> None:
        self._session_factory = session_factory

    @property
    def name(self) -> str:
        return "complete_task"

    @property
    def description(self) -> str:
        return "Mark a scheduled task as completed."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ID of the scheduled task.",
                },
            },
            "required": ["task_id"],
        }

    def complete_task(self, context: ToolContext, task_id: str) -> dict:
        with self._session_context(context) as session:
            task = self._get_owned_task(session, context, task_id)
            if task.status == "cancelled":
                raise ValueError("A cancelled task cannot be completed.")

            task.status = "completed"
            session.commit()
            return self._serialize(task)

    def execute(self, context: ToolContext, payload: dict) -> ToolResult:
        try:
            task_id = payload.get("task_id")
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("task_id is required.")

            task = self.complete_task(context, task_id)
            return ToolResult(True, f"Task {task_id} completed.", task)
        except (TypeError, ValueError) as exc:
            return ToolResult(False, str(exc))

    @staticmethod
    def _get_owned_task(session: Any, context: ToolContext, task_id: str) -> ScheduledTask:
        task = (
            session.query(ScheduledTask)
            .filter_by(id=task_id, profile_id=context.user_id)
            .first()
        )
        if task is None:
            raise ValueError("Task not found.")
        return task

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

    def _session_context(self, context: ToolContext):
        if self._session_factory is not None:
            return self._session_factory()
        if context.session is None:
            raise RuntimeError("A database session is required.")
        return nullcontext(context.session)


CompleteTaskTool = CompleteTask
