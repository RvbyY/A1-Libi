def add_calendar_event(title: str, start: str, end: str, attendees: list[str] = []) -> dict:
    """Crée un événement calendrier."""

def list_calendar_events(date_from: str, date_to: str) -> list[dict]:
    """Liste les événements sur une période."""

def cancel_calendar_event(event_id: str) -> bool:
    """Annule un événement."""