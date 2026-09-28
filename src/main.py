import json
import os

from galerelm.models.chat import Chat, Options, Message, MessageList
from dotenv import load_dotenv
from rapideAPI.client import RapideAPI
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

load_dotenv()

hf_model = os.getenv("HF_MODEL")
ollama_host = os.getenv("OLLAMA_HOST")

api = RapideAPI(
    base_url=ollama_host,
    default_headers={"Authorization": "TOKEN"}
)

user_prompt = input("\nPosez votre question au modèle : ")

# PAS TOUCHER SVP
options = Options(
    seed=0,                
    temperature=0.7,       
    top_k=40,              
    top_p=0.9,             
    min_p=0.05,            
    stop=["\nuser:", "</s>"], 
    num_ctx=4096,          
    num_predict=512        
)

messages = MessageList([
    Message(role="user", content=user_prompt)
])

user_chat = Chat(
    model=hf_model, 
    messages=messages, 
    tools=None, 
    request_format="json",
    options=options, 
    stream=True, 
    think="medium",
    keep_alive="5m", 
    logprobs=False, 
    top_logprobs=0
)

print("\n--- RÉPONSE DU MODÈLE ---")

for token in user_chat.execute_stream(api):
    print(token, end="", flush=True)

print()
ollama_response = user_chat.last_response

if ollama_response:
    print("\n--- OBJET CHATRESPONSE SAUVEGARDÉ ---")
    print(f"Modèle: {ollama_response.model}")
    print(f"Tokens évalués: {ollama_response.eval_count}")
    print(f"Temps de génération: {ollama_response.eval_duration / 1e9:.2f} s")
else:
    print("\nErreur: Flux interrompu avant la fin, réponse incomplète.")

