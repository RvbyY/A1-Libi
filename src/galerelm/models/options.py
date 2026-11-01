"""
Modèle Options.
Paramètres de génération du LLM (temperature, top_k, etc.).
"""
from typing import Union

from sqlalchemy import Column, Integer, Float, ForeignKey, JSON

from src.config import config
from src.galerelm.models.base import Base


class Options(Base):
    __tablename__ = "options"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    context_id: int = Column(Integer, ForeignKey("contexts.id"), nullable=True)

    seed: int = Column(Integer)
    temperature: float = Column(Float)
    top_k: int = Column(Integer)
    top_p: float = Column(Float)
    min_p: float = Column(Float)
    stop: Union[str, list[str]] = Column(JSON)
    num_ctx: int = Column(Integer)
    num_predict: int = Column(Integer)

    PARAMS = ("seed", "temperature", "top_k", "top_p", "min_p", "stop", "num_ctx", "num_predict")

    def __init__(self, seed: int = None, temperature: float = None, top_k: int = None, top_p: float = None,
                 min_p: float = None, stop: Union[str, list[str]] = None, num_ctx: int = None,
                 num_predict: int = None, profile: str = "chat"):
        """
        Les paramètres non fournis prennent la valeur du profil de génération (config.GENERATION),
        lui-même réglable dans config.yaml, en CLI ou avec /params. Voir docs/15-parametres-generation.md.
        """
        defaults = config.generation_options(profile)
        given = {"seed": seed, "temperature": temperature, "top_k": top_k, "top_p": top_p, "min_p": min_p,
                 "stop": stop, "num_ctx": num_ctx, "num_predict": num_predict}
        for key in self.PARAMS:
            setattr(self, key, given[key] if given[key] is not None else defaults[key])

    @classmethod
    def from_profile(cls, profile: str) -> "Options":
        """Paramètres actuels d'un profil : 'chat', 'judge' ou 'guardrail'."""
        return cls(profile=profile)

    def format(self) -> dict:
        """Charge utile 'options' pour Ollama. Une graine absente ou une liste stop vide ne sont pas envoyées."""
        payload = {key: getattr(self, key) for key in self.PARAMS}
        if payload["seed"] is None:
            del payload["seed"]
        if not payload["stop"]:
            del payload["stop"]
        return payload

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(**{key: data.get(key) for key in cls.PARAMS})
