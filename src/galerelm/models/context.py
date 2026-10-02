"""
Context — Mémoire à Court Terme (Relationnelle).
Maintient le fil exact de la conversation (historique brut).
Limité à X messages pour ne pas surcharger la fenêtre de contexte.
"""
import logging
from typing import Optional

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from src.galerelm.models.base import Base
from src.galerelm.models.options import Options
from src.galerelm.models.message import Message, MessageList
from src.galerelm.models.deep_context import DeepContext

logger = logging.getLogger("galerelm.models.context")


class Context(Base):
    __tablename__ = "contexts"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    profile_id: str = Column(String, ForeignKey("profiles.id"), nullable=False)
    context_limit: int = Column(Integer, default=10, nullable=False)

    options = relationship(
        "Options", uselist=False, backref="context_parent",
        foreign_keys="[Options.context_id]", cascade="all, delete-orphan"
    )

    messages = relationship(
        "Message",
        collection_class=MessageList,
        backref="context",
        foreign_keys="[Message.context_id]",
        cascade="all, delete-orphan",
        order_by="Message.id"
    )

    deep_context = relationship(
        "DeepContext", uselist=False, backref="context", cascade="all, delete-orphan"
    )

    def __init__(self, profile_id: str, context_limit: int = 10, options: Optional[Options] = None,
                 messages: Optional[MessageList] = None):
        self.profile_id = profile_id
        self.context_limit = context_limit
        self.options = options if options is not None else Options()
        self.messages = messages if messages is not None else MessageList([])
        self.deep_context = DeepContext(vector_limit=4096)
        logger.debug(f"Initialized Context for profile_id={profile_id} with limit={context_limit}")

    def add(self, message: Message):
        """Ajoute un message à la mémoire court terme. Bascule vers la mémoire long terme si on dépasse la limite."""
        self.messages.append(message)
        logger.info(f"[Context] Ajout d'un message ({message.role}) — Taille actuelle : {len(self.messages)}/{self.context_limit}")
        self._check_limit_and_save()

    def _check_limit_and_save(self):
        """Vérifie la limite. Si dépassée, sauvegarde les plus anciens dans DeepContext et les retire."""
        if len(self.messages) > self.context_limit:
            overflow_count = len(self.messages) - self.context_limit
            logger.warning(f"[Context] Limite dépassée ! Transfert de {overflow_count} messages vers DeepContext.")
            overflow_messages = MessageList(self.messages[:overflow_count])

            if self.deep_context is None:
                logger.info("[Context] Création à la volée du DeepContext (non trouvé en base).")
                self.deep_context = DeepContext(vector_limit=4096)

            self.deep_context.save(overflow_messages)
            self.messages = MessageList(self.messages[overflow_count:])
            logger.debug(f"[Context] Nettoyage effectué. Nouvelle taille : {len(self.messages)}")

    def get_messages_copy(self) -> MessageList:
        """Retourne une copie DÉTACHÉE des messages (pour construire un payload LLM sans polluer l'ORM)."""
        return MessageList([
            Message(role=m.role, content=m.content, images=m.images)
            for m in self.messages
        ])
