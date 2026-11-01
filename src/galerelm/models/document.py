"""
Modèle DocumentChunk (R1) : un fragment d'un document local ingéré, avec son vecteur.
Le contenu des fichiers est découpé, vectorisé et stocké pour la recherche sémantique (voir src/galerelm/documents.py).
"""
from sqlalchemy import JSON, Column, ForeignKey, Integer, String, Text

from src.galerelm.models.base import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    profile_id: str = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)
    source: str = Column(String, nullable=False, index=True)   # chemin du fichier d'origine
    position: int = Column(Integer, nullable=False)            # numéro du fragment dans le fichier (à partir de 1)
    content: str = Column(Text, nullable=False)
    embedding: list[float] = Column(JSON, nullable=False)

    def __init__(self, profile_id: str, source: str, position: int, content: str, embedding: list[float] = None):
        self.profile_id = profile_id
        self.source = source
        self.position = position
        self.content = content
        self.embedding = embedding if embedding is not None else []

    @property
    def label(self) -> str:
        """Référence courte citée dans le prompt et les réponses : fichier#fragment."""
        return f"{self.source}#{self.position}"
