"""
ScheduledTask — Tâche planifiée associée à un profil utilisateur.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, ForeignKey

from src.galerelm.models.base import Base


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id: str = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    profile_id: str = Column(
        String,
        ForeignKey("profiles.id"),
        nullable=False
    )

    prompt: str = Column(
        Text,
        nullable=False
    )

    scheduled_at: datetime = Column(
        DateTime,
        nullable=False
    )

    recurrence: str = Column(
        String,
        nullable=True
    )

    status: str = Column(
        String,
        nullable=False,
        default="pending"
    )

    created_at: datetime = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )