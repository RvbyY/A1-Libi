"""
SensAI — Point d'entrée principal du framework LLM.
"""
import os
import logging
from dotenv import load_dotenv

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.galerelm.models import Base, Chat, Message, Context, Profile
from src.rapideAPI import RapideAPI
from src.commands import CommandRegistry, CommandResult, default_registry

from src.scheduler.task_manager import TaskManager
import threading
from src.scheduler.runner import TaskRunner

logger = logging.getLogger("sensai")


class SensAI:
    """
    Classe principale qui encapsule toute la logique du framework :
    - Initialisation de la base de données
    - Gestion du profil utilisateur et de son contexte
    - Exécution des échanges avec le LLM
    """

    def __init__(self, db_url: str = "sqlite:///galerelm.db", model: str = None, api_url: str = None,
                 commands: CommandRegistry = None):
        load_dotenv()
        self.model = model or os.getenv("HF_MODEL")
        api_url = api_url or os.getenv("OLLAMA_HOST")

        # ── Base de données ──────────────────────────────────────────
        logger.info(f"Connexion à la base de données ({db_url})...")
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.session = self.SessionLocal()
        self.task_manager = TaskManager(self.session)
        self.task_runner = TaskRunner(self.SessionLocal, executor=self.chat,)
        logger.info("Base de données initialisée avec succès.")

        # ── API ──────────────────────────────────────────────────────
        self.api = RapideAPI(base_url=api_url)

        # ── Commandes du terminal ────────────────────────────────────
        self.commands = commands if commands is not None else default_registry()

        # ── Profil & Contexte ────────────────────────────────────────
        self.profile: Profile = None
        self.context: Context = None

    # ── Gestion du profil ────────────────────────────────────────────

    def load_or_create_profile(self, email: str = "user@sensai.ai", name: str = "Utilisateur",
                                instructions: str = "Tu es SensAI, un assistant intelligent et concis.") -> "SensAI":
        """Charge un profil existant ou en crée un nouveau. Retourne self pour le chaînage."""
        self.profile = self.session.query(Profile).filter_by(email=email).first()

        if not self.profile:
            logger.info(f"Création d'un nouveau profil ({email}).")
            self.profile = Profile(name=name, email=email, instructions=instructions)
            self.session.add(self.profile)
            self.session.commit()
        else:
            logger.info(f"Profil trouvé : {self.profile.name} ({self.profile.email})")

        # Charge le contexte le plus récent pour ce profil
        self.context = (
            self.session.query(Context)
            .filter_by(profile_id=self.profile.id)
            .order_by(Context.id.desc())
            .first()
        )

        if not self.context:
            logger.info("Aucun contexte trouvé. Création d'un nouveau contexte.")
            self.context = Context(profile_id=self.profile.id, context_limit=10)
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

        # 2. Construire le Chat avec RAG (injection de souvenirs pertinents)
        system_prompt = self._build_augmented_prompt(prompt)
        llm = Chat(
            model=self.model,
            api=self.api,
            messages=self.context.get_messages_copy(),
            system_prompt=system_prompt,
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

    def _build_augmented_prompt(self, query: str) -> str:
        """
        Construit le prompt système enrichi avec les mémoires long terme pertinentes (RAG).
        Si aucune mémoire n'est trouvée, retourne les instructions brutes du profil.
        """
        base_instructions = self.profile.instructions

        if not self.context.deep_context or not self.context.deep_context.memories:
            return base_instructions

        try:
            results = self.context.deep_context.search(query, self.api, top_k=3)
        except Exception as e:
            logger.warning(f"[RAG] Recherche de mémoires échouée : {e}")
            return base_instructions

        if not results:
            return base_instructions

        memory_lines = []
        for score, mem in results:
            memory_lines.append(f"- [{mem.role}] {mem.content}")

        augmented = (
            f"{base_instructions}\n\n"
            f"Voici des informations pertinentes issues de conversations précédentes :\n"
            + "\n".join(memory_lines)
        )
        logger.info(f"[RAG] {len(results)} mémoires injectées dans le prompt système.")
        return augmented

    # ── Boucle interactive (REPL) ────────────────────────────────────

    def repl(self):
        """Lance une boucle interactive de chat dans le terminal."""
        if not self.profile or not self.context:
            raise RuntimeError("Aucun profil chargé. Appelez load_or_create_profile() d'abord.")

        print(f"\nBienvenue {self.profile.name} ! (Historique: {len(self.context.messages)} messages chargés)")
        print("Tapez /help pour voir les commandes disponibles.\n")

        logger.info("Démarrage de la boucle interactive de discussion.")

        runner_thread = threading.Thread(
            target=self.task_runner.run_forever,
            daemon=True,
        )
        
        runner_thread.start()

        while True:
            user_prompt = input("Vous : ").strip()

            if not user_prompt:
                continue

            # ── Gestion des commandes (/command) ─────────────────────
            if self.commands.is_command(user_prompt):
                if self.commands.dispatch(user_prompt, self) is CommandResult.QUIT:
                    break
                continue

            # ── Échange normal avec le LLM ───────────────────────────
            self.context.add(Message(role="user", content=user_prompt), api_client=self.api)
            self.session.commit()

            system_prompt = self._build_augmented_prompt(user_prompt)
            llm = Chat(
                model=self.model,
                api=self.api,
                messages=self.context.get_messages_copy(),
                system_prompt=system_prompt,
            )

            print("\nSensAI : ", end="", flush=True)

            try:
                for token in llm.execute_stream():
                    print(token, end="", flush=True)
                print("\n")
            except Exception as e:
                print(f"\n[!] Erreur de connexion : {e}\n")
                continue

            if llm.last_response and llm.last_response.message:
                assistant_msg = llm.last_response.message
                self.context.add(Message(
                    role="assistant",
                    content=assistant_msg.content,
                    images=assistant_msg.images,
                ), api_client=self.api)
                self.session.commit()
            else:
                print("[!] Erreur: Aucune réponse retournée par le modèle.")

# ── Point d'entrée ───────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    sensai = SensAI()
    sensai.load_or_create_profile()
    sensai.repl()