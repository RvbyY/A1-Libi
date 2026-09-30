from typing import Optional

class calendar_setup:
    calendar: Optional[dict] = None

    def __init__(self, calendar):
        self.calendar = calendar

    def save_event(self, event: dict):
        if not hasattr(calendar_setup.save_event, 'id'):
            calendar_setup.save_event.id = 0
        self.calendar.update({
            "id": id,
            "event": event
        })
        calendar_setup.save_event.id += 1
        return 0

    def add_calendar_event(self, title: str, start: str, end: str, attendees: list[str] = []) -> dict:
        """Crée un événement calendrier."""
        if not hasattr(calendar_setup.add_calendar_event, 'id'):
            calendar_setup.add_calendar_event.id = 0
        event = {
            "id": calendar_setup.add_calendar_event.id,
            "title": title,
            "start": start,
            "end": end,
            "attendees": attendees,
            "status": dict.fromkeys(attendees, "pending")
        }

        calendar_setup.save_event(self, event)
        for a in attendees:
            send_notification(user_id=a, message=f"Invitation: {title} le {start}")
        calendar_setup.add_calendar_event.id += 1
        return event

def list_calendar_events(date_from: str, date_to: str) -> list[dict]:
    """Liste les événements sur une période."""

def cancel_calendar_event(event_id: str) -> bool:
    """Annule un événement."""