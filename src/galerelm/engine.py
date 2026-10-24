"""
Module engine.py
Orchestrateur central (ChatEngine) gérant le cycle complet d'un tour de conversation :
Message Utilisateur -> Guardrail -> Prompt (RAG + Tools) -> LLM Stream / Graphe Anti-Hallucination -> ToolExecutor -> Persistance.
"""
import logging
from typing import Any, Callable, Generator, Optional

from src.config import config
from src.galerelm.graph import AntiHallucinationWorkflow, HallucinationGrader
from src.galerelm.intent_classifier import IntentGuardrail
from src.galerelm.models import (
    Chat,
    ChatResponse,
    Context,
    Message,
    Profile,
    Prompt,
    PromptBuilder,
    ToolsList,
)
from src.rapideAPI.client import RapideAPI
from src.tools.registry import ToolExecutor, ToolRegistry

logger = logging.getLogger("galerelm.engine")


class ChatEngine:
    """
    Service d'orchestration d'une conversation avec le LLM.
    Centralise tout le pipeline :
    User Message -> Guardrail -> Prompt (RAG + Tools) -> LLM Stream (ou AntiHallucinationWorkflow) -> ToolExecutor -> Persistence.
    """

    def __init__(
        self,
        api: RapideAPI,
        model: str = None,
        tool_registry: Optional[ToolRegistry] = None,
        guardrail: Optional[IntentGuardrail] = None,
        hallucination_grader: Optional[HallucinationGrader] = None,
        max_hallucination_retries: int = 2,
        blocked_responses: Optional[dict[str, str]] = None,
        rag_top_k: int = 3,
        on_event: Optional[Callable[[str, str, str], None]] = None,
    ):
        self.api = api
        self.model = model or config.DEFAULT_MODEL
        self.tool_registry = tool_registry
        self.tool_executor = ToolExecutor(tool_registry) if tool_registry else None
        self.guardrail = guardrail
        self.hallucination_grader = hallucination_grader
        self.max_hallucination_retries = max_hallucination_retries
        self.blocked_responses = blocked_responses or {}
        self.rag_top_k = rag_top_k
        self.on_event = on_event
        self.last_response: Optional[ChatResponse] = None
        self.last_graph_state: Optional[dict[str, Any]] = None
        self.last_built_prompt: Optional[Prompt] = None

    def _emit(self, node_id: str, state: str, detail: str = "") -> None:
        if self.on_event:
            self.on_event(node_id, state, detail)

    def set_tool_registry(self, registry: Optional[ToolRegistry]) -> None:
        self.tool_registry = registry
        self.tool_executor = ToolExecutor(registry) if registry else None

    def enable_anti_hallucination(self, max_retries: int = 2) -> "ChatEngine":
        """Active le graphe par nœuds AntiHallucinationWorkflow sur ce moteur."""
        self.hallucination_grader = HallucinationGrader(api=self.api, model=self.model)
        self.max_hallucination_retries = max_retries
        return self

    # ── 1. Construction du Prompt (Profil + RAG + Outils) ────────────

    def build_prompt(self, profile: Optional[Profile], query: str = "") -> Prompt:
        """
        Construit l'objet Prompt enrichi avec les instructions du profil,
        les souvenirs RAG et les définitions d'outils.
        """
        if not profile:
            return Prompt(system_content="", user_content=query)

        builder = PromptBuilder().with_profile(profile).with_user_query(query)
        if self.tool_registry:
            builder.with_tools(self.tool_registry)
        if query:
            self._emit("retrieve", "active", f"Recherche RAG top-{self.rag_top_k}")
            builder.with_rag(profile, query, self.api, top_k=self.rag_top_k)
            self._emit("retrieve", "success", "Contexte vectoriel extrait")
        self._emit("prompt", "active", "Assemblage PromptBuilder")
        built = builder.build()
        self.last_built_prompt = built
        # self._emit("prompt", "success", f"Prompt prêt ({len(built.render_system())} car.)")
        return built

    def _get_tools_list(self) -> ToolsList:
        """Convertit les outils du ToolRegistry en ToolsList via to_tools_list()."""
        if not self.tool_registry:
            return ToolsList([])
        return self.tool_registry.to_tools_list()

    # ── 2. Guardrail (Classification d'intention) ────────────────────

    def check_guardrail(self, user_prompt: str) -> Optional[str]:
        """
        Vérifie l'intention de la requête via IntentGuardrail.
        Retourne un message de refus si la catégorie est bloquée,
        ou None si la requête est autorisée à poursuivre vers le LLM.
        """
        if self.guardrail is None:
            self._emit("guardrail", "success", "Guardrail désactivé (LEGAL)")
            return None

        self._emit("guardrail", "active", "Analyse d'intention en cours...")
        if self.blocked_responses:
            category = self.guardrail.classify(user_prompt)
            logger.info(f"[ChatEngine] Intention classifiée : {category}")
            refusal = self.blocked_responses.get(category)
            self._emit(
                "guardrail",
                "error" if refusal else "success",
                f"Catégorie : {category}",
            )
            return refusal

        if hasattr(self.guardrail, "evaluate") and callable(self.guardrail.evaluate):
            decision = self.guardrail.evaluate(user_prompt)
            logger.info(f"[ChatEngine] Intention classifiée : {decision.category} (allowed={decision.allowed})")
            self._emit(
                "guardrail",
                "success" if decision.allowed else "error",
                f"Catégorie : {decision.category}",
            )
            return decision.refusal_message

        category = self.guardrail.classify(user_prompt)
        logger.info(f"[ChatEngine] Intention classifiée : {category}")
        self._emit("guardrail", "success", f"Catégorie : {category}")
        return None

    # ── 3. Préparation de la requête Chat ────────────────────────────

    def prepare_chat(
        self,
        session,
        profile: Profile,
        context: Context,
        user_prompt: str,
    ) -> Chat:
        """
        Persiste le message utilisateur, construit le prompt enrichi (RAG + Tools)
        et retourne l'instance Chat prête à être exécutée.
        """
        context.add(Message(role="user", content=user_prompt), api_client=self.api)
        session.commit()

        built_prompt = self.build_prompt(profile, user_prompt)
        return Chat(
            model=self.model,
            api=self.api,
            messages=context.get_messages_copy(),
            tools=self._get_tools_list(),
            system_prompt=built_prompt,
        )

    # ── 4. Exécution des Outils & Persistance ────────────────────────

    def _execute_tool_calls(
        self,
        session,
        profile: Profile,
        context: Context,
        assistant_msg: Message,
    ) -> list[str]:
        """Délègue l'exécution des tool_calls à ToolExecutor et retourne les messages produits."""
        if not self.tool_regex_ready() or not assistant_msg.tool_calls:
            self._emit("tools", "idle", "Aucun appel d'outil")
            return []

        self._emit("tools", "active", f"Exécution de {len(assistant_msg.tool_calls)} outil(s)")
        tool_ctx = self.tool_executor.build_tool_context(
            profile=profile,
            session=session,
            context=context,
            api=self.api,
        )
        results = self.tool_executor.execute_calls(assistant_msg, tool_ctx)
        self._emit("tools", "success", f"{len(results)} outil(s) terminé(s)")
        return [f"[{name}] {res.message}" for name, res in results]

    def tool_regex_ready(self) -> bool:
        if self.tool_registry and self.tool_executor is None:
            self.tool_executor = ToolExecutor(self.tool_registry)
        return self.tool_executor is not None

    def persist_response(
        self,
        session,
        profile: Profile,
        context: Context,
        llm: Chat,
        execute_tools: bool = True,
    ) -> Optional[Message]:
        """
        Enregistre la réponse de l'assistant dans le contexte et exécute les éventuels outils.
        """
        self.last_response = llm.last_response
        if not llm.last_response or not llm.last_response.message:
            logger.error("[ChatEngine] Aucune réponse retournée par le modèle.")
            return None

        assistant_msg = llm.last_response.message
        persisted_msg = Message(
            role="assistant",
            content=assistant_msg.content,
            images=assistant_msg.images,
            tool_calls=assistant_msg.tool_calls,
        )
        context.add(persisted_msg, api_client=self.api)
        session.commit()

        if execute_tools:
            self._execute_tool_calls(session, profile, context, persisted_msg)
        self._emit("persist", "success", "Réponse sauvegardée en BDD")
        return assistant_msg

    # ── 5. Exécution par Nœuds (AntiHallucinationWorkflow) ───────────

    def run_workflow_turn(
        self,
        session,
        profile: Profile,
        context: Context,
        user_prompt: str,
    ) -> dict[str, Any]:
        """
        Exécute le tour de conversation à travers le graphe de nœuds AntiHallucinationWorkflow
        (retrieve -> generate -> tools -> grade -> regenerate/accept) et persiste le résultat validé.
        """
        context.add(Message(role="user", content=user_prompt), api_client=self.api)
        session.commit()

        workflow = AntiHallucinationWorkflow(
            api=self.api,
            model=self.model,
            grader=self.hallucination_grader,
            tool_registry=self.tool_registry,
            rag_top_k=self.rag_top_k,
            max_retries=self.max_hallucination_retries,
            on_event=self.on_event,
        )
        final_state = workflow.run(session, profile, context, user_prompt)
        self.last_graph_state = final_state
        self.last_built_prompt = final_state.get("built_prompt")

        last_llm: Optional[Chat] = final_state.get("last_llm")
        if last_llm is not None:
            # Les outils ont déjà été exécutés dans le nœud 'tools' du graphe s'il y en avait
            self.persist_response(session, profile, context, last_llm, execute_tools=False)

        return final_state

    # ── 6. Pipeline d'exécution (Stream & Bloquant) ──────────────────

    def stream_turn(
        self,
        session,
        profile: Profile,
        context: Context,
        user_prompt: str,
    ) -> Generator[str, None, Optional[ChatResponse]]:
        """
        Exécute un tour complet :
        - Vérifie d'abord IntentGuardrail.
        - Si hallucination_grader est activé, exécute le graphe de nœuds AntiHallucinationWorkflow
          et yield la réponse vérifiée.
        - Sinon, streame directement les tokens en temps réel depuis Chat.
        """
        self._emit("input", "success", f"Message reçu ({len(user_prompt)} car.)")
        refusal = self.check_guardrail(user_prompt)
        if refusal is not None:
            context.add(Message(role="user", content=user_prompt), api_client=self.api)
            context.add(Message(role="assistant", content=refusal), api_client=self.api)
            session.commit()
            self._emit("persist", "warning", "Refus Guardrail enregistré")
            self.last_response = ChatResponse(
                model=self.model,
                created_at="",
                message=Message(role="assistant", content=refusal),
                done=True,
                done_reason="guardrail",
                total_duration=0,
                load_duration=0,
                prompt_eval_count=0,
                prompt_eval_cached_count=0,
                prompt_eval_duration=0,
                eval_count=0,
                eval_duration=0,
            )
            yield refusal
            return self.last_response

        if self.hallucination_grader is not None:
            state = self.run_workflow_turn(session, profile, context, user_prompt)
            answer = state.get("candidate_answer", "")
            if answer:
                yield answer
            return self.last_response

        llm = self.prepare_chat(session, profile, context, user_prompt)
        self._emit("generate", "active", f"Streaming depuis {self.model}...")

        for token in llm.execute_stream():
            yield token

        self._emit("generate", "success", "Génération terminée")
        self.persist_response(session, profile, context, llm)
        return self.last_response

    def execute_turn(
        self,
        session,
        profile: Profile,
        context: Context,
        user_prompt: str,
    ) -> Optional[ChatResponse]:
        """Exécute un tour complet en mode bloquant et retourne la ChatResponse finale."""
        for _ in self.stream_turn(session, profile, context, user_prompt):
            pass
        return self.last_response
