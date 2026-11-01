"""
Module database.py
Encapsule l'initialisation du moteur SQLAlchemy et la fabrique de sessions.
"""
import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from src.config import config, resolve_db_url
from src.galerelm.models import Base

logger = logging.getLogger("galerelm.database")


def add_missing_columns(engine) -> list[str]:
    """
    Migration minimale : create_all() crée les tables absentes, mais ne modifie jamais une table existante.
    On ajoute donc les colonnes nullables apparues dans les modèles depuis la création de la base
    (ALTER TABLE ... ADD COLUMN). Retourne les colonnes ajoutées, au format table.colonne.
    """
    inspector = inspect(engine)
    added = []
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing or not column.nullable or column.primary_key:
                    continue
                column_type = column.type.compile(dialect=engine.dialect)
                connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'))
                added.append(f"{table.name}.{column.name}")
    if added:
        logger.info(f"Colonnes ajoutées à la base : {', '.join(added)}")
    return added


class DatabaseManager:
    """
    Gère la connexion à la base de données SQLAlchemy, la création des tables
    et la fourniture de sessions thread-safe.
    """

    def __init__(self, db_url: str = None):
        self.db_url = resolve_db_url(db_url or config.DB_URL)
        logger.info(f"Connexion à la base de données ({self.db_url})...")
        self.engine = create_engine(self.db_url)
        Base.metadata.create_all(self.engine)
        add_missing_columns(self.engine)
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
