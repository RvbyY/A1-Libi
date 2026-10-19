from datetime import datetime
from typing import Any

from ..ITools import ToolContext, ToolResult, ToolsInterface


class Calendar(ToolsInterface):
    """In-memory calendar tool scoped to the current user."""

    def __init__(self, calendar: dict[str, dict[str, Any]] | None = None) -> None:
        self.calendar = calendar if calendar is not None else {}
        self._next_event_id = 0

    @property
    def name(self) -> str:
        return "calendar"

    @property
    def description(self) -> str:
        return "Create, list, and cancel calendar events for the current user."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "cancel"],
                    "description": "Calendar operation to perform.",
                },
                "title": {
                    "type": "string",
                    "description": "Event title, required for add.",
                },
                "start": {
                    "type": "string",
                    "description": "Event start in ISO 8601 format, required for add.",
                },
                "end": {
                    "type": "string",
                    "description": "Event end in ISO 8601 format, required for add.",
                },
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional attendee IDs for add.",
                },
                "date_from": {
                    "type": "string",
                    "description": "Period start in ISO 8601 format, required for list.",
                },
                "date_to": {
                    "type": "string",
                    "description": "Period end in ISO 8601 format, required for list.",
                },
                "event_id": {
                    "type": "string",
                    "description": "Event ID, required for cancel.",
                },
            },
            "required": ["action"],
        }

    @staticmethod
    def _parse_datetime(value: str, field_name: str) -> datetime:
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a valid ISO 8601 date.") from exc

    def _add_event(self, context: ToolContext, payload: dict) -> dict:
        title = payload.get("title")
        start = payload.get("start")
        end = payload.get("end")
        if not isinstance(title, str) or not title:
            raise ValueError("title is required to add an event.")
        if not isinstance(start, str) or not isinstance(end, str):
            raise ValueError("start and end are required to add an event.")

        start_date = self._parse_datetime(start, "start")
        end_date = self._parse_datetime(end, "end")
        if end_date <= start_date:
            raise ValueError("end must be after start.")

        event_id = str(self._next_event_id)
        self._next_event_id += 1
        event = {
            "id": event_id,
            "owner_id": context.user_id,
            "title": title,
            "start": start,
            "end": end,
            "attendees": payload.get("attendees", []),
            "status": "confirmed",
        }
        self.calendar[event_id] = event
        return event

    def _list_events(self, context: ToolContext, payload: dict) -> list[dict]:
        date_from = payload.get("date_from")
        date_to = payload.get("date_to")
        if not isinstance(date_from, str) or not isinstance(date_to, str):
            raise ValueError("date_from and date_to are required to list events.")

        period_start = self._parse_datetime(date_from, "date_from")
        period_end = self._parse_datetime(date_to, "date_to")
        if period_end < period_start:
            raise ValueError("date_to must be after date_from.")

        return [
            event
            for event in self.calendar.values()
            if event["owner_id"] == context.user_id
            and self._parse_datetime(event["start"], "start") <= period_end
            and self._parse_datetime(event["end"], "end") >= period_start
        ]

    def _cancel_event(self, context: ToolContext, payload: dict) -> bool:
        event_id = payload.get("event_id")
        if not isinstance(event_id, str):
            raise ValueError("event_id is required to cancel an event.")

        event = self.calendar.get(event_id)
        if event is None or event["owner_id"] != context.user_id:
            return False
        del self.calendar[event_id]
        return True

    def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        action = arguments.get("action")
        try:
            if action == "add":
                event = self._add_event(context, arguments)
                return ToolResult(True, f"Calendar event {event['id']} created.", event)
            if action == "list":
                events = self._list_events(context, arguments)
                return ToolResult(True, f"Found {len(events)} calendar event(s).", events)
            if action == "cancel":
                cancelled = self._cancel_event(context, arguments)
                if not cancelled:
                    return ToolResult(False, "Calendar event not found.")
                return ToolResult(True, f"Calendar event {arguments['event_id']} cancelled.")
            return ToolResult(False, "action must be one of: add, list, cancel.")
        except ValueError as exc:
            return ToolResult(False, str(exc))
