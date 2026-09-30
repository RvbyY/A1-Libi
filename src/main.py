import os
# C'est la dernière fois qu'on me supprime une branche
from galerelm.models.chat import Chat, Options, Message, MessageList
from dotenv import load_dotenv
from rapideAPI.client import RapideAPI
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.galerelm.models.profile import Profile
from src.galerelm.models.context import Context
from src.galerelm.models.deep_context import DeepContext, LongTermMemory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

load_dotenv()
hf_model = os.getenv("HF_MODEL")
ollama_host = os.getenv("OLLAMA_HOST")

engine = create_engine('sqlite:///galerelm.db')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

user_profile = session.query(Profile).filter_by(email="user@sensai.ai").first()

if not user_profile:
    user_profile = Profile(
        name="Utilisateur", 
        email="user@sensai.ai", 
        instructions="Tu es SensAI, un assistant intelligent et concis."
    )
    session.add(user_profile)
    session.commit()

user_context = session.query(Context).filter_by(profile_id=user_profile.id).first()

if not user_context:
    user_context = Context(profile_id=user_profile.id, context_limit=10)
    session.add(user_context)
    session.commit()

api = RapideAPI(
    base_url=ollama_host,
    default_headers={"Authorization": "TOKEN"}
)

user_prompt = input("\nPosez votre question au modèle : ")

llm = Chat(model=hf_model, api=api)

llm.ask(user_prompt)

    llm_messages = MessageList([
        Message(role=m.role, content=m.content, images=m.images)
        for m in user_context.messages
    ])

ollama_response = llm.last_response

if ollama_response:
    print("\n--- OBJET CHATRESPONSE SAUVEGARDÉ ---")
    print(f"Modèle: {ollama_response.model}")
    print(f"Tokens évalués: {ollama_response.eval_count}")
    print(f"Temps de génération: {ollama_response.eval_duration / 1e9:.2f} s")
else:
    print("\nErreur: Flux interrompu avant la fin, réponse incomplète.")
