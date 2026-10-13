"""
Module commands/schedule.py
Commande /schedule : planification de tâches IA.
"""
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandResult

if TYPE_CHECKING:
    from src.main import SensAI


class ScheduleCommand(Command):
    name = "schedule"
    description = "Planifier une tâche"
    usage = (
        "at HH:MM <requête> | "
        "in <durée> <requête> | "
        "daily HH:MM <requête> | "
        "weekly <jour> HH:MM <requête> |"
        "every <durée> <requête>"
    )
    requires_profile = True

    _DURATION_FORMATS = "10s, 30m, 2h, 1d"
    _DURATION_UNITS = {
        "s": "seconds",
        "m": "minutes",
        "h": "hours",
        "d": "days",
    }

    _WEEKDAYS = {
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

    def execute(self, app: "SensAI", args: str) -> CommandResult:
        if not args:
            self.error(f"Usage : {self.usage}")
            return CommandResult.CONTINUE

        try:
            scheduled_at, prompt, recurrence = self._parse_schedule(args)
        except ValueError as error:
            self.error(str(error))
            return CommandResult.CONTINUE

        task = app.task_manager.create_task(
            profile_id=app.profile.id,
            prompt=prompt,
            scheduled_at=scheduled_at,
            recurrence=recurrence,
        )

        recurrence_label = f" [{task.recurrence}]" if task.recurrence else ""

        self.success(
            f"Tâche planifiée{recurrence_label} pour "
            f"{task.scheduled_at.strftime('%Y-%m-%d %H:%M:%S')} : "
            f"{task.prompt}"
        )

        return CommandResult.CONTINUE

    def _parse_schedule(self, args: str) -> tuple[datetime, str, str | None]:
        parts = args.split(maxsplit=3)

        if len(parts) < 3:
            raise ValueError(f"Usage : {self.usage}")

        mode = parts[0].lower()

        if mode == "at":
            scheduled_at, prompt = self._parse_at(parts[1], self._join_prompt(parts, 2))
            return scheduled_at, prompt, None

        if mode == "in":
            scheduled_at, prompt = self._parse_in(parts[1], self._join_prompt(parts, 2))
            return scheduled_at, prompt, None

        if mode == "daily":
            scheduled_at, prompt = self._parse_daily(parts)
            return scheduled_at, prompt, "daily"

        if mode == "weekly":
            scheduled_at, prompt, weekday_name = self._parse_weekly(parts)
            return scheduled_at, prompt, f"weekly:{weekday_name}"

        if mode == "every":
            scheduled_at, prompt = self._parse_in(parts[1], self._join_prompt(parts, 2),)
            return scheduled_at, prompt, f"every:{parts[1].lower()}"

        raise ValueError(f"Usage : {self.usage}")

    @staticmethod
    def _join_prompt(parts: list[str], start_index: int) -> str:
        prompt = " ".join(parts[start_index:]).strip()

        if not prompt:
            raise ValueError("La requête planifiée ne peut pas être vide.")

        return prompt

    @staticmethod
    def _parse_at(time_str: str, prompt: str) -> tuple[datetime, str]:
        hour, minute = ScheduleCommand._parse_time(time_str)

        now = datetime.now()
        scheduled_at = now.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )

        if scheduled_at <= now:
            scheduled_at += timedelta(days=1)

        return scheduled_at, prompt

    @staticmethod
    def _parse_time(time_str: str) -> tuple[int, int]:
        try:
            hour, minute = map(int, time_str.split(":"))
        except ValueError:
            raise ValueError("Heure invalide. Format attendu : HH:MM")

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Heure invalide. Format attendu : HH:MM")

        return hour, minute

    @classmethod
    def _parse_in(cls, duration: str, prompt: str) -> tuple[datetime, str]:
        amount, unit = cls._parse_duration(duration)
        delta = timedelta(**{cls._DURATION_UNITS[unit]: amount})

        return datetime.now() + delta, prompt

    @classmethod
    def _parse_duration(cls, duration: str) -> tuple[int, str]:
        if len(duration) < 2:
            raise ValueError(
                f"Durée invalide. Formats attendus : {cls._DURATION_FORMATS}"
            )

        amount_part = duration[:-1]
        unit = duration[-1].lower()

        if unit not in cls._DURATION_UNITS:
            raise ValueError("Unité invalide. Utilisez s, m, h ou d.")

        try:
            amount = int(amount_part)
        except ValueError:
            raise ValueError(
                f"Durée invalide. Formats attendus : {cls._DURATION_FORMATS}"
            )

        if amount <= 0:
            raise ValueError("La durée doit être supérieure à zéro.")

        return amount, unit

    @classmethod
    def _parse_daily(cls, parts: list[str]) -> tuple[datetime, str]:
        if len(parts) < 3:
            raise ValueError("Usage : daily HH:MM <requête>")

        prompt = cls._join_prompt(parts, 2)
        scheduled_at, _ = cls._parse_at(parts[1], prompt)

        return scheduled_at, prompt

    @classmethod
    def _parse_weekly(cls, parts: list[str]) -> tuple[datetime, str, str]:
        if len(parts) < 4:
            raise ValueError("Usage : weekly <jour> HH:MM <requête>")

        weekday_name = parts[1].lower()

        if weekday_name not in cls._WEEKDAYS:
            raise ValueError(
                "Jour invalide. Utilisez monday, tuesday, ..., sunday."
            )

        hour, minute = cls._parse_time(parts[2])
        prompt = cls._join_prompt(parts, 3)

        now = datetime.now()
        target_weekday = cls._WEEKDAYS[weekday_name]

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