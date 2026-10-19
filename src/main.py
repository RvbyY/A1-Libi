from src.config import config
"""
SensAI — Point d'entrée principal du framework LLM.
"""
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.galerelm.models import Base, Chat, Message, Context, Profile, Prompt, PromptBuilder, PromptTemplate
from src.rapideAPI import RapideAPI
from src.commands import CommandRegistry, default_registry

from src.scheduler.task_manager import TaskManager
from src.scheduler.runner import TaskRunner

from src.repl import repl

logger = logging.getLogger("sensai")


class SensAI:
    """
    Classe principale qui encapsule toute la logique du framework :
    - Initialisation de la base de données
    - Gestion du profil utilisateur et de son contexte
    - Exécution des échanges avec le LLM
    """

    def __init__(
        self,
        db_url: str = None,
        model: str = None,
        api_url: str = None,
        commands: CommandRegistry = None,
    ):
        db_url = db_url or config.DB_URL
        self.model = model or config.DEFAULT_MODEL
        api_url = api_url or config.OLLAMA_HOST

        # ── Base de données ──────────────────────────────────────────
        logger.info(f"Connexion à la base de données ({db_url})...")
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.session = self.SessionLocal()
        self.task_manager = TaskManager(self.session)
        self.task_runner = TaskRunner(self.SessionLocal, executor=self.chat)
        logger.info("Base de données initialisée avec succès.")

        # ── API ──────────────────────────────────────────────────────
        self.api = RapideAPI(base_url=api_url)

        # ── Commandes du terminal ────────────────────────────────────
        self.commands = commands if commands is not None else default_registry()

        # ── Profil & Contexte ────────────────────────────────────────
        self.profile: Profile = None
        self.context: Context = None

    # ── Gestion du profil ────────────────────────────────────────────

    def load_or_create_profile(
        self,
        email: str = "user@sensai.ai",
        name: str = "Utilisateur",
        instructions: str = None,
    ) -> "SensAI":
        """Charge un profil existant ou en crée un nouveau. Retourne self pour le chaînage."""
        if instructions is None:
            instructions = PromptTemplate.default_system(persona="Alibi").render()

        self.profile = self.session.query(Profile).filter_by(email=email).first()

        if not self.profile:
            logger.info(f"Création d'un nouveau profil ({email}).")
            self.profile = Profile(name=name, email=email, instructions=instructions)
            from src.galerelm.models.deep_context import DeepContext
            self.profile.deep_context = DeepContext(vector_limit=config.DEEP_CONTEXT_LIMIT)
            self.session.add(self.profile)
            self.session.commit()
        else:
            logger.info(f"Profil trouvé : {self.profile.name} ({self.profile.email})")
            if not self.profile.deep_context:
                from src.galerelm.models.deep_context import DeepContext
                self.profile.deep_context = DeepContext(vector_limit=config.DEEP_CONTEXT_LIMIT)
                self.session.commit()

        # Charge le contexte le plus récent pour ce profil
        self.context = (
            self.session.query(Context)
            .filter_by(profile_id=self.profile.id)
            .order_by(Context.id.desc())
            .first()
        )

        if not self.context:
            logger.info("Aucun contexte trouvé. Création d'un nouveau contexte.")
            self.context = Context(profile_id=self.profile.id, context_limit=config.CONTEXT_LIMIT)
            self.session.add(self.context)
            self.session.commit()
        else:
            logger.info(f"Contexte chargé. Messages en mémoire : {len(self.context.messages)}")

        return self

    # ── Échange unique ───────────────────────────────────────────────

    def chat(self, prompt: str) -> str:
        """
        Envoie un prompt au LLM et retourne la réponse complète.
        Persiste automatiquement les messages (user + assistant) dans le contexte.
        """
        if not self.profile or not self.context:
            raise RuntimeError("Aucun profil chargé. Appelez load_or_create_profile() d'abord.")

        # 1. Persister le message utilisateur
        self.context.add(Message(role="user", content=prompt), api_client=self.api)
        self.session.commit()

        # 2. Construire le Chat avec PromptBuilder (injection RAG)
        built_prompt = self.build_prompt(prompt)
        llm = Chat(
            model=self.model,
            api=self.api,
            messages=self.context.get_messages_copy(),
            system_prompt=built_prompt,
        )

        # 3. Streamer la réponse
        response_parts = []
        for token in llm.execute_stream():
            response_parts.append(token)

        # 4. Persister la réponse assistant
        full_response = "".join(response_parts)
        if llm.last_response and llm.last_response.message:
            assistant_msg = llm.last_response.message
            self.context.add(Message(
                role="assistant",
                content=assistant_msg.content,
                images=assistant_msg.images,
            ), api_client=self.api)
            self.session.commit()
        else:
            logger.error("Aucune réponse retournée par le modèle.")

        return full_response

    def build_prompt(self, query: str = "", profile: Profile = None) -> Prompt:
        """
        Construit un objet Prompt structuré via PromptBuilder (instructions profil + RAG).
        """
        prof = profile or getattr(self, "profile", None)
        if not prof:
            return Prompt(system_content="", user_content=query)

        builder = PromptBuilder().with_profile(prof).with_user_query(query)
        if query:
            builder.with_rag(prof, query, self.api, top_k=3)
        return builder.build()

    def _build_augmented_prompt(self, query: str, profile: Profile = None) -> str:
        """
        Construit le prompt système enrichi avec les mémoires long terme pertinentes (RAG).
        Délègue désormais à PromptBuilder via build_prompt().
        """
        return self.build_prompt(query=query, profile=profile).system_content

# ── Point d'entrée ───────────────────────────────────────────────────

if __name__ == "__main__":
    # logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logging.basicConfig(level=logging.ERROR)
    sensai = SensAI()
    sensai.load_or_create_profile()
    repl(sensai)

# ollama_response = llm.last_response

# if ollama_response:
#     print("\n--- OBJET CHATRESPONSE SAUVEGARDÉ ---")
#     print(f"Modèle: {ollama_response.model}")
#     print(f"Tokens évalués: {ollama_response.eval_count}")
#     print(f"Temps de génération: {ollama_response.eval_duration / 1e9:.2f} s")
# else:
#     print("\nErreur: Flux interrompu avant la fin, réponse incomplète.")
