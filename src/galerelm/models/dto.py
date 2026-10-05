"""
Modèles de réponse (DTOs) pour SensAIWrapper.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class ProfileResponse:
    id: str
    name: str
    email: str
    instructions: str

@dataclass
class ContextResponse:
    id: int
    profile_id: str
    context_limit: int

@dataclass
class MessageResponse:
    role: str
    content: str

@dataclass
class ChatCompletionResponse:
    message: MessageResponse
    eval_count: int
    eval_duration: float

@dataclass
class MemoryResponse:
    id: int
    role: str
    content: str
    score: Optional[float] = None

@dataclass
class StatusResponse:
    db_status: str
    api_status: str
    active_model: str
