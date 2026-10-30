import logging
from typing import Generator, List, Optional

from src.config import config
from src.galerelm.models.dto import (
    ChatCompletionResponse,
    ContextResponse,
    MemoryResponse,
    MessageResponse,
    ProfileResponse,
    StatusResponse,
)
from src.main import SensAI

logger = logging.getLogger("galerelm.wrapper")


class SensAIWrapper:
    """
    Interface haut niveau masquant la complexité du framework.
    Retourne exclusivement des objets typés (DTOs).
    Thread-safe : chaque requête utilise une session isolée via DatabaseManager
    et délègue la logique métier à SessionManager et ChatEngine.
    """

    def __init__(self, db_url: str = None):
        db_url = db_url or config.DB_URL
        self.core = SensAI(db_url=db_url)
        self.sessions = self.core.session_manager
        self.engine = self.core.chat_engine
        logger.info("SensAIWrapper initialisé avec succès (Typage Strict, Thread-Safe).")

    # ── 1. Gestion des Utilisateurs (Profils) ────────────────────────

    def create_profile(self, email: str, name: str, instructions: str = None) -> ProfileResponse:
        with self.core.db.session_scope() as session:
            profile = self.sessions.get_or_create_profile(
                session=session,
                email=email,
                name=name,
                instructions=instructions,
            )
            return ProfileResponse(profile.id, profile.name, profile.email, profile.instructions)

    def get_profile(self, email: str) -> Optional[ProfileResponse]:
        with self.core.db.session_scope() as session:
            profile = self.sessions.get_profile(session, email)
            if profile:
                return ProfileResponse(profile.id, profile.name, profile.email, profile.instructions)
            return None

    def update_profile(self, email: str, name: str = None, instructions: str = None) -> ProfileResponse:
        with self.core.db.session_scope() as session:
            profile = self.sessions.update_profile(session, email, name=name, instructions=instructions)
            return ProfileResponse(profile.id, profile.name, profile.email, profile.instructions)

    def list_profiles(self) -> List[ProfileResponse]:
        with self.core.db.session_scope() as session:
            profiles = self.sessions.list_profiles(session)
            return [ProfileResponse(p.id, p.name, p.email, p.instructions) for p in profiles]

    # ── 2. Gestion des Sessions (Contextes) ──────────────────────────

    def start_new_chat(self, email: str) -> ContextResponse:
        with self.core.db.session_scope() as session:
            profile = self.sessions.get_profile_or_raise(session, email)
            # Rend les chats précédents retrouvables depuis le nouveau (RAG)
            self.sessions.archive_chats(session, profile, api_client=self.core.api)
            new_context = self.sessions.create_new_context(session, profile.id)
            return ContextResponse(new_context.id, new_context.profile_id, new_context.context_limit)

    def get_chat_history(self, email: str, context_id: int = None) -> List[MessageResponse]:
        with self.core.db.session_scope() as session:
            profile = self.sessions.get_profile_or_raise(session, email)
            context = self.sessions.get_context_or_raise(session, profile.id, context_id)
            return [MessageResponse(m.role, m.content) for m in context.messages]

    def list_chats(self, email: str) -> List[ContextResponse]:
        with self.core.db.session_scope() as session:
            profile = self.sessions.get_profile_or_raise(session, email)
            contexts = self.sessions.list_contexts(session, profile.id)
            return [ContextResponse(c.id, c.profile_id, c.context_limit) for c in contexts]

    def clear_chat(self, email: str) -> bool:
        with self.core.db.session_scope() as session:
            profile = self.sessions.get_profile_or_raise(session, email)
            context = self.sessions.get_context_or_raise(session, profile.id)
            self.sessions.clear_context(session, context)
            return True

    # ── 3. Inférence & Discussion (Déléguée à ChatEngine) ────────────

    def chat_stream(self, email: str, prompt: str, context_id: int = None) -> Generator[str, None, None]:
        with self.core.db.session_scope() as session:
            profile = self.sessions.get_profile_or_raise(session, email)
            context = self.sessions.get_context_or_raise(session, profile.id, context_id)

            accumulated_response = ""
            for token in self.engine.stream_turn(session, profile, context, prompt):
                accumulated_response += token
                yield accumulated_response

    def chat_blocking(self, email: str, prompt: str, context_id: int = None) -> ChatCompletionResponse:
        with self.core.db.session_scope() as session:
            profile = self.sessions.get_profile_or_raise(session, email)
            context = self.sessions.get_context_or_raise(session, profile.id, context_id)

            response = self.engine.execute_turn(session, profile, context, prompt)
            if response and response.message:
                return ChatCompletionResponse(
                    message=MessageResponse(response.message.role, response.message.content),
                    eval_count=response.eval_count,
                    eval_duration=response.eval_duration / 1e9,
                )

            raise RuntimeError("Aucune réponse reçue du modèle.")

    # ── 4. Mémoire Long Terme (RAG) ──────────────────────────────────

    def get_memories(self, email: str) -> List[MemoryResponse]:
        with self.core.db.session_scope() as session:
            profile = self.sessions.get_profile_or_raise(session, email)
            if not profile.deep_context or not profile.deep_context.memories:
                return []
            return [MemoryResponse(m.id, m.role, m.content) for m in profile.deep_context.memories]

    def search_memories(self, email: str, query: str, top_k: int = 5) -> List[MemoryResponse]:
        with self.core.db.session_scope() as session:
            profile = self.sessions.get_profile_or_raise(session, email)
            if not profile.deep_context or not profile.deep_context.memories:
                return []
            results = profile.deep_context.search(query, self.core.api, top_k=top_k)
            return [MemoryResponse(mem.id, mem.role, mem.content, score=score) for score, mem in results]

    def delete_memory(self, memory_id: int) -> bool:
        with self.core.db.session_scope() as session:
            return self.sessions.delete_memory(session, memory_id)

    # ── 5. Configuration et Système ──────────────────────────────────

    def get_status(self) -> StatusResponse:
        db_status = "ok" if self.core.db.is_healthy() else "error"
        api_status = "ok"

        try:
            res = self.core.api.get("api/tags")
            if not res:
                api_status = "error"
        except Exception:
            api_status = "unreachable"

        return StatusResponse(
            db_status=db_status,
            api_status=api_status,
            active_model=self.core.model,
        )

    def set_active_model(self, model_name: str) -> bool:
        self.core.model = model_name
        return True
