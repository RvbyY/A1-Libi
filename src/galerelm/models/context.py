import uuid
from typing import Optional
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from src.galerelm.models.chat import Base, Options, Message, MessageList
from src.galerelm.models.deep_context import DeepContext

class Context(Base):
    """
    Mémoire à Court Terme (Relationnelle).
    Maintient le fil exact de la conversation (historique brut).
    Limité à X messages pour ne pas surcharger la fenêtre de contexte.
    """
    __tablename__ = "contexts"
    
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    profile_id: str = Column(String, ForeignKey("profiles.id"), nullable=False)
    context_limit: int = Column(Integer, default=10, nullable=False)

    options = relationship("Options", uselist=False, backref="context_parent", foreign_keys="[Options.context_id]", cascade="all, delete-orphan")

    messages = relationship(
        "Message", 
        collection_class=MessageList, 
        backref="context", 
        foreign_keys="[Message.context_id]",
        cascade="all, delete-orphan",
        order_by="Message.id"
    )

    deep_context = relationship("DeepContext", uselist=False, backref="context", cascade="all, delete-orphan")

    def __init__(self, profile_id: str, context_limit: int = 10, options: Optional[Options] = None, messages: Optional[MessageList] = None):
        self.profile_id = profile_id
        self.context_limit = context_limit
        self.options = options if options is not None else Options(
            seed=0, temperature=0.7, top_k=40, top_p=0.9, min_p=0.05, stop=["\nuser:", "</s>"], num_ctx=4096, num_predict=512
        )
        self.messages = messages if messages is not None else MessageList([])

        self.deep_context = DeepContext(vector_limit=4096)

    def add(self, message: Message):
        """Ajoute un message à la mémoire court terme. Bascule vers la mémoire long terme si on dépasse la limite."""
        self.messages.append(message)
        self.check_limit_and_save()

    def check_limit_and_save(self):
        """Vérifie la limite. Si dépassée, sauvegarde les plus anciens dans DeepContext et les retire."""
        if len(self.messages) > self.context_limit:
            overflow_count = len(self.messages) - self.context_limit
            overflow_messages = MessageList(self.messages[:overflow_count])

            # Si la base a été rechargée et que le DeepContext n'existait pas encore, on le crée à la volée
            if self.deep_context is None:
                self.deep_context = DeepContext(vector_limit=4096)

            self.deep_context.save(overflow_messages)

            self.messages = MessageList(self.messages[overflow_count:])
