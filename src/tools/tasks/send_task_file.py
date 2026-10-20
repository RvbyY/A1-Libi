"""
Module send_task_file.py
Outil permettant au LLM d'exporter la liste des tâches planifiées de l'utilisateur dans un fichier JSON.
"""
import json
from pathlib import Path

from src.galerelm.models.scheduled_task import ScheduledTask
from ..ITools import ToolContext, ToolResult, ToolsInterface


class SendTaskFileTool(ToolsInterface):
    """Exporte les tâches planifiées de l'utilisateur dans un fichier JSON."""

    @property
    def name(self) -> str:
        return "send_task_file"

    @property
    def description(self) -> str:
        return "Export the current user's scheduled tasks to a JSON file."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Target file path for the exported JSON tasks (default: tasks_export.json).",
                },
                "status_filter": {
                    "type": "string",
                    "enum": ["all", "pending", "completed", "cancelled", "failed"],
                    "description": "Optional status filter (default: all).",
                },
            },
            "required": [],
        }

    def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        file_path = str(arguments.get("file_path", "tasks_export.json")).strip()
        status_filter = str(arguments.get("status_filter", "all")).lower()

        session = context.session
        if session is None and context.task_manager is not None:
            session = context.task_manager.session
        if session is None:
            return ToolResult(False, "No database session available in ToolContext.")

        query = session.query(ScheduledTask).filter_by(profile_id=context.user_id)
        if status_filter != "all":
            query = query.filter_by(status=status_filter)

        tasks = query.all()
        serialized = [
            {
                "id": t.id,
                "prompt": t.prompt,
                "scheduled_at": t.scheduled_at.isoformat() if t.scheduled_at else None,
                "recurrence": t.recurrence,
                "status": t.status,
            }
            for t in tasks
        ]

        try:
            target = Path(file_path)
            target.write_text(json.dumps(serialized, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            return ToolResult(False, f"Failed to write tasks file: {exc}")

        return ToolResult(
            True,
            f"Exported {len(serialized)} task(s) to {file_path}.",
            {"file_path": str(target), "count": len(serialized), "tasks": serialized},
        )
