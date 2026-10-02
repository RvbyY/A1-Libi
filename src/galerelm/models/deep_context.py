"""
DeepContext — Mémoire à Long Terme (Vectorielle).
Stocke les faits et l'historique sous forme de vecteurs pour une recherche RAG.
"""
import logging

from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship

from src.galerelm.models.base import Base
from src.galerelm.models.message import MessageList

logger = logging.getLogger("galerelm.models.deep_context")


class DeepContext(Base):
    __tablename__ = "deep_contexts"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    context_id: int = Column(Integer, ForeignKey("contexts.id"), nullable=False)
    vector_limit: int = Column(Integer, default=4096)

    memories = relationship("LongTermMemory", backref="deep_context", cascade="all, delete-orphan")

    def __init__(self, vector_limit: int = 4096):
        self.vector_limit = vector_limit
        logger.debug(f"Initialized DeepContext with limit={vector_limit}")

    def save(self, message_list: MessageList):
        """Convertit les messages sortants du contexte en mémoires à long terme."""
        for msg in message_list:
            memory = LongTermMemory(
                role=msg.role,
                content=msg.content,
                embedding=[]  # Placeholder pour les embeddings vectoriels
            )
            self.memories.append(memory)
        logger.info(f"[DeepContext] {len(message_list)} messages archivés en mémoire long terme.")


class LongTermMemory(Base):
    """
    Une entrée de la mémoire à long terme, stockant un contenu et son vecteur.
    Pour l'instant, on stocke le vecteur dans un JSON pour SQLite.
    (Peut évoluer vers pgvector avec PostgreSQL).
    """
    __tablename__ = "long_term_memories"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    deep_context_id: int = Column(Integer, ForeignKey("deep_contexts.id"), nullable=False)

    role: str = Column(String, nullable=False)
    content: str = Column(Text, nullable=False)
    embedding: list[float] = Column(JSON, nullable=False)
