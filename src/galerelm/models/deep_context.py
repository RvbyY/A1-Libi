from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from src.galerelm.models.chat import Base, MessageList

class DeepContext(Base):
    """
    Mémoire à Long Terme (Vectorielle).
    Stocke les faits et l'historique sous forme de vecteurs pour une recherche RAG.
    """
    __tablename__ = "deep_contexts"
    
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    context_id: int = Column(Integer, ForeignKey("contexts.id"), nullable=False)
    vector_limit: int = Column(Integer, default=4096)
    
    # Historique long terme (relation One-to-Many vers LongTermMemory)
    memories = relationship("LongTermMemory", backref="deep_context", cascade="all, delete-orphan")

    def __init__(self, vector_limit: int = 4096):
        self.vector_limit = vector_limit

    def save(self, message_list: MessageList):
        """
        Convertit les messages sortants du contexte en mémoires à long terme.
        """
        for msg in message_list:
            # Ici, dans un vrai système RAG, on appellerait l'API d'embeddings
            # ex: vector = ollama.embeddings(model="nomic-embed-text", prompt=msg.content)
            memory = LongTermMemory(
                role=msg.role,
                content=msg.content,
                embedding=[] # Simulation du stockage vectoriel
            )
            self.memories.append(memory)
        print(f"[*] {len(message_list)} messages archivés dans la mémoire à long terme (DeepContext).")

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

