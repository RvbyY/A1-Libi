"""
SensAI — Point d'entrée principal du framework LLM.
"""
import os
from galerelm.models.chat import Chat, Options, Message, MessageList
from dotenv import load_dotenv
from rapideAPI.client import RapideAPI
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.galerelm.models import Base, Chat, Message, Context, Profile
from src.rapideAPI import RapideAPI

logger = logging.getLogger("sensai")


class SensAI:
    """
    Classe principale qui encapsule toute la logique du framework :
    - Initialisation de la base de données
    - Gestion du profil utilisateur et de son contexte
    - Exécution des échanges avec le LLM
    """

    def __init__(self, db_url: str = "sqlite:///galerelm.db", model: str = None, api_url: str = None):
        load_dotenv()
        self.model = model or os.getenv("HF_MODEL")
        api_url = api_url or os.getenv("OLLAMA_HOST")

        # ── Base de données ──────────────────────────────────────────
        logger.info(f"Connexion à la base de données ({db_url})...")
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.session = self.SessionLocal()
        logger.info("Base de données initialisée avec succès.")

        # ── API ──────────────────────────────────────────────────────
        self.api = RapideAPI(base_url=api_url)

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
        self.context = self.session.query(Context).filter_by(profile_id=self.profile.id).first()

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

        while True:
            user_prompt = input("Vous : ").strip()

            if not user_prompt:
                continue

            # ── Gestion des commandes (/command) ─────────────────────
            if user_prompt.startswith("/"):
                parts = user_prompt.split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                if command in self._commands:
                    should_quit = self._commands[command](self, args)
                    if should_quit:
                        break
                else:
                    print(f"[!] Commande inconnue : {command}. Tapez /help pour la liste.\n")
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

    # ── Commandes REPL ───────────────────────────────────────────────

    def _cmd_help(self, args: str):
        """Affiche les commandes."""
        print("\n╔═══════════════════════════════════════════════════════════╗")
        print("║                 Commandes Disponibles                   ║")
        print("╠═══════════════════════════════════════════════════════════╣")
        for cmd, handler in self._commands.items():
            doc = handler.__doc__ or ""
            print(f"║  {cmd:<12} {doc:<42} ║")
        print("╚═══════════════════════════════════════════════════════════╝\n")

    def _cmd_quit(self, args: str):
        """Quitter le programme."""
        logger.info("Fermeture du programme demandée par l'utilisateur.")
        print("Au revoir !\n")
        return True

    def _cmd_messages(self, args: str):
        """Lister les messages du contexte."""
        messages = self.context.messages
        if not messages:
            print("\n[i] Aucun message dans le contexte actuel.\n")
            return

        print(f"\n── Messages en contexte ({len(messages)}/{self.context.context_limit}) ──")
        for i, m in enumerate(messages):
            role_icon = {"system": "⚙️", "user": "👤", "assistant": "🤖", "tool": "🔧"}.get(m.role, "❓")
            content_preview = m.content[:80].replace("\n", "↵")
            if len(m.content) > 80:
                content_preview += "..."
            print(f"  {i+1}. {role_icon} [{m.role}] {content_preview}")
        print()

    def _cmd_memories(self, args: str):
        """Lister les mémoires long terme."""
        if not self.context.deep_context or not self.context.deep_context.memories:
            print("\n[i] Aucune mémoire long terme enregistrée.\n")
            return

        memories = self.context.deep_context.memories
        print(f"\n── Mémoires Long Terme ({len(memories)} entrées) ──")
        for i, mem in enumerate(memories):
            role_icon = {"user": "👤", "assistant": "🤖"}.get(mem.role, "❓")
            content_preview = mem.content[:80].replace("\n", "↵")
            if len(mem.content) > 80:
                content_preview += "..."
            print(f"  {i+1}. {role_icon} [{mem.role}] {content_preview}")
        print()

    def _cmd_profile(self, args: str):
        """Afficher le profil courant."""
        p = self.profile
        print(f"\n── Profil ──")
        print(f"  ID           : {p.id}")
        print(f"  Nom          : {p.name}")
        print(f"  Email        : {p.email}")
        print(f"  Instructions : {p.instructions[:100]}{'...' if len(p.instructions) > 100 else ''}")
        print()

    def _cmd_context(self, args: str):
        """Afficher les stats du contexte."""
        ctx = self.context
        mem_count = len(ctx.deep_context.memories) if ctx.deep_context else 0
        print(f"\n── Contexte ──")
        print(f"  ID              : {ctx.id}")
        print(f"  Profile ID      : {ctx.profile_id}")
        print(f"  Messages        : {len(ctx.messages)}/{ctx.context_limit}")
        print(f"  Mémoires LT     : {mem_count}")
        print(f"  Modèle          : {self.model}")
        print()

    def _cmd_payload(self, args: str):
        """Afficher le payload JSON brut."""
        import json
        llm = Chat(
            model=self.model,
            api=self.api,
            messages=self.context.get_messages_copy(),
            system_prompt=self.profile.instructions,
        )
        payload = llm.format()
        print(f"\n── Payload JSON ──")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print()

    def _cmd_clear(self, args: str):
        """Vider le contexte courant."""
        from src.galerelm.models.message import MessageList
        count = len(self.context.messages)
        self.context.messages = MessageList([])
        self.session.commit()
        print(f"\n[✓] {count} messages supprimés du contexte.\n")

    def _cmd_new(self, args: str):
        """Créer un nouveau contexte vierge."""
        self.context = Context(profile_id=self.profile.id, context_limit=10)
        self.session.add(self.context)
        self.session.commit()
        print("\n[✓] Nouveau contexte créé. Historique vierge.\n")

    def _cmd_recall(self, args: str):
        """Rechercher dans la mémoire long terme."""
        if not args:
            print("\n[!] Usage : /recall <votre requête>\n")
            return

        if not self.context.deep_context or not self.context.deep_context.memories:
            print("\n[i] Aucune mémoire long terme enregistrée.\n")
            return

        try:
            results = self.context.deep_context.search(args, self.api, top_k=5)
        except Exception as e:
            print(f"\n[!] Erreur lors de la recherche : {e}\n")
            return

        if not results:
            print("\n[i] Aucun résultat pertinent trouvé.\n")
            return

        print(f"\n── Résultats RAG pour \"{args}\" ({len(results)} trouvés) ──")
        for i, (score, mem) in enumerate(results):
            role_icon = {"user": "👤", "assistant": "🤖"}.get(mem.role, "❓")
            content_preview = mem.content[:100].replace("\n", "↵")
            if len(mem.content) > 100:
                content_preview += "..."
            print(f"  {i+1}. {role_icon} [{mem.role}] (score: {score:.4f}) {content_preview}")
        print()

    # ── Registre des commandes ───────────────────────────────────────

    _commands = {
        "/help":     _cmd_help,
        "/quit":     _cmd_quit,
        "/exit":     _cmd_quit,
        "/q":        _cmd_quit,
        "/messages": _cmd_messages,
        "/memories": _cmd_memories,
        "/profile":  _cmd_profile,
        "/context":  _cmd_context,
        "/payload":  _cmd_payload,
        "/clear":    _cmd_clear,
        "/new":      _cmd_new,
        "/recall":   _cmd_recall,
    }


# ── Point d'entrée ───────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    sensai = SensAI()
    sensai.load_or_create_profile()
    sensai.repl()