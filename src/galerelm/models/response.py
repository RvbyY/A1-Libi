"""
Modèles de réponse : ChatResponse, LogProb, TopLogProb.
Stockent les métadonnées retournées par l'API après une génération.
"""
from typing import Optional

from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship

from src.galerelm.models.base import Base
from src.galerelm.models.message import Message


class TopLogProb(Base):
    __tablename__ = "top_logprobs"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    logprob_id: int = Column(Integer, ForeignKey("logprobs.id"))

    token: str = Column(String)
    logprob: float = Column(Float)
    bytes: list[int] = Column(JSON, nullable=True)

    def __init__(self, token: str, logprob: float, bytes_repr: list[int]):
        self.token = token
        self.logprob = logprob
        self.bytes = bytes_repr

    def format(self) -> dict:
        return {
            "token": self.token,
            "logprob": self.logprob,
            "bytes": self.bytes
        }

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(
            token=data.get("token", ""),
            logprob=data.get("logprob", 0.0),
            bytes_repr=data.get("bytes", [])
        )


class LogProb(Base):
    __tablename__ = "logprobs"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    response_id: int = Column(Integer, ForeignKey("chat_responses.id"))

    token: str = Column(String)
    logprob: float = Column(Float)
    bytes: list[int] = Column(JSON, nullable=True)

    top_logprobs = relationship("TopLogProb", backref="parent_logprob", cascade="all, delete-orphan")

    def __init__(self, token: str, logprob: float, bytes_repr: list[int], top_logprobs: list[TopLogProb] = None):
        self.token = token
        self.logprob = logprob
        self.bytes = bytes_repr
        self.top_logprobs = top_logprobs if top_logprobs is not None else []

    def format(self) -> dict:
        return {
            "token": self.token,
            "logprob": self.logprob,
            "bytes": self.bytes,
            "top_logprobs": [t.format() for t in self.top_logprobs] if self.top_logprobs else []
        }

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(
            token=data.get("token", ""),
            logprob=data.get("logprob", 0.0),
            bytes_repr=data.get("bytes", []),
            top_logprobs=[TopLogProb.from_format(t) for t in data.get("top_logprobs", [])]
        )


class ChatResponse(Base):
    """Réponse complète retournée par l'API après une génération (métadonnées + message)."""
    __tablename__ = "chat_responses"
    id: int = Column(Integer, primary_key=True, autoincrement=True)

    model: str = Column(String)
    created_at: str = Column(String)
    done: bool = Column(Boolean)
    done_reason: str = Column(String)
    total_duration: int = Column(Integer)
    load_duration: int = Column(Integer)
    prompt_eval_count: int = Column(Integer)
    prompt_eval_cached_count: int = Column(Integer)
    prompt_eval_duration: int = Column(Integer)
    eval_count: int = Column(Integer)
    eval_duration: int = Column(Integer)

    message = relationship("Message", uselist=False, backref="response_parent", foreign_keys="[Message.response_id]",
                           cascade="all, delete-orphan")
    logprobs = relationship("LogProb", backref="response", cascade="all, delete-orphan")

    def __init__(
            self,
            model: str,
            created_at: str,
            message: Message,
            done: bool,
            done_reason: str,
            total_duration: int,
            load_duration: int,
            prompt_eval_count: int,
            prompt_eval_cached_count: int,
            prompt_eval_duration: int,
            eval_count: int,
            eval_duration: int,
            logprobs: Optional[list[LogProb]] = None
    ):
        self.model = model
        self.created_at = created_at
        self.message = message
        self.done = done
        self.done_reason = done_reason
        self.total_duration = total_duration
        self.load_duration = load_duration
        self.prompt_eval_count = prompt_eval_count
        self.prompt_eval_cached_count = prompt_eval_cached_count
        self.prompt_eval_duration = prompt_eval_duration
        self.eval_count = eval_count
        self.eval_duration = eval_duration
        self.logprobs = logprobs if logprobs is not None else []

    def format(self) -> dict:
        res = {
            "model": self.model,
            "created_at": self.created_at,
            "message": self.message.format() if self.message else None,
            "done": self.done,
            "done_reason": self.done_reason,
            "total_duration": self.total_duration,
            "load_duration": self.load_duration,
            "prompt_eval_count": self.prompt_eval_count,
            "prompt_eval_cached_count": self.prompt_eval_cached_count,
            "prompt_eval_duration": self.prompt_eval_duration,
            "eval_count": self.eval_count,
            "eval_duration": self.eval_duration,
        }
        if self.logprobs:
            res["logprobs"] = [lp.format() for lp in self.logprobs]
        return res

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        logprobs_data = data.get("logprobs")
        return cls(
            model=data.get("model", ""),
            created_at=data.get("created_at", ""),
            message=Message.from_format(data.get("message", {})),
            done=data.get("done", False),
            done_reason=data.get("done_reason", ""),
            total_duration=data.get("total_duration", 0),
            load_duration=data.get("load_duration", 0),
            prompt_eval_count=data.get("prompt_eval_count", 0),
            prompt_eval_cached_count=data.get("prompt_eval_cached_count", 0),
            prompt_eval_duration=data.get("prompt_eval_duration", 0),
            eval_count=data.get("eval_count", 0),
            eval_duration=data.get("eval_duration", 0),
            logprobs=[LogProb.from_format(lp) for lp in logprobs_data] if logprobs_data else None
        )
