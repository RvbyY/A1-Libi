"""
Modèle InteractionLog (EV3) : une ligne par échange avec le modèle, pour le suivi des métriques
(volume, latence, tokens, outils, erreurs) et leur évolution dans le temps.
"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text

from src.galerelm.models.base import Base

TEXT_PREVIEW = 500  # longueur gardée de la question et de la réponse


class InteractionLog(Base):
    __tablename__ = "interaction_logs"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    created_at: datetime = Column(DateTime, nullable=False, default=datetime.now, index=True)
    profile_id: str = Column(String, index=True)
    context_id: int = Column(Integer)
    model: str = Column(String)
    persona: str = Column(String)
    status: str = Column(String, nullable=False)          # ok, blocked (guardrail), error, interrupted
    error: str = Column(Text)
    latency_s: float = Column(Float)                      # durée totale de l'échange
    first_token_s: float = Column(Float)                  # attente avant le premier morceau de réponse
    prompt_tokens: int = Column(Integer)                  # tokens lus par le modèle (dernière génération)
    gen_tokens: int = Column(Integer)                     # tokens générés (dernière génération)
    system_prompt_chars: int = Column(Integer)
    memories_injected: int = Column(Integer)
    documents_injected: int = Column(Integer)
    tools: list = Column(JSON)                            # noms des outils appelés pendant l'échange
    tool_failures: int = Column(Integer)
    user_prompt: str = Column(Text)
    answer: str = Column(Text)
    # Scores du juge (EV1), renseignés en mode anti-hallucination : 0 à 5
    eval_relevance: float = Column(Float)
    eval_coherence: float = Column(Float)
    eval_faithfulness: float = Column(Float)
    eval_grounded: bool = Column(Boolean)
    eval_verified: bool = Column(Boolean)

    def format(self) -> dict:
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}
