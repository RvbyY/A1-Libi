"""
Module galerelm/rag.py
Encapsule la génération d'embeddings vectoriels (EmbeddingService) et la recherche
de similarité / archivage RAG (RAGManager) séparément des modèles ORM SQLAlchemy.
"""
import logging
import math
from typing import TYPE_CHECKING, Any, Optional

from src.config import config
from src.galerelm.models.message import MessageList

if TYPE_CHECKING:
    from src.galerelm.models.deep_context import DeepContext, LongTermMemory

logger = logging.getLogger("galerelm.rag")


class EmbeddingService:
    """
    Service dédié aux appels d'embedding vectoriel (via RapideAPI / Ollama)
    et aux calculs de similarité cosinus.
    """

    def __init__(self, embed_model: Optional[str] = None, api_client: Any = None):
        self.embed_model = embed_model or config.EMBED_MODEL
        self.api_client = api_client

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Calcule la similarité cosinus entre deux vecteurs."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    def embed(self, text: str, api_client: Any = None) -> list[float]:
        """Génère un vecteur d'embedding pour un texte unique."""
        client = api_client or self.api_client
        if client is None:
            logger.warning("[EmbeddingService] Aucun client API disponible pour embed().")
            return []

        try:
            response = client.post("api/embed", json={
                "model": self.embed_model,
                "input": text,
            })
            embeddings = response.get("embeddings", []) if isinstance(response, dict) else []
            if embeddings and len(embeddings) > 0:
                logger.debug(f"[EmbeddingService] Embedding généré ({len(embeddings[0])} dimensions)")
                return embeddings[0]
            logger.warning("[EmbeddingService] Réponse d'embedding vide.")
            return []
        except Exception as exc:
            logger.error(f"[EmbeddingService] Erreur lors de la génération de l'embedding : {exc}")
            return []

    def embed_batch(self, texts: list[str], api_client: Any = None) -> list[list[float]]:
        """Génère des vecteurs d'embedding pour un lot de textes en un seul appel API."""
        if not texts:
            return []

        client = api_client or self.api_client
        if client is None:
            logger.warning("[EmbeddingService] Pas de client API — stockage sans embeddings (mode dégradé).")
            return [[] for _ in texts]

        try:
            response = client.post("api/embed", json={
                "model": self.embed_model,
                "input": texts,
            })
            embeddings = response.get("embeddings", []) if isinstance(response, dict) else []
            logger.debug(f"[EmbeddingService] Batch de {len(embeddings)} embeddings générés")
            return embeddings
        except Exception as exc:
            logger.error(f"[EmbeddingService] Erreur lors du batch embedding : {exc}")
            return [[] for _ in texts]


class RAGManager:
    """
    Orchestre l'archivage des messages sortants du contexte court terme vers DeepContext
    et la recherche sémantique (RAG) dans les LongTermMemory.
    """

    def __init__(self, embedding_service: Optional[EmbeddingService] = None, api_client: Any = None):
        self.embedding_service = embedding_service or EmbeddingService(api_client=api_client)
        self.api_client = api_client

    def _service_for(self, deep_context: "DeepContext") -> EmbeddingService:
        model_name = getattr(deep_context, "embed_model", None) or self.embedding_service.embed_model
        if model_name != self.embedding_service.embed_model:
            return EmbeddingService(embed_model=model_name, api_client=self.api_client)
        return self.embedding_service

    def archive(
        self,
        deep_context: "DeepContext",
        message_list: MessageList,
        api_client: Any = None,
    ) -> list["LongTermMemory"]:
        """
        Vectorise un lot de messages et les ajoute en tant que LongTermMemory dans deep_context.
        Respecte la limite vector_limit si elle est atteinte.
        """
        from src.galerelm.models.deep_context import LongTermMemory

        if not message_list:
            return []

        client = api_client or self.api_client
        service = self._service_for(deep_context)
        texts = [msg.content for msg in message_list]
        embeddings = service.embed_batch(texts, api_client=client)

        created: list[LongTermMemory] = []
        for msg, embedding in zip(message_list, embeddings):
            memory = LongTermMemory(
                role=msg.role,
                content=msg.content,
                embedding=embedding,
            )
            deep_context.add_memory(memory)
            created.append(memory)

        vectorized = sum(1 for e in embeddings if e)
        logger.info(f"[RAGManager] {len(created)} messages archivés ({vectorized} vectorisés).")
        return created

    def search(
        self,
        deep_context: Optional["DeepContext"],
        query: str,
        api_client: Any = None,
        top_k: int = 3,
    ) -> list[tuple[float, "LongTermMemory"]]:
        """
        Recherche les mémoires les plus pertinentes dans deep_context par similarité cosinus.
        """
        if not deep_context or not getattr(deep_context, "memories", None):
            return []

        client = api_client or self.api_client
        service = self._service_for(deep_context)
        query_embedding = service.embed(query, api_client=client)
        if not query_embedding:
            logger.warning("[RAGManager] Impossible de vectoriser la requête. Recherche annulée.")
            return []

        results: list[tuple[float, "LongTermMemory"]] = []
        for mem in deep_context.memories:
            if mem.embedding:
                score = service.cosine_similarity(query_embedding, mem.embedding)
                results.append((score, mem))

        results.sort(key=lambda x: x[0], reverse=True)
        top_results = results[:top_k]

        if top_results:
            logger.info(
                f"[RAGManager] Recherche RAG : {len(top_results)} résultats trouvés "
                f"(meilleur score: {top_results[0][0]:.4f})"
            )

        return top_results
