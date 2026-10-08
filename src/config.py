import os
from dotenv import load_dotenv

# Charge les variables d'environnement depuis le fichier .env s'il existe
load_dotenv()

class Config:
    # ── Base de Données ──
    DB_URL: str = os.getenv("DB_URL", "sqlite:///galerelm.db")
    
    # ── Ollama API ──
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    DEFAULT_MODEL: str = os.getenv("HF_MODEL", "llama3.2")
    EMBED_MODEL: str = os.getenv("EMBED_MODEL", "nomic-embed-text")
    
    # ── Paramètres de Mémoire (Contextes) ──
    # Nombre max de messages conservés en mémoire courte (avant archivage)
    CONTEXT_LIMIT: int = int(os.getenv("CONTEXT_LIMIT", "10"))
    
    # Nombre max d'entrées vectorielles dans la mémoire long terme (DeepContext)
    DEEP_CONTEXT_LIMIT: int = int(os.getenv("DEEP_CONTEXT_LIMIT", "4096"))

config = Config()
