"""
Module database.py
Encapsule l'initialisation du moteur SQLAlchemy et la fabrique de sessions.
"""
import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import config
from src.galerelm.models import Base

logger = logging.getLogger("galerelm.database")


class DatabaseManager:
    """
    Gère la connexion à la base de données SQLAlchemy, la création des tables
    et la fourniture de sessions thread-safe.
    """

    def __init__(self, db_url: str = None):
        self.db_url = db_url or config.DB_URL
        logger.info(f"Connexion à la base de données ({self.db_url})...")
        self.engine = create_engine(self.db_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info("Base de données initialisée avec succès.")

    def create_session(self) -> Session:
        """Retourne une nouvelle session SQLAlchemy."""
        return self.SessionLocal()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Fournit un contexte transactionnel propre (fermeture garantie)."""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def is_healthy(self) -> bool:
        return self.engine is not None
