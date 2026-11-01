"""
Module documents.py
RAG sur documents locaux (R1) : lecture des fichiers, découpage en fragments, vectorisation, stockage,
puis recherche par similarité pour injecter les meilleurs extraits dans le prompt, avec leur source.
"""
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from src.galerelm.models.document import DocumentChunk
from src.galerelm.rag import EmbeddingService

logger = logging.getLogger("galerelm.documents")

# Formats texte lus directement. Les autres fichiers d'un dossier sont ignorés.
SUPPORTED_SUFFIXES = (".md", ".txt", ".rst", ".csv", ".json", ".yaml", ".yml", ".py", ".html")
CHUNK_SIZE = 800       # caractères par fragment : quelques paragraphes
CHUNK_OVERLAP = 100    # caractères repris du fragment précédent, pour ne pas couper une idée en deux
MAX_FILE_SIZE = 2_000_000


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Découpe un texte en fragments d'environ `size` caractères, en coupant de préférence entre deux paragraphes,
    sinon entre deux phrases, sinon entre deux mots. Chaque fragment reprend la fin du précédent (`overlap`).
    """
    if overlap >= size:
        raise ValueError("overlap doit être plus petit que size.")
    text = re.sub(r"\n{3,}", "\n\n", text.replace("\r\n", "\n")).strip()
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start:end]
            for separator in ("\n\n", ". ", "\n", " "):
                cut = window.rfind(separator)
                if cut > size // 2:
                    end = start + cut + len(separator)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        # Le fragment suivant reprend la fin du précédent, en commençant au début d'un mot
        next_start = end - overlap
        if next_start > 0 and not text[next_start - 1].isspace():
            space = text.find(" ", next_start, end)
            next_start = space + 1 if space != -1 else end
        start = max(next_start, start + 1)
    return chunks


def collect_files(path: Path) -> list[Path]:
    """Un fichier, ou tous les fichiers texte d'un dossier (récursif, dossiers cachés exclus)."""
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"Chemin introuvable : {path}")
    return sorted(
        file for file in path.rglob("*")
        if file.is_file() and file.suffix.lower() in SUPPORTED_SUFFIXES
        and not any(part.startswith(".") for part in file.relative_to(path).parts)
    )


@dataclass
class IngestReport:
    files: int = 0
    chunks: int = 0
    vectorized: int = 0
    skipped: list[str] = None

    def __post_init__(self):
        self.skipped = self.skipped or []


class DocumentStore:
    """Ingestion et recherche des documents d'un profil."""

    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        self.embeddings = embedding_service or EmbeddingService()

    def ingest(self, session, profile_id: str, path: str, api_client: Any = None) -> IngestReport:
        """Ingère un fichier ou un dossier. Réingérer un fichier remplace ses anciens fragments."""
        report = IngestReport()
        root = Path(path).expanduser()
        for file in collect_files(root):
            if file.stat().st_size > MAX_FILE_SIZE:
                report.skipped.append(f"{file} (trop volumineux)")
                continue
            try:
                text = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                report.skipped.append(f"{file} (illisible en texte)")
                continue
            pieces = chunk_text(text)
            if not pieces:
                report.skipped.append(f"{file} (vide)")
                continue
            source = str(file)
            session.query(DocumentChunk).filter_by(profile_id=profile_id, source=source).delete()
            vectors = self.embeddings.embed_batch(pieces, api_client=api_client)
            for position, (piece, vector) in enumerate(zip(pieces, vectors), start=1):
                session.add(DocumentChunk(profile_id, source, position, piece, vector or []))
            report.files += 1
            report.chunks += len(pieces)
            report.vectorized += sum(1 for vector in vectors if vector)
        session.commit()
        logger.info(f"[Documents] {report.files} fichier(s), {report.chunks} fragment(s) ingérés.")
        return report

    def search(self, session, profile_id: str, query: str, api_client: Any = None,
               top_k: int = 3) -> list[tuple[float, DocumentChunk]]:
        """Les `top_k` fragments les plus proches de la question, avec leur score de similarité."""
        chunks = session.query(DocumentChunk).filter_by(profile_id=profile_id).all()
        if not chunks or not query:
            return []
        query_vector = self.embeddings.embed(query, api_client=api_client)
        if not query_vector:
            return []
        scored = [(EmbeddingService.cosine_similarity(query_vector, c.embedding), c) for c in chunks if c.embedding]
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[:top_k]

    @staticmethod
    def sources(session, profile_id: str) -> list[tuple[str, int]]:
        """Fichiers ingérés et nombre de fragments par fichier."""
        from sqlalchemy import func
        rows = (session.query(DocumentChunk.source, func.count(DocumentChunk.id))
                .filter_by(profile_id=profile_id).group_by(DocumentChunk.source).order_by(DocumentChunk.source).all())
        return [(source, count) for source, count in rows]

    @staticmethod
    def forget(session, profile_id: str, source: Optional[str] = None) -> int:
        """Supprime les fragments d'un fichier, ou de tous les fichiers si source est None."""
        query = session.query(DocumentChunk).filter_by(profile_id=profile_id)
        if source is not None:
            query = query.filter_by(source=source)
        count = query.delete()
        session.commit()
        return count
