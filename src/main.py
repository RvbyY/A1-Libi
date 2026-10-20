"""
SensAI — Point d'entrée principal du framework LLM.
Agît comme une façade légère assemblant DatabaseManager, SessionManager, ChatEngine,
TaskManager/TaskRunner et CommandRegistry.
"""
import logging
from typing import Generator, Optional

from src.commands import CommandRegistry, default_registry
from src.config import config
from src.galerelm.database import DatabaseManager
from src.galerelm.engine import ChatEngine
from src.galerelm.intent_classifier import IntentGuardrail
from src.galerelm.models import Context, Profile, Prompt
from src.galerelm.session_manager import SessionManager
from src.rapideAPI import RapideAPI
from src.repl import TerminalREPL, repl
from src.scheduler.runner import TaskRunner
from src.scheduler.task_manager import TaskManager
from src.tools import ToolRegistry, default_tool_registry

logger = logging.getLogger("sensai")


class SensAI:
    """
    Façade principale du framework coordonnant les composants spécialisés :
    - DatabaseManager : moteur SQLAlchemy et sessions
    - SessionManager : cycle de vie des Profils, Contextes et DeepContext
    - ChatEngine : orchestration Prompt (RAG + Tools) -> Guardrail -> LLM -> Persistance
    - TaskManager / TaskRunner : planification des tâches
    """

    def __init__(
        self,
        db_url: str = None,
        model: str = None,
        api_url: str = None,
        commands: Optional[CommandRegistry] = None,
        tool_registry: Optional[ToolRegistry] = None,
        guardrail: Optional[IntentGuardrail] = None,
        use_guardrail: bool = False,
    ):
        resolved_model = model or config.DEFAULT_MODEL
        api_url = api_url or config.OLLAMA_HOST

        # ── 1. Base de données & Gestionnaire de sessions ────────────
        self.db = DatabaseManager(db_url=db_url)
        self.engine = self.db.engine
        self.SessionLocal = self.db.SessionLocal
        self.session = self.db.create_session()
        self.session_manager = SessionManager()

        # ── 2. Planificateur de tâches ───────────────────────────────
        self.task_manager = TaskManager(self.session)
        self.task_runner = TaskRunner(self.SessionLocal, executor=self.chat)

        # ── 3. Client API, Outils, Guardrail & Moteur d'orchestration ─
        self.api = RapideAPI(base_url=api_url)
        self.tools = tool_registry if tool_registry is not None else default_tool_registry()
        resolved_guardrail = guardrail
        if resolved_guardrail is None and use_guardrail:
            resolved_guardrail = IntentGuardrail(api=self.api, model=resolved_model)

        self.chat_engine = ChatEngine(
            api=self.api,
            model=resolved_model,
            tool_registry=self.tools,
            guardrail=resolved_guardrail,
        )

        # ── 4. Commandes du terminal ─────────────────────────────────
        self.commands = commands if commands is not None else default_registry()

        # ── 5. État de la session active (CLI) ───────────────────────
        self.profile: Optional[Profile] = None
        self.context: Optional[Context] = None

    def enable_guardrail(self, policy: str = "safety") -> "SensAI":
        """Active et configure le classifieur d'intention (IntentGuardrail) sur le ChatEngine."""
        self.chat_engine.guardrail = IntentGuardrail(
            api=self.api,
            model=self.model,
            policy=policy,
        )
        return self

    @property
    def model(self) -> str:
        return self.chat_engine.model

    @model.setter
    def model(self, value: str) -> None:
        self.chat_engine.model = value

    # ── Gestion du profil (Déléguée à SessionManager) ────────────────

    def load_or_create_profile(
        self,
        email: str = "user@sensai.ai",
        name: str = "Utilisateur",
        instructions: str = None,
    ) -> "SensAI":
        """Charge un profil existant ou en crée un nouveau avec son contexte. Retourne self."""
        self.profile = self.session_manager.get_or_create_profile(
            session=self.session,
            email=email,
            name=name,
            instructions=instructions,
        )
        self.context = self.session_manager.get_or_create_latest_context(
            session=self.session,
            profile_id=self.profile.id,
        )
        logger.info(
            f"Session active : {self.profile.name} ({self.profile.email}) — "
            f"{len(self.context.messages)} messages en contexte."
        )
        return self

    # ── Inférence & Discussion (Déléguées à ChatEngine) ──────────────

    def _ensure_ready(self) -> None:
        if not self.profile or not self.context:
            raise RuntimeError("Aucun profil chargé. Appelez load_or_create_profile() d'abord.")

    def stream_chat(self, prompt: str) -> Generator[str, None, None]:
        """Streame la réponse token par token et persiste automatiquement l'échange."""
        self._ensure_ready()
        yield from self.chat_engine.stream_turn(
            session=self.session,
            profile=self.profile,
            context=self.context,
            user_prompt=prompt,
        )

    def chat(self, prompt: str) -> str:
        """Envoie un prompt au LLM et retourne la réponse complète."""
        return "".join(self.stream_chat(prompt))

    def build_prompt(self, query: str = "", profile: Profile = None) -> Prompt:
        """Construit un objet Prompt structuré via le ChatEngine."""
        prof = profile or self.profile
        return self.chat_engine.build_prompt(prof, query)

    def _build_augmented_prompt(self, query: str, profile: Profile = None) -> str:
        """Méthode de compatibilité retournant la chaîne du prompt système enrichi."""
        return self.build_prompt(query=query, profile=profile).system_content


# ── Point d'entrée ───────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    sensai = SensAI()
    sensai.load_or_create_profile()
    TerminalREPL(sensai).run()
