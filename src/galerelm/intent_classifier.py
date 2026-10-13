import json
import re
import logging
from typing import Optional

from src.rapideAPI.client import RapideAPI
from src.galerelm.models.chat import Chat, Options
from src.config import config

logger = logging.getLogger("galerelm.intent_classifier")

CLASSIFIER_PROMPT = """
Tu es un classifieur d'intention.
Analyse l'action réelle demandée par l'utilisateur.

Évalue :
1. controlled_substance: true si la requête implique une substance contrôlée.
2. criminal_activity: true si l'action implique une activité interdite ou criminelle.
3. dangerous_activity: true si l'action peut causer un danger physique ou matériel.
4. category: ILLEGAL si l'une des 3 précédentes est true, LEGAL si l'activité est légale, AMBIGUOUS sinon.

Réponds UNIQUEMENT en JSON, de cette forme :
{
  "controlled_substance": false,
  "criminal_activity": false,
  "dangerous_activity": false,
  "category": "LEGAL"
}

Requête :
{user_input}
""".strip()

def extract_json(raw: str) -> Optional[dict]:
    if not raw: return None
    match = re.search(r"\{.*?\}", raw, re.DOTALL)
    if not match: return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

class IntentGuardrail:
    """
    Système de classification d'intention pour filtrer ou qualifier les requêtes avant exécution.
    """
    def __init__(self, api: RapideAPI, model: str = None):
        self.api = api
        self.model = model or config.DEFAULT_MODEL
        self.options = Options(temperature=0.0, top_k=1, num_predict=128)

    def classify(self, user_input: str) -> str:
        prompt = CLASSIFIER_PROMPT.format(user_input=user_input)
        
        chat = Chat(
            model=self.model,
            api=self.api,
            messages=[],
            system_prompt=prompt,
            options=self.options
        )
        
        # Consomme le stream
        raw_output = ""
        try:
            for token in chat.execute_stream():
                raw_output += token
                
            result = extract_json(raw_output)
            if not result:
                return "AMBIGUOUS"
                
            category = str(result.get("category", "AMBIGUOUS")).strip().upper()
            
            if result.get("controlled_substance") or result.get("criminal_activity") or result.get("dangerous_activity"):
                return "ILLEGAL"
                
            if category in ["LEGAL", "ILLEGAL", "AMBIGUOUS"]:
                return category
                
            return "AMBIGUOUS"
        except Exception as e:
            logger.error(f"[Guardrail] Erreur lors de la classification: {e}")
            return "AMBIGUOUS"
