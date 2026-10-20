"""
Module deep_context.py
Modèles de données ORM SQLAlchemy pour la mémoire à long terme (DeepContext et LongTermMemory).
La logique d'appel API d'embedding et de calcul vectoriel est encapsulée dans EmbeddingService et RAGManager (src/galerelm/rag.py).
"""
import logging
from sqlalchemy import Column, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from src.config import config
from src.galerelm.models.base import Base
from src.galerelm.models.message import MessageList
from src.galerelm.rag import EmbeddingService, RAGManager

logger = logging.getLogger("galerelm.models.deep_context")

DEFAULT_EMBED_MODEL = config.EMBED_MODEL
cosine_similarity = EmbeddingService.cosine_similarity


class DeepContext(Base):
    """
    Entité ORM représentant le conteneur de mémoire à long terme d'un profil.
    Délègue la vectorisation et la recherche sémantique à RAGManager.
    """
    __tablename__ = "deep_contexts"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    profile_id: str = Column(String, ForeignKey("profiles.id"), nullable=False)
    vector_limit: int = Column(Integer, default=config.DEEP_CONTEXT_LIMIT)
    embed_model: str = Column(String, default=DEFAULT_EMBED_MODEL)

    memories = relationship("LongTermMemory", backref="deep_context", cascade="all, delete-orphan")

    def __init__(self, vector_limit: int = config.DEEP_CONTEXT_LIMIT, embed_model: str = DEFAULT_EMBED_MODEL):
        self.vector_limit = vector_limit
        self.embed_model = embed_model
        logger.debug(f"Initialized DeepContext (model={embed_model}, limit={vector_limit})")

    def add_memory(self, memory: "LongTermMemory") -> None:
        """Ajoute une entrée LongTermMemory en respectant la capacité vector_limit."""
        self.memories.append(memory)
        if self.vector_limit and len(self.memories) > self.vector_limit:
            overflow = len(self.memories) - self.vector_limit
            del self.memories[:overflow]

    def save(self, message_list: MessageList, api_client=None) -> list["LongTermMemory"]:
        """Archive une liste de messages via RAGManager."""
        return RAGManager(api_client=api_client).archive(self, message_list, api_client=api_client)

    def search(self, query: str, api_client, top_k: int = 3) -> list[tuple[float, "LongTermMemory"]]:
        """Recherche les mémoires les plus pertinentes via RAGManager."""
        return RAGManager(api_client=api_client).search(self, query, api_client=api_client, top_k=top_k)


class LongTermMemory(Base):
    """
    Une entrée de la mémoire à long terme, stockant un contenu et son vecteur.
    Le vecteur est stocké en JSON pour SQLite (évolutif vers pgvector avec PostgreSQL).
    """
    __tablename__ = "long_term_memories"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    deep_context_id: int = Column(Integer, ForeignKey("deep_contexts.id"), nullable=False)

    role: str = Column(String, nullable=False)
    content: str = Column(Text, nullable=False)
    embedding: list[float] = Column(JSON, nullable=False)

    def __init__(self, role: str, content: str, embedding: list[float] = None):
        self.role = role
        self.content = content
        self.embedding = embedding if embedding is not None else []
