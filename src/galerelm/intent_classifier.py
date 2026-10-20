"""
Module intent_classifier.py
Système orienté objet de classification d'intention (IntentGuardrail) fusionnant
la logique complète de résolution d'ambiguïté et d'analyse JSON avec la classe Prompt.
"""
import json
import logging
import re
from dataclasses import dataclass
from typing import Literal, Optional

from src.config import config
from src.galerelm.models.chat import Chat, Options
from src.galerelm.models.message import Message, MessageList
from src.galerelm.models.prompt import Prompt, PromptBuilder, PromptTemplate
from src.rapideAPI.client import RapideAPI

logger = logging.getLogger("galerelm.intent_classifier")

IntentCategory = Literal["LEGAL", "ILLEGAL", "AMBIGUOUS"]

SAFETY_BLOCKED_RESPONSES: dict[str, str] = {
    "ILLEGAL": "Désolé, je ne peux pas répondre à cette demande pour des raisons de sécurité.",
}

ALIBI_BLOCKED_RESPONSES: dict[str, str] = {
    "LEGAL": "Cela ne te menera nulle part de savoir cela...",
    "AMBIGUOUS": "Requête ambiguë.",
}


@dataclass
class GuardrailDecision:
    """Résultat complet de l'évaluation d'une requête par IntentGuardrail."""
    category: IntentCategory
    allowed: bool
    refusal_message: Optional[str] = None
    details: Optional[dict] = None


class IntentGuardrail:
    """
    Système de classification d'intention pour filtrer ou qualifier les requêtes
    avant exécution par le LLM principal, basé sur PromptBuilder et PromptTemplate.
    """

    def __init__(
        self,
        api: RapideAPI,
        model: str = None,
        classifier_template: Optional[PromptTemplate] = None,
        ambiguity_template: Optional[PromptTemplate] = None,
        blocked_responses: Optional[dict[str, str]] = None,
        policy: Literal["safety", "alibi", "none"] = "safety",
    ):
        self.api = api
        self.model = model or config.DEFAULT_MODEL
        self.options = Options(temperature=0.0, top_k=1, num_predict=128)
        self.classifier_template = classifier_template or PromptTemplate.intent_classifier()
        self.ambiguity_template = ambiguity_template or PromptTemplate.ambiguity_resolver()

        if blocked_responses is not None:
            self.blocked_responses = dict(blocked_responses)
        elif policy == "alibi":
            self.blocked_responses = dict(ALIBI_BLOCKED_RESPONSES)
        elif policy == "safety":
            self.blocked_responses = dict(SAFETY_BLOCKED_RESPONSES)
        else:
            self.blocked_responses = {}

    # ── Construction des Prompts via PromptBuilder ───────────────────

    def build_classifier_prompt(self, user_input: str) -> Prompt:
        return (
            PromptBuilder(self.classifier_template)
            .with_user_query(user_input)
            .build()
        )

    def build_ambiguity_prompt(self, user_input: str) -> Prompt:
        return (
            PromptBuilder(self.ambiguity_template)
            .with_user_query(user_input)
            .build()
        )

    # ── Analyseurs de sortie LLM ─────────────────────────────────────

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
    def parse_simple_category(raw: str) -> IntentCategory:
        """Analyse une réponse textuelle courte (LEGAL / ILLEGAL)."""
        normalized = (raw or "").strip().upper()
        # ILLEGAL doit être vérifié avant LEGAL car "LEGAL" est une sous-chaîne de "ILLEGAL"
        if "ILLEGAL" in normalized:
            return "ILLEGAL"
        if "LEGAL" in normalized:
            return "LEGAL"
        return "AMBIGUOUS"

    # ── Exécution LLM isolée ─────────────────────────────────────────

    def _run_prompt(self, prompt: Prompt) -> str:
        """Exécute un appel LLM déterministe sans historique ni réflexion."""
        chat = Chat(
            model=self.model,
            api=self.api,
            messages=MessageList([Message(role="user", content=prompt.system_content)]),
            options=self.options,
            think=False,
        )
        raw_output = ""
        for token in chat.execute_stream():
            raw_output += token
        return raw_output

    def resolve_ambiguity(self, user_input: str) -> IntentCategory:
        """Second passage de classification lorsqu'une requête est jugée ambiguë ou mal formée."""
        prompt = self.build_ambiguity_prompt(user_input)
        raw_output = self._run_prompt(prompt)
        category = self.parse_simple_category(raw_output)
        if category in {"LEGAL", "ILLEGAL"}:
            return category
        return "AMBIGUOUS"

    def classify(self, user_input: str) -> IntentCategory:
        """Classifie l'intention de l'utilisateur en LEGAL, ILLEGAL ou AMBIGUOUS."""
        prompt = self.build_classifier_prompt(user_input)

        try:
            raw_output = self._run_prompt(prompt)
            result = self.extract_json(raw_output)
            if result is None:
                return self.resolve_ambiguity(user_input)

            controlled = result.get("controlled_substance")
            criminal = result.get("criminal_activity")
            dangerous = result.get("dangerous_activity")
            category = str(result.get("category", "AMBIGUOUS")).strip().upper()

            # Tout signal explicite dangereux/criminel/substance l'emporte
            if controlled is True or criminal is True or dangerous is True:
                return "ILLEGAL"

            if category == "ILLEGAL":
                return "ILLEGAL"

            if category == "AMBIGUOUS":
                return self.resolve_ambiguity(user_input)

            if category == "LEGAL":
                return "LEGAL"

            # Classifie en LEGAL uniquement si les 3 booléens sont explicitement False
            if controlled is False and criminal is False and dangerous is False:
                return "LEGAL"

            return "AMBIGUOUS"
        except Exception as e:
            logger.error(f"[Guardrail] Erreur lors de la classification: {e}")
            return "AMBIGUOUS"

    def evaluate(self, user_input: str) -> GuardrailDecision:
        """
        Évalue la requête et retourne une décision structurée indiquant la catégorie,
        si la requête est autorisée, et le message de refus éventuel.
        """
        category = self.classify(user_input)
        refusal = self.blocked_responses.get(category)
        return GuardrailDecision(
            category=category,
            allowed=(refusal is None),
            refusal_message=refusal,
        )
