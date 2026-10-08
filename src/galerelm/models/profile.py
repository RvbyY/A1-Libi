"""
Profile — Profil utilisateur.
Contient les informations de l'utilisateur et ses instructions système personnalisées.
"""
import uuid
import logging

from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship

from src.galerelm.models.base import Base

logger = logging.getLogger("galerelm.models.profile")


class Profile(Base):
    __tablename__ = 'profiles'

    id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: str = Column(String, nullable=False)
    email: str = Column(String, nullable=False, unique=True)
    password: str = Column(String, nullable=False)
    instructions: str = Column(Text, nullable=False)

    contexts = relationship("Context", backref="profile", cascade="all, delete-orphan")
    deep_context = relationship("DeepContext", backref="profile", uselist=False, cascade="all, delete-orphan")

    def __init__(self, name: str, email: str, instructions: str):
        self.id = str(uuid.uuid4())
        self.name = name
        self.email = email
        self.password = ""
        self.instructions = instructions
        logger.info(f"[Profile] Nouveau profil créé : {name} ({email})")

    def format(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "password": self.password,
            "instructions": self.instructions
        }

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        prof = cls(
            name=data.get("name", ""),
            email=data.get("email", ""),
            instructions=data.get("instructions", "")
        )
        if "id" in data:
            prof.id = data["id"]
        if "password" in data:
            prof.password = data["password"]
        return prof
