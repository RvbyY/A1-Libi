"""
Module create_task.py
Outil permettant au LLM de planifier une tâche différée ou récurrente via TaskManager.
"""
from datetime import datetime
from typing import Optional

from src.scheduler.task_manager import TaskManager
from ..ITools import ToolContext, ToolResult, ToolsInterface


class CreateTaskTool(ToolsInterface):
    """Crée une tâche planifiée associée à l'utilisateur courant."""

    @property
    def name(self) -> str:
        return "create_task"

    @property
    def description(self) -> str:
        return "Create a scheduled or recurring task for the current user."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The instruction or prompt to execute at the scheduled time.",
                },
                "scheduled_at": {
                    "type": "string",
                    "description": "Execution date and time in ISO 8601 format (e.g. 2026-10-20T14:30:00).",
                },
                "recurrence": {
                    "type": "string",
                    "description": "Optional recurrence rule (e.g. 'daily', 'weekly:monday', 'every:30m').",
                },
            },
            "required": ["prompt", "scheduled_at"],
        }

    @staticmethod
    def _resolve_task_manager(context: ToolContext) -> Optional[TaskManager]:
        if context.task_manager is not None:
            return context.task_manager
        if context.session is not None:
            return TaskManager(context.session)
        return None

    def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        prompt = str(arguments.get("prompt", "")).strip()
        scheduled_at_str = str(arguments.get("scheduled_at", "")).strip()
        recurrence = arguments.get("recurrence")

        if not prompt:
            return ToolResult(False, "prompt is required to create a task.")
        if not scheduled_at_str:
            return ToolResult(False, "scheduled_at is required in ISO 8601 format.")

        try:
            scheduled_at = datetime.fromisoformat(scheduled_at_str)
        except ValueError:
            return ToolResult(False, "scheduled_at must be a valid ISO 8601 datetime.")

        manager = self._resolve_task_manager(context)
        if manager is None:
            return ToolResult(False, "No database session or TaskManager available in ToolContext.")

        task = manager.create_task(
            profile_id=context.user_id,
            prompt=prompt,
            scheduled_at=scheduled_at,
            recurrence=str(recurrence) if recurrence else None,
        )
        return ToolResult(
            True,
            f"Scheduled task {task.id} created for {task.scheduled_at.isoformat()}.",
            {
                "id": task.id,
                "prompt": task.prompt,
                "scheduled_at": task.scheduled_at.isoformat(),
                "recurrence": task.recurrence,
                "status": task.status,
            },
        )
