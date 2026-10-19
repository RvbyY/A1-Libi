import json
import re
import logging
from typing import Optional

from src.rapideAPI.client import RapideAPI
from src.galerelm.models.chat import Chat, Options
from src.galerelm.models.prompt import PromptTemplate
from src.config import config

logger = logging.getLogger("galerelm.intent_classifier")


class IntentGuardrail:
    """
    Système de classification d'intention orienté objet pour filtrer ou qualifier
    les requêtes avant exécution, en s'appuyant sur PromptTemplate.
    """

    def __init__(
        self,
        api: RapideAPI,
        model: str = None,
        classifier_template: Optional[PromptTemplate] = None,
        ambiguity_template: Optional[PromptTemplate] = None,
    ):
        self.api = api
        self.model = model or config.DEFAULT_MODEL
        self.options = Options(temperature=0.0, top_k=1, num_predict=128)
        self.classifier_template = classifier_template or PromptTemplate.intent_classifier()
        self.ambiguity_template = ambiguity_template or PromptTemplate.ambiguity_resolver()

    @staticmethod
    def extract_json(raw: str) -> Optional[dict]:
        """Extrait le premier bloc JSON valide d'une réponse brute du LLM."""
        if not raw:
            return None
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def parse_simple_category(raw: str) -> str:
        """Analyse une réponse textuelle courte (LEGAL / ILLEGAL)."""
        normalized = (raw or "").strip().upper()
        if "ILLEGAL" in normalized:
            return "ILLEGAL"
        if "LEGAL" in normalized:
            return "LEGAL"
        return "AMBIGUOUS"

    def _run_prompt(self, rendered_prompt: str) -> str:
        """Exécute un appel LLM déterministe avec le prompt fourni."""
        chat = Chat(
            model=self.model,
            api=self.api,
            messages=[],
            system_prompt=rendered_prompt,
            options=self.options,
        )
        raw_output = ""
        for token in chat.execute_stream():
            raw_output += token
        return raw_output

    def resolve_ambiguity(self, user_input: str) -> str:
        """Second passage de classification lorsqu'une requête est jugée ambiguë."""
        prompt = self.ambiguity_template.render(user_input=user_input)
        raw_output = self._run_prompt(prompt)
        category = self.parse_simple_category(raw_output)
        if category in {"LEGAL", "ILLEGAL"}:
            return category
        return "AMBIGUOUS"

    def classify(self, user_input: str) -> str:
        """Classifie l'intention de l'utilisateur en LEGAL, ILLEGAL ou AMBIGUOUS."""
        prompt = self.classifier_template.render(user_input=user_input)

        try:
            raw_output = self._run_prompt(prompt)
            result = self.extract_json(raw_output)
            if not result:
                return self.resolve_ambiguity(user_input)

            controlled = result.get("controlled_substance")
            criminal = result.get("criminal_activity")
            dangerous = result.get("dangerous_activity")
            category = str(result.get("category", "AMBIGUOUS")).strip().upper()

            if controlled is True or criminal is True or dangerous is True:
                return "ILLEGAL"

            if category == "ILLEGAL":
                return "ILLEGAL"

            if category == "AMBIGUOUS":
                return self.resolve_ambiguity(user_input)

            if category == "LEGAL":
                return "LEGAL"

            if controlled is False and criminal is False and dangerous is False:
                return "LEGAL"

            return "AMBIGUOUS"
        except Exception as e:
            logger.error(f"[Guardrail] Erreur lors de la classification: {e}")
            return "AMBIGUOUS"

