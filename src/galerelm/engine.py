"""
Module engine.py
Orchestrateur central (ChatEngine) gérant le cycle complet d'un tour de conversation :
Message Utilisateur -> Guardrail -> Prompt (RAG + Tools) -> LLM Stream / Graphe Anti-Hallucination -> ToolExecutor -> Persistance.
"""
import json
import logging
import time
from typing import TYPE_CHECKING, Any, Callable, Generator, Optional

from sqlalchemy.orm import object_session

from src.config import config
from src.galerelm.graph import AntiHallucinationWorkflow, HallucinationGrader
from src.galerelm.intent_classifier import IntentGuardrail
from src.galerelm.documents import DocumentStore
from src.galerelm.models.interaction_log import TEXT_PREVIEW, InteractionLog
from src.galerelm.output_guardrail import OutputGuardrail
from src.galerelm.prompt_simplifier import replace_last_user_message, simplify
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

if TYPE_CHECKING:
    # Import seulement pour les annotations : src.tools importe src.galerelm, un import réel serait circulaire.
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
        tool_registry: Optional["ToolRegistry"] = None,
        guardrail: Optional[IntentGuardrail] = None,
        hallucination_grader: Optional[HallucinationGrader] = None,
        max_hallucination_retries: int = 2,
        blocked_responses: Optional[dict[str, str]] = None,
        rag_top_k: int = 3,
        on_event: Optional[Callable[[str, str, str], None]] = None,
        confirm_tool: Optional[Callable[[str, dict], bool]] = None,
        on_tool_call: Optional[Callable[[str, dict, Any, float], None]] = None,
        max_tool_rounds: int = 3,
        simplify_prompt: bool = True,
        output_guardrail: Optional[OutputGuardrail] = None,
    ):
        self.api = api
        # Filtre de sortie (EV2) : données personnelles anonymisées ou réponse refusée, à l'affichage et en base
        self.output_guardrail = output_guardrail
        # Persona actif (A5) : nom, ton et instructions de l'agent ; modifiable en cours de session
        self.persona: Optional[dict] = None
        # Documents ingérés (R1) : recherche des extraits pertinents pour chaque question
        self.documents = DocumentStore()
        # Allège le message (tics, politesse...) avant Guardrail et LLM ; l'historique garde l'original
        self.simplify_prompt = simplify_prompt
        self.last_clean_prompt: Optional[str] = None
        # Nombre max de relances du modèle après exécution d'outils (évite les boucles d'appels infinies)
        self.max_tool_rounds = max_tool_rounds
        self.last_tool_outputs: list[str] = []
        # Outils appelés pendant l'échange en cours (nom, succès), pour le journal (EV3)
        self._turn_tools: list[tuple[str, bool]] = []
        # Demande à l'utilisateur d'autoriser un outil sensible (email, discord...) ; None = toujours refuser
        self.confirm_tool = confirm_tool
        # Reçoit (nom, arguments, ToolResult, durée ms) après chaque appel d'outil (logs CLI)
        self.on_tool_call = on_tool_call
        self.model = model or config.DEFAULT_MODEL
        self.tool_registry = tool_registry
        self.tool_executor = self._new_executor(tool_registry)
        self.guardrail = guardrail
        self.hallucination_grader = hallucination_grader
        self.max_hallucination_retries = max_hallucination_retries
        self.blocked_responses = blocked_responses or {}
        self.rag_top_k = rag_top_k
        self.on_event = on_event
        self.last_response: Optional[ChatResponse] = None
        self.last_graph_state: Optional[dict[str, Any]] = None
        # Dernier verdict du juge (EV1), en mode anti-hallucination
        self.last_grade = None
        self.last_built_prompt: Optional[Prompt] = None

    def _emit(self, node_id: str, state: str, detail: str = "") -> None:
        if self.on_event:
            self.on_event(node_id, state, detail)

    def _confirm_tool(self, name: str, arguments: dict) -> bool:
        """Relaie la demande de confirmation au callback courant (il peut être défini après la création)."""
        return self.confirm_tool is not None and self.confirm_tool(name, arguments)

    def _notify_tool_call(self, name: str, arguments: dict, result: Any, duration_ms: float) -> None:
        """Relaie chaque appel d'outil à l'observateur courant (il peut être défini après la création)."""
        self._turn_tools.append((name, bool(getattr(result, "success", False))))
        if self.on_tool_call is not None:
            self.on_tool_call(name, arguments, result, duration_ms)

    def _new_executor(self, registry: Optional["ToolRegistry"]) -> Optional["ToolExecutor"]:
        if not registry:
            return None
        from src.tools.registry import ToolExecutor

        return ToolExecutor(registry, confirm=self._confirm_tool, on_call=self._notify_tool_call)

    def set_persona(self, key: Optional[str]) -> dict:
        """Change l'agent pour les prochains messages. L'historique de la conversation est gardé."""
        self.persona = config.persona(key)
        self._emit("prompt", "success", f"Persona : {self.persona['name']}")
        return self.persona

    def set_tool_registry(self, registry: Optional["ToolRegistry"]) -> None:
        self.tool_registry = registry
        self.tool_executor = self._new_executor(registry)

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

        builder = PromptBuilder().with_profile(profile).with_agent(self.persona).with_user_query(query)
        if self.tool_registry:
            builder.with_tools(self.tool_registry)
        if query:
            self._emit("retrieve", "active", f"Recherche RAG top-{self.rag_top_k}")
            builder.with_rag(profile, query, self.api, top_k=self.rag_top_k)
            documents = self.search_documents(profile, query)
            builder.with_documents(documents)
            self._emit("retrieve", "success", f"Contexte vectoriel extrait ({len(documents)} extrait(s) de documents)")
        self._emit("prompt", "active", "Assemblage PromptBuilder")
        built = builder.build()
        self.last_built_prompt = built
        self._emit("prompt", "success", f"Prompt prêt ({len(built.system_content)} car.)")
        return built

    def _llm_messages(self, context: Context):
        """Copie de l'historique où le dernier message utilisateur est remplacé par sa version simplifiée."""
        messages = context.get_messages_copy()
        if self.last_clean_prompt is not None:
            replace_last_user_message(messages, self.last_clean_prompt)
        return messages

    def search_documents(self, profile: Optional[Profile], query: str) -> list:
        """Extraits des documents ingérés par le profil (R1), les plus proches de la question."""
        session = object_session(profile) if profile is not None else None
        if session is None or not query:
            return []
        try:
            return self.documents.search(session, profile.id, query, api_client=self.api, top_k=self.rag_top_k)
        except Exception as exc:
            logger.warning(f"[ChatEngine] Recherche dans les documents échouée : {exc}")
            return []

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

        built_prompt = self.build_prompt(profile, self.last_clean_prompt or user_prompt)
        return Chat(
            model=self.model,
            api=self.api,
            messages=self._llm_messages(context),
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
            self.tool_executor = self._new_executor(self.tool_registry)
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
        self.last_tool_outputs = []
        if not llm.last_response or not llm.last_response.message:
            logger.error("[ChatEngine] Aucune réponse retournée par le modèle.")
            return None

        assistant_msg = llm.last_response.message
        content = assistant_msg.content
        if self.output_guardrail is not None and content:
            decision = self.output_guardrail.apply(content)
            content = decision.text
            if decision.found:
                self._emit("guardrail", "warning", f"Données personnelles filtrées : {decision.found}")
        persisted_msg = Message(
            role="assistant",
            content=content,
            images=assistant_msg.images,
            tool_calls=assistant_msg.tool_calls,
        )
        context.add(persisted_msg, api_client=self.api)
        session.commit()

        if execute_tools:
            # Les ToolCalls sont une relation SQLAlchemy : les passer à persisted_msg les retire
            # de assistant_msg, c'est donc persisted_msg qui porte les appels à exécuter.
            self.last_tool_outputs = self._execute_tool_calls(session, profile, context, persisted_msg)
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
            confirm_tool=self._confirm_tool,
            on_tool_call=self._notify_tool_call,
            persona=self.persona,
            max_tool_rounds=self.max_tool_rounds,
        )
        final_state = workflow.run(session, profile, context, self.last_clean_prompt or user_prompt)
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
        Exécute un tour complet (voir _stream_turn_impl) et le journalise (EV3) :
        latence, premier morceau, tokens, outils appelés, statut et erreur, dans la table interaction_logs.
        """
        started = time.perf_counter()
        first_token: Optional[float] = None
        answer: list[str] = []
        self._turn_tools = []
        self.last_response = None
        self.last_built_prompt = None
        self.last_grade = None
        status, error = "ok", None
        try:
            for token in self._stream_turn_impl(session, profile, context, user_prompt):
                if first_token is None and token:
                    first_token = time.perf_counter() - started
                answer.append(token)
                yield token
            if self.last_response is not None and self.last_response.done_reason == "guardrail":
                status = "blocked"
        except GeneratorExit:
            status = "interrupted"
            raise
        except Exception as exc:
            status, error = "error", str(exc)
            raise
        finally:
            self._log_interaction(session, profile, context, user_prompt, "".join(answer), status, error,
                                  time.perf_counter() - started, first_token)
        return self.last_response

    @staticmethod
    def verification_note(grade) -> str:
        """
        Signale à l'utilisateur ce que le juge n'a pas pu confirmer (EV1) :
        une réponse non vérifiée, ou les affirmations non appuyées par les sources.
        """
        if grade is None:
            return ""
        if not grade.verified:
            return "\n\n[Vérification] Cette réponse n'a pas pu être vérifiée par le juge."
        if not grade.grounded:
            claims = "; ".join(grade.unsupported_claims) or grade.critique or "voir la réponse"
            return f"\n\n[Vérification] Affirmations non appuyées par les sources : {claims}"
        return ""

    def _log_interaction(self, session, profile, context, user_prompt, answer, status, error, latency, first_token):
        """Écrit une ligne InteractionLog. Un échec de journalisation ne doit jamais casser la conversation."""
        response = self.last_response
        prompt = self.last_built_prompt
        failures = sum(1 for _, ok in self._turn_tools if not ok)
        entry = InteractionLog(
            profile_id=getattr(profile, "id", None),
            context_id=getattr(context, "id", None),
            model=self.model,
            persona=(self.persona or {}).get("key"),
            status=status,
            error=error,
            latency_s=round(latency, 3),
            first_token_s=round(first_token, 3) if first_token is not None else None,
            prompt_tokens=getattr(response, "prompt_eval_count", None),
            gen_tokens=getattr(response, "eval_count", None),
            system_prompt_chars=len(prompt.system_content) if prompt is not None else None,
            memories_injected=getattr(prompt, "memories_injected", None),
            documents_injected=getattr(prompt, "documents_injected", None),
            tools=[name for name, _ in self._turn_tools],
            tool_failures=failures,
            user_prompt=(user_prompt or "")[:TEXT_PREVIEW],
            answer=(answer or "")[:TEXT_PREVIEW],
        )
        grade = self.last_grade
        if grade is not None:
            entry.eval_relevance, entry.eval_coherence, entry.eval_faithfulness = (
                grade.relevance, grade.coherence, grade.faithfulness)
            entry.eval_grounded, entry.eval_verified = grade.grounded, grade.verified
        logger.info("[Interaction] " + json.dumps({k: v for k, v in entry.format().items() if k not in ("id", "created_at")},
                                                   ensure_ascii=False, default=str))
        try:
            session.add(entry)
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.warning(f"[ChatEngine] Journalisation de l'échange impossible : {exc}")

    def _stream_turn_impl(
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
        self.last_clean_prompt = simplify(user_prompt) if self.simplify_prompt else None
        clean_prompt = self.last_clean_prompt or user_prompt
        self._emit("input", "success", f"Message reçu ({len(user_prompt)} → {len(clean_prompt)} car.)")
        refusal = self.check_guardrail(clean_prompt)
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
            if answer and self.output_guardrail is not None:
                answer = self.output_guardrail.apply(answer).text
            if answer:
                yield answer
            self.last_grade = state.get("grade")
            note = self.verification_note(self.last_grade)
            if note:
                yield note
            return self.last_response

        llm = self.prepare_chat(session, profile, context, user_prompt)
        streamed_text = False
        for tool_round in range(self.max_tool_rounds + 1):
            self._emit("generate", "active", f"Streaming depuis {self.model}...")
            separator = "\n\n" if streamed_text else ""
            tokens = llm.execute_stream()
            if self.output_guardrail is not None:
                tokens = self.output_guardrail.filter_stream(tokens)
            for token in tokens:
                if separator:
                    yield separator
                    separator = ""
                streamed_text = True
                yield token
            self._emit("generate", "success", "Génération terminée")

            self.persist_response(session, profile, context, llm)
            if not self.last_tool_outputs:
                break
            if tool_round == self.max_tool_rounds:
                logger.warning("[ChatEngine] Limite de relances après outils atteinte.")
                break
            # Relance : le modèle lit les résultats des outils (messages 'tool') et formule sa réponse
            llm = self.follow_up_chat(context)
        return self.last_response

    def follow_up_chat(self, context: Context) -> Chat:
        """Prépare la génération qui suit l'exécution d'outils, avec le même prompt système."""
        messages = context.get_messages_copy()
        if len(messages) > 6:
            messages = type(messages)(messages[-6:])
        return Chat(
            model=self.model,
            api=self.api,
            messages=messages,
            tools=self._get_tools_list(),
            system_prompt=self.last_built_prompt,
        )

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
