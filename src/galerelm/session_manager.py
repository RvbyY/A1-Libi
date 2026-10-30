"""
Module session_manager.py
Encapsule toute la logique métier liée aux Profils, aux Contextes (sessions de chat)
et à la Mémoire Long Terme (DeepContext).
"""
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from src.config import config
from src.galerelm.models import (
    Context,
    DeepContext,
    LongTermMemory,
    Message,
    MessageList,
    Profile,
    PromptTemplate,
)

logger = logging.getLogger("galerelm.session_manager")

# Rôles copiés dans la mémoire longue à l'archivage d'un chat (les messages 'tool' et 'system' sont du bruit)
ARCHIVED_ROLES = ("user", "assistant")


class SessionManager:
    """
    Service gérant le cycle de vie des entités Profile, DeepContext et Context.
    Évite de dupliquer les requêtes ORM entre SensAI, SensAIWrapper et les commandes CLI.
    """

    def __init__(self, default_persona: str = "Alibi"):
        self.default_persona = default_persona

    def ensure_deep_context(self, session: Session, profile: Profile) -> DeepContext:
        """Garantit qu'un profil possède toujours une instance DeepContext attachée."""
        if not profile.deep_context:
            profile.deep_context = DeepContext(vector_limit=config.DEEP_CONTEXT_LIMIT)
            session.commit()
        return profile.deep_context

    def get_profile(self, session: Session, email: str) -> Optional[Profile]:
        profile = session.query(Profile).filter_by(email=email).first()
        if profile:
            self.ensure_deep_context(session, profile)
        return profile

    def get_profile_or_raise(self, session: Session, email: str) -> Profile:
        profile = self.get_profile(session, email)
        if not profile:
            raise ValueError(f"Profil introuvable pour l'email: {email}")
        return profile

    def get_or_create_profile(
        self,
        session: Session,
        email: str,
        name: str = "Utilisateur",
        instructions: Optional[str] = None,
    ) -> Profile:
        """Récupère un profil existant ou le crée avec son DeepContext et un Context initial."""
        profile = session.query(Profile).filter_by(email=email).first()
        if not profile:
            resolved_instructions = (
                instructions
                if instructions
                else PromptTemplate.default_system(persona=self.default_persona).render()
            )
            logger.info(f"[SessionManager] Création d'un nouveau profil ({email}).")
            profile = Profile(name=name, email=email, instructions=resolved_instructions)
            profile.deep_context = DeepContext(vector_limit=config.DEEP_CONTEXT_LIMIT)
            session.add(profile)
            session.commit()

            initial_context = Context(profile_id=profile.id, context_limit=config.CONTEXT_LIMIT)
            session.add(initial_context)
            session.commit()
        else:
            self.ensure_deep_context(session, profile)

        return profile

    def update_profile(
        self,
        session: Session,
        email: str,
        name: Optional[str] = None,
        instructions: Optional[str] = None,
    ) -> Profile:
        profile = self.get_profile_or_raise(session, email)
        if name:
            profile.name = name
        if instructions:
            profile.instructions = instructions
        session.commit()
        return profile

    def list_profiles(self, session: Session) -> List[Profile]:
        return session.query(Profile).all()

    # ── Gestion des Contextes (Conversations) ────────────────────────

    def get_or_create_latest_context(self, session: Session, profile_id: str) -> Context:
        context = (
            session.query(Context)
            .filter_by(profile_id=profile_id)
            .order_by(Context.id.desc())
            .first()
        )
        if not context:
            context = self.create_new_context(session, profile_id)
        return context

    def get_context_or_raise(
        self,
        session: Session,
        profile_id: str,
        context_id: Optional[int] = None,
    ) -> Context:
        query = session.query(Context).filter_by(profile_id=profile_id)
        if context_id is not None:
            query = query.filter_by(id=context_id)
        context = query.order_by(Context.id.desc()).first()
        if not context:
            raise ValueError(f"Contexte introuvable pour le profil: {profile_id}")
        return context

    def create_new_context(
        self,
        session: Session,
        profile_id: str,
        context_limit: Optional[int] = None,
    ) -> Context:
        limit = context_limit if context_limit is not None else config.CONTEXT_LIMIT
        new_context = Context(profile_id=profile_id, context_limit=limit)
        session.add(new_context)
        session.commit()
        return new_context

    def list_contexts(self, session: Session, profile_id: str) -> List[Context]:
        return (
            session.query(Context)
            .filter_by(profile_id=profile_id)
            .order_by(Context.id.desc())
            .all()
        )

    def clear_context(self, session: Session, context: Context) -> int:
        count = len(context.messages)
        context.messages = MessageList([])
        session.commit()
        return count

    # ── Gestion de la Mémoire Long Terme (RAG) ───────────────────────

    def archive_chats(self, session: Session, profile: Profile, api_client=None) -> int:
        """
        Copie dans la mémoire longue les messages de tous les chats du profil qui n'y sont pas encore,
        pour qu'un nouveau chat puisse les retrouver par RAG. Les chats restent intacts.
        Sans cela, seuls les messages qui débordent de CONTEXT_LIMIT étaient archivés :
        une conversation courte était invisible depuis les autres chats.
        Retourne le nombre de messages archivés.
        """
        deep_context = self.ensure_deep_context(session, profile)
        known = {(m.role, m.content) for m in deep_context.memories}
        pending: list[Message] = []
        for context in self.list_contexts(session, profile.id):
            for message in context.messages:
                key = (message.role, message.content)
                if message.role not in ARCHIVED_ROLES or not (message.content or "").strip() or key in known:
                    continue
                known.add(key)
                # Copie détachée : le message d'origine reste dans son chat
                pending.append(Message(role=message.role, content=message.content))

        if not pending:
            return 0
        deep_context.save(MessageList(pending), api_client)
        session.commit()
        logger.info(f"[SessionManager] {len(pending)} messages archivés en mémoire longue.")
        return len(pending)

    def delete_memory(self, session: Session, memory_id: int) -> bool:
        memory = session.query(LongTermMemory).filter_by(id=memory_id).first()
        if not memory:
            return False
        session.delete(memory)
        session.commit()
        return True
