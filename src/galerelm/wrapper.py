"""
SensAI Wrapper — Facade API pour interfaces (ex: Gradio, FastAPI).
Fournit des fonctions fortement typées utilisant les Data Transfer Objects (DTO).
"""
import logging
from typing import Generator, List, Optional

from src.main import SensAI
from src.galerelm.models import Profile, Context, Message, LongTermMemory, Chat
from src.galerelm.models.dto import (
    ProfileResponse, ContextResponse, MessageResponse, 
    ChatCompletionResponse, MemoryResponse, StatusResponse
)

logger = logging.getLogger("galerelm.wrapper")


class SensAIWrapper:
    """
    Interface haut niveau masquant la complexité du framework.
    Retourne exclusivement des objets typés (DTOs).
    """

    def __init__(self, db_url: str = "sqlite:///galerelm.db"):
        self.core = SensAI(db_url=db_url)
        logger.info("SensAIWrapper initialisé avec succès (Typage Strict).")

    def _get_profile_or_raise(self, email: str) -> Profile:
        profile = self.core.session.query(Profile).filter_by(email=email).first()
        if not profile:
            raise ValueError(f"Profil introuvable pour l'email: {email}")
        return profile

    def _get_context_or_raise(self, profile_id: str) -> Context:
        context = self.core.session.query(Context).filter_by(profile_id=profile_id).order_by(Context.id.desc()).first()
        if not context:
            raise ValueError(f"Contexte introuvable pour le profil: {profile_id}")
        return context

    # ── 1. Gestion des Utilisateurs (Profils) ────────────────────────

    def create_profile(self, email: str, name: str, instructions: str) -> ProfileResponse:
        profile = self.core.session.query(Profile).filter_by(email=email).first()
        if not profile:
            profile = Profile(name=name, email=email, instructions=instructions)
            self.core.session.add(profile)
            self.core.session.commit()
            
            context = Context(profile_id=profile.id, context_limit=10)
            self.core.session.add(context)
            self.core.session.commit()
            
        return ProfileResponse(profile.id, profile.name, profile.email, profile.instructions)

    def get_profile(self, email: str) -> Optional[ProfileResponse]:
        profile = self.core.session.query(Profile).filter_by(email=email).first()
        if profile:
            return ProfileResponse(profile.id, profile.name, profile.email, profile.instructions)
        return None

    def update_profile(self, email: str, name: str = None, instructions: str = None) -> ProfileResponse:
        profile = self._get_profile_or_raise(email)
        if name:
            profile.name = name
        if instructions:
            profile.instructions = instructions
        self.core.session.commit()
        return ProfileResponse(profile.id, profile.name, profile.email, profile.instructions)

    def list_profiles(self) -> List[ProfileResponse]:
        profiles = self.core.session.query(Profile).all()
        return [ProfileResponse(p.id, p.name, p.email, p.instructions) for p in profiles]

    # ── 2. Gestion des Sessions (Contextes) ──────────────────────────

    def start_new_chat(self, email: str) -> ContextResponse:
        profile = self._get_profile_or_raise(email)
        new_context = Context(profile_id=profile.id, context_limit=10)
        self.core.session.add(new_context)
        self.core.session.commit()
        return ContextResponse(new_context.id, new_context.profile_id, new_context.context_limit)

    def get_chat_history(self, email: str) -> List[MessageResponse]:
        profile = self._get_profile_or_raise(email)
        context = self._get_context_or_raise(profile.id)
        return [MessageResponse(m.role, m.content) for m in context.messages]

    def clear_chat(self, email: str) -> bool:
        profile = self._get_profile_or_raise(email)
        context = self._get_context_or_raise(profile.id)
        context.messages.clear()
        self.core.session.commit()
        return True

    # ── 3. Inférence & Discussion ────────────────────────────────────

    def _setup_chat_environment(self, email: str, prompt: str) -> Chat:
        profile = self._get_profile_or_raise(email)
        context = self._get_context_or_raise(profile.id)

        self.core.profile = profile
        self.core.context = context

        context.add(Message(role="user", content=prompt), api_client=self.core.api)
        self.core.session.commit()

        system_prompt = self.core._build_augmented_prompt(prompt)

        return Chat(
            model=self.core.model,
            api=self.core.api,
            messages=context.get_messages_copy(),
            system_prompt=system_prompt,
        )

    def chat_stream(self, email: str, prompt: str) -> Generator[str, None, None]:
        llm = self._setup_chat_environment(email, prompt)
        
        accumulated_response = ""
        for token in llm.execute_stream():
            accumulated_response += token
            yield accumulated_response

        if llm.last_response and llm.last_response.message:
            assistant_msg = llm.last_response.message
            self.core.context.add(
                Message(role="assistant", content=assistant_msg.content), 
                api_client=self.core.api
            )
            self.core.session.commit()

    def chat_blocking(self, email: str, prompt: str) -> ChatCompletionResponse:
        llm = self._setup_chat_environment(email, prompt)
        
        for _ in llm.execute_stream():
            pass

        if llm.last_response and llm.last_response.message:
            assistant_msg = llm.last_response.message
            self.core.context.add(
                Message(role="assistant", content=assistant_msg.content), 
                api_client=self.core.api
            )
            self.core.session.commit()
            return ChatCompletionResponse(
                message=MessageResponse(assistant_msg.role, assistant_msg.content),
                eval_count=llm.last_response.eval_count,
                eval_duration=llm.last_response.eval_duration / 1e9
            )
            
        raise RuntimeError("Aucune réponse reçue du modèle.")

    # ── 4. Mémoire Long Terme (RAG) ──────────────────────────────────

    def get_memories(self, email: str) -> List[MemoryResponse]:
        profile = self._get_profile_or_raise(email)
        context = self._get_context_or_raise(profile.id)
        
        if not profile.deep_context or not profile.deep_context.memories:
            return []
            
        return [MemoryResponse(m.id, m.role, m.content) for m in profile.deep_context.memories]

    def search_memories(self, email: str, query: str, top_k: int = 5) -> List[MemoryResponse]:
        profile = self._get_profile_or_raise(email)
        context = self._get_context_or_raise(profile.id)
        
        if not profile.deep_context or not profile.deep_context.memories:
            return []

        results = profile.deep_context.search(query, self.core.api, top_k=top_k)
        return [MemoryResponse(mem.id, mem.role, mem.content, score=score) for score, mem in results]

    def delete_memory(self, memory_id: int) -> bool:
        memory = self.core.session.query(LongTermMemory).filter_by(id=memory_id).first()
        if not memory:
            return False
            
        self.core.session.delete(memory)
        self.core.session.commit()
        return True

    # ── 5. Configuration et Système ──────────────────────────────────

    def get_status(self) -> StatusResponse:
        db_status = "ok" if self.core.engine else "error"
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
            active_model=self.core.model
        )

    def set_active_model(self, model_name: str) -> bool:
        self.core.model = model_name
        return True
