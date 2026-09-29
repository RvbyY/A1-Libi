import os
import logging
from dotenv import load_dotenv

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.galerelm.models.chat import Base, Chat, Message, MessageList
from src.galerelm.models.profile import Profile
from src.galerelm.models.context import Context
from src.rapideAPI.client import RapideAPI

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

load_dotenv()
hf_model = os.getenv("HF_MODEL")
ollama_host = os.getenv("OLLAMA_HOST")

# ---- 1. INITIALISATION DE LA BASE DE DONNÉES ----
engine = create_engine('sqlite:///galerelm.db')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

# ---- 2. CRÉATION OU CHARGEMENT DU PROFIL & CONTEXTE ----
# On simule la connexion d'un utilisateur
user_profile = session.query(Profile).filter_by(email="user@sensai.ai").first()

if not user_profile:
    # Création d'un profil par défaut s'il n'existe pas
    user_profile = Profile(
        name="Utilisateur", 
        email="user@sensai.ai", 
        instructions="Tu es SensAI, un assistant intelligent et concis."
    )
    session.add(user_profile)
    session.commit()

# On récupère le contexte (session de chat) de l'utilisateur
user_context = session.query(Context).filter_by(profile_id=user_profile.id).first()

if not user_context:
    user_context = Context(profile_id=user_profile.id, context_limit=10)
    session.add(user_context)
    session.commit()

# ---- 3. INITIALISATION DE L'API ----
api = RapideAPI(
    base_url=ollama_host,
    default_headers={"Authorization": "TOKEN"}
)

print(f"\nBienvenue {user_profile.name} ! (Historique: {len(user_context.messages)} messages chargés)")
print("Tapez 'quit' pour quitter.\n")

# ---- 4. BOUCLE DE DISCUSSION ----
while True:
    user_prompt = input("Vous : ")
    if user_prompt.lower() in ["quit", "exit", "q"]:
        break

    # Ajout du message utilisateur au contexte persistant (qui gère l'overflow vers DeepContext)
    user_context.add(Message(role="user", content=user_prompt))
    session.commit()

    # On copie la liste pour éviter que SQLAlchemy n'essaie de lier le modèle Chat éphémère à la base de données
    llm_messages = MessageList(list(user_context.messages))
    llm = Chat(model=hf_model, api=api, messages=llm_messages)
    session.add(llm)

    print("\nSensAI : ", end="", flush=True)

    # Récupération et affichage du flux
    for token in llm.execute_stream(api):
        print(token, end="", flush=True)
    print("\n")

    # On récupère la réponse générée et on l'ajoute au contexte
    if getattr(llm, "last_response", None) and llm.last_response.message:
        assistant_msg = llm.last_response.message
        # On recrée un objet Message (le message reçu est rattaché à ChatResponse, on le duplique pour le contexte)
        new_msg = Message(
            role="assistant", 
            content=assistant_msg.content, 
            images=assistant_msg.images, 
            tool_calls=assistant_msg.tool_calls
        )
        user_context.add(new_msg)
        session.commit()
    else:
        print("[!] Erreur: Aucune réponse retournée par le modèle.")
