"""
Module scheduler/parser.py
Encapsule l'analyse syntaxique des expressions de planification (dates, heures, durées, récurrences)
dans une classe dédiée ScheduleParser réutilisable par les commandes CLI, TaskManager et les outils LLM.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class ScheduleSpec:
    """Représentation structurée d'une planification analysée."""
    scheduled_at: datetime
    prompt: str
    recurrence: Optional[str] = None


class ScheduleParser:
    """
    Parseur d'expressions temporelles et de récurrences pour le planificateur SensAI.
    """

    USAGE = (
        "at HH:MM <requête> | "
        "in <durée> <requête> | "
        "daily HH:MM <requête> | "
        "weekly <jour> HH:MM <requête> | "
        "every <durée> <requête>"
    )

    DURATION_FORMATS = "10s, 30m, 2h, 1d"
    DURATION_UNITS = {
        "s": "seconds",
        "m": "minutes",
        "h": "hours",
        "d": "days",
    }

    WEEKDAYS = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
        "lundi": 0,
        "mardi": 1,
        "mercredi": 2,
        "jeudi": 3,
        "vendredi": 4,
        "samedi": 5,
        "dimanche": 6,
    }

    @classmethod
    def parse(cls, args: str) -> ScheduleSpec:
        """Analyse une expression complète de commande /schedule et retourne un ScheduleSpec."""
        parts = args.split(maxsplit=3)
        if len(parts) < 3:
            raise ValueError(f"Usage : {cls.USAGE}")

        mode = parts[0].lower()

        if mode == "at":
            scheduled_at, prompt = cls.parse_at(parts[1], cls._join_prompt(parts, 2))
            return ScheduleSpec(scheduled_at=scheduled_at, prompt=prompt, recurrence=None)

        if mode == "in":
            scheduled_at, prompt = cls.parse_in(parts[1], cls._join_prompt(parts, 2))
            return ScheduleSpec(scheduled_at=scheduled_at, prompt=prompt, recurrence=None)

        if mode == "daily":
            scheduled_at, prompt = cls.parse_daily(parts)
            return ScheduleSpec(scheduled_at=scheduled_at, prompt=prompt, recurrence="daily")

        if mode == "weekly":
            scheduled_at, prompt, weekday_name = cls.parse_weekly(parts)
            return ScheduleSpec(
                scheduled_at=scheduled_at,
                prompt=prompt,
                recurrence=f"weekly:{weekday_name}",
            )

        if mode == "every":
            scheduled_at, prompt = cls.parse_in(parts[1], cls._join_prompt(parts, 2))
            return ScheduleSpec(
                scheduled_at=scheduled_at,
                prompt=prompt,
                recurrence=f"every:{parts[1].lower()}",
            )

        raise ValueError(f"Usage : {cls.USAGE}")

    @staticmethod
    def _join_prompt(parts: list[str], start_index: int) -> str:
        prompt = " ".join(parts[start_index:]).strip()
        if not prompt:
            raise ValueError("La requête planifiée ne peut pas être vide.")
        return prompt

    @classmethod
    def parse_time(cls, time_str: str) -> tuple[int, int]:
        """Analyse une chaîne HH:MM et retourne (hour, minute)."""
        try:
            hour, minute = map(int, time_str.split(":"))
        except ValueError:
            raise ValueError("Heure invalide. Format attendu : HH:MM")

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Heure invalide. Format attendu : HH:MM")

        return hour, minute

    @classmethod
    def parse_duration(cls, duration: str) -> tuple[int, str]:
        """Analyse une durée courte (ex: 10s, 30m, 2h, 1d) et retourne (amount, unit)."""
        if not duration or len(duration) < 2:
            raise ValueError(f"Durée invalide. Formats attendus : {cls.DURATION_FORMATS}")

        amount_part = duration[:-1]
        unit = duration[-1].lower()

        if unit not in cls.DURATION_UNITS:
            raise ValueError("Unité invalide. Utilisez s, m, h ou d.")

        try:
            amount = int(amount_part)
        except ValueError:
            raise ValueError(f"Durée invalide. Formats attendus : {cls.DURATION_FORMATS}")

        if amount <= 0:
            raise ValueError("La durée doit être supérieure à zéro.")

        return amount, unit

    @classmethod
    def duration_to_delta(cls, duration: str) -> timedelta:
        """Convertit une chaîne de durée (ex: '30m') en objet timedelta."""
        amount, unit = cls.parse_duration(duration)
        return timedelta(**{cls.DURATION_UNITS[unit]: amount})

    @classmethod
    def parse_at(cls, time_str: str, prompt: str) -> tuple[datetime, str]:
        hour, minute = cls.parse_time(time_str)
        now = datetime.now()
        scheduled_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled_at <= now:
            scheduled_at += timedelta(days=1)
        return scheduled_at, prompt

    @classmethod
    def parse_in(cls, duration: str, prompt: str) -> tuple[datetime, str]:
        delta = cls.duration_to_delta(duration)
        return datetime.now() + delta, prompt

    @classmethod
    def parse_daily(cls, parts: list[str]) -> tuple[datetime, str]:
        if len(parts) < 3:
            raise ValueError("Usage : daily HH:MM <requête>")
        prompt = cls._join_prompt(parts, 2)
        scheduled_at, _ = cls.parse_at(parts[1], prompt)
        return scheduled_at, prompt

    @classmethod
    def parse_weekly(cls, parts: list[str]) -> tuple[datetime, str, str]:
        if len(parts) < 4:
            raise ValueError("Usage : weekly <jour> HH:MM <requête>")

        weekday_name = parts[1].lower()
        if weekday_name not in cls.WEEKDAYS:
            raise ValueError("Jour invalide. Utilisez monday, tuesday, ..., sunday.")

        hour, minute = cls.parse_time(parts[2])
        prompt = cls._join_prompt(parts, 3)

        now = datetime.now()
        target_weekday = cls.WEEKDAYS[weekday_name]
        days_ahead = target_weekday - now.weekday()
        if days_ahead < 0:
            days_ahead += 7

        scheduled_at = (now + timedelta(days=days_ahead)).replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
        if scheduled_at <= now:
            scheduled_at += timedelta(days=7)

        return scheduled_at, prompt, weekday_name

    @classmethod
    def parse_datetime_or_relative(cls, value: str) -> datetime:
        """
        Analyse une date ISO 8601, une heure HH:MM ou une durée relative ('30m' ou 'in 30m').
        """
        cleaned = value.strip()
        if cleaned.lower().startswith("in "):
            cleaned = cleaned[3:].strip()

        try:
            return datetime.fromisoformat(cleaned)
        except ValueError:
            pass

        if ":" in cleaned:
            dt, _ = cls.parse_at(cleaned, "_")
            return dt

        return datetime.now() + cls.duration_to_delta(cleaned)

    @classmethod
    def next_occurrence(cls, current_scheduled_at: datetime, recurrence: Optional[str]) -> Optional[datetime]:
        """Calcule la prochaine date d'exécution pour une tâche récurrente, ou None si ponctuelle."""
        if not recurrence:
            return None
        if recurrence == "daily":
            return current_scheduled_at + timedelta(days=1)
        if recurrence.startswith("weekly:"):
            return current_scheduled_at + timedelta(days=7)
        if recurrence.startswith("every:"):
            duration = recurrence.removeprefix("every:")
            return datetime.now() + cls.duration_to_delta(duration)
        return None
