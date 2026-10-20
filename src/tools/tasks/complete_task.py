"""
Module complete_task.py
Outil permettant au LLM de marquer une tâche planifiée comme terminée ou annulée.
"""
from typing import Optional

from src.galerelm.models.scheduled_task import ScheduledTask
from src.scheduler.task_manager import TaskManager
from ..ITools import ToolContext, ToolResult, ToolsInterface


class CompleteTaskTool(ToolsInterface):
    """Marque une tâche planifiée de l'utilisateur comme terminée ou annulée."""

    @property
    def name(self) -> str:
        return "complete_task"

    @property
    def description(self) -> str:
        return "Mark a scheduled task as completed or cancelled by its task ID."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ID of the scheduled task to update.",
                },
                "action": {
                    "type": "string",
                    "enum": ["complete", "cancel"],
                    "description": "Whether to mark the task as completed or cancelled (default: complete).",
                },
            },
            "required": ["task_id"],
        }

    @staticmethod
    def _resolve_task_manager(context: ToolContext) -> Optional[TaskManager]:
        if context.task_manager is not None:
            return context.task_manager
        if context.session is not None:
            return TaskManager(context.session)
        return None

    def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        task_id = str(arguments.get("task_id", "")).strip()
        action = str(arguments.get("action", "complete")).lower()

        if not task_id:
            return ToolResult(False, "task_id is required.")
        if action not in {"complete", "cancel"}:
            return ToolResult(False, "action must be 'complete' or 'cancel'.")

        manager = self._resolve_task_manager(context)
        if manager is None:
            return ToolResult(False, "No database session or TaskManager available in ToolContext.")

        task = (
            manager.session.query(ScheduledTask)
            .filter_by(id=task_id, profile_id=context.user_id)
            .first()
        )
        if task is None:
            return ToolResult(False, f"Scheduled task {task_id} not found.")

        if action == "cancel":
            manager.cancel_task(task)
            return ToolResult(True, f"Task {task_id} cancelled.", {"id": task_id, "status": task.status})

        manager.mark_completed(task)
        return ToolResult(True, f"Task {task_id} marked as completed.", {"id": task_id, "status": task.status})
