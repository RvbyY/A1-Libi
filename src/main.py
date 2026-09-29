import os
from galerelm.models.chat import Base,Chat, Options, Message, MessageList
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

print(f"\nBienvenue {user_profile.name} ! (Historique: {len(user_context.messages)} messages chargés)")
print("Tapez 'quit' pour quitter.\n")

while True:
    user_prompt = input("Vous : ")
    if user_prompt.lower() in ["quit", "exit", "q"]:
        break

    user_context.add(Message(role="user", content=user_prompt))
    session.commit()

    llm_messages = MessageList([
        Message(role=m.role, content=m.content, images=m.images)
        for m in user_context.messages
    ])

    llm = Chat(model=hf_model, api=api, messages=llm_messages)

    print("\nSensAI : ", end="", flush=True)

    try:
        for token in llm.execute_stream(api):
            print(token, end="", flush=True)
        print("\n")
    except Exception as e:
        print(f"\n[!] Erreur de connexion : {e}\n")
        continue

    if llm.last_response and llm.last_response.message:
        assistant_msg = llm.last_response.message
        new_msg = Message(
            role="assistant", 
            content=assistant_msg.content, 
            images=assistant_msg.images
        )
        user_context.add(new_msg)
        session.commit()
    else:
        print("[!] Erreur: Aucune réponse retournée par le modèle.")
