"""
Module deep_context.py
Gère la mémoire à long terme (vectorielle) et le processus RAG.
Pour une documentation détaillée, voir deep_context.md.
"""
import math
import logging
from src.config import config

from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship

from src.galerelm.models.base import Base
from src.galerelm.models.message import MessageList

logger = logging.getLogger("galerelm.models.deep_context")

# ── Modèle d'embedding par défaut ────────────────────────────────────
DEFAULT_EMBED_MODEL = config.EMBED_MODEL


# ── Calcul de similarité cosinus (pur Python, sans numpy) ────────────

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calcule la similarité cosinus entre deux vecteurs."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class DeepContext(Base):
    __tablename__ = "deep_contexts"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    profile_id: str = Column(String, ForeignKey("profiles.id"), nullable=False)
    vector_limit: int = Column(Integer, default=config.DEEP_CONTEXT_LIMIT)
    embed_model: str = Column(String, default=DEFAULT_EMBED_MODEL)

    memories = relationship("LongTermMemory", backref="deep_context", cascade="all, delete-orphan")

    def __init__(self, vector_limit: int = 4096, embed_model: str = DEFAULT_EMBED_MODEL):
        self.vector_limit = vector_limit
        self.embed_model = embed_model
        logger.debug(f"Initialized DeepContext (model={embed_model}, limit={vector_limit})")

    # ── Embedding ────────────────────────────────────────────────────

    def _embed(self, text: str, api_client) -> list[float]:
        """Génère un vecteur d'embedding via l'API Ollama."""
        try:
            response = api_client.post("api/embed", json={
                "model": self.embed_model,
                "input": text,
            })
            # Ollama renvoie {"embeddings": [[0.1, 0.2, ...]]}
            embeddings = response.get("embeddings", [])
            if embeddings and len(embeddings) > 0:
                logger.debug(f"[DeepContext] Embedding généré ({len(embeddings[0])} dimensions)")
                return embeddings[0]
            logger.warning("[DeepContext] Réponse d'embedding vide.")
            return []
        except Exception as e:
            logger.error(f"[DeepContext] Erreur lors de la génération de l'embedding : {e}")
            return []

    def _embed_batch(self, texts: list[str], api_client) -> list[list[float]]:
        """Génère des embeddings pour un lot de textes en un seul appel API."""
        try:
            response = api_client.post("api/embed", json={
                "model": self.embed_model,
                "input": texts,
            })
            embeddings = response.get("embeddings", [])
            logger.debug(f"[DeepContext] Batch de {len(embeddings)} embeddings générés")
            return embeddings
        except Exception as e:
            logger.error(f"[DeepContext] Erreur lors du batch embedding : {e}")
            return [[] for _ in texts]

    # ── Sauvegarde ───────────────────────────────────────────────────

    def save(self, message_list: MessageList, api_client=None):
        """
        Convertit les messages sortants du contexte en mémoires à long terme.
        Si api_client est fourni, génère de vrais embeddings vectoriels.
        Sinon, stocke un vecteur vide (mode dégradé).
        """
        texts = [msg.content for msg in message_list]

        # Génération des embeddings (en batch si possible)
        if api_client:
            embeddings = self._embed_batch(texts, api_client)
        else:
            logger.warning("[DeepContext] Pas de client API — stockage sans embeddings (mode dégradé).")
            embeddings = [[] for _ in texts]

        for msg, embedding in zip(message_list, embeddings):
            memory = LongTermMemory(
                role=msg.role,
                content=msg.content,
                embedding=embedding,
            )
            self.memories.append(memory)

        vectorized = sum(1 for e in embeddings if e)
        logger.info(f"[DeepContext] {len(message_list)} messages archivés ({vectorized} vectorisés).")

    # ── Recherche par similarité (RAG) ───────────────────────────────

    def search(self, query: str, api_client, top_k: int = 3) -> list[tuple[float, "LongTermMemory"]]:
        """
        Recherche les mémoires les plus pertinentes par rapport à une requête.
        Retourne une liste de tuples (score_similarité, mémoire), triée par pertinence décroissante.
        """
        if not self.memories:
            return []

        query_embedding = self._embed(query, api_client)
        if not query_embedding:
            logger.warning("[DeepContext] Impossible de vectoriser la requête. Recherche annulée.")
            return []

        results = []
        for mem in self.memories:
            if mem.embedding:
                score = cosine_similarity(query_embedding, mem.embedding)
                results.append((score, mem))

        results.sort(key=lambda x: x[0], reverse=True)
        top_results = results[:top_k]

        if top_results:
            logger.info(
                f"[DeepContext] Recherche RAG : {len(top_results)} résultats trouvés "
                f"(meilleur score: {top_results[0][0]:.4f})"
            )

        return top_results


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
