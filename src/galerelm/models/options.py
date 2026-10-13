"""
Modèle Options.
Paramètres de génération du LLM (temperature, top_k, etc.).
"""
from typing import Union

from sqlalchemy import Column, Integer, Float, ForeignKey, JSON

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

    def __init__(self, seed: int = 0, temperature: float = 0.7, top_k: int = 40, top_p: float = 0.9, min_p: float = 0.05,
                 stop: Union[str, list[str]] = None, num_ctx: int = 4096, num_predict: int = 512):
        self.seed = seed
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p
        self.min_p = min_p
        self.stop = stop if stop is not None else ["\nuser:", "</s>"]
        self.num_ctx = num_ctx
        self.num_predict = num_predict

    def format(self) -> dict:
        return {
            "seed": self.seed,
            "temperature": self.temperature,
            "top_k": self.top_k,
            "top_p": self.top_p,
            "min_p": self.min_p,
            "stop": self.stop,
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict
        }

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(
            seed=data.get("seed", 0),
            temperature=data.get("temperature", 0.8),
            top_k=data.get("top_k", 40),
            top_p=data.get("top_p", 0.9),
            min_p=data.get("min_p", 0.0),
            stop=data.get("stop", ""),
            num_ctx=data.get("num_ctx", 2048),
            num_predict=data.get("num_predict", 128)
        )
