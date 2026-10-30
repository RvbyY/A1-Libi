"""
Module galerelm/graph.py
Implémente un moteur de graphe d'états orienté objet en pur Python (StateGraph, CompiledGraph)
sans dépendance externe (type LangGraph), ainsi que le vérificateur HallucinationGrader
et le workflow par nœuds AntiHallucinationWorkflow.
"""
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from src.config import config
from src.galerelm.intent_classifier import IntentGuardrail
from src.galerelm.models import (
    Chat,
    ChatResponse,
    Context,
    Message,
    MessageList,
    Options,
    Profile,
    PromptBuilder,
    PromptTemplate,
)
from src.galerelm.rag import RAGManager
from src.rapideAPI.client import RapideAPI
from src.tools.registry import ToolExecutor, ToolRegistry

logger = logging.getLogger("galerelm.graph")

END = "__end__"


@dataclass
class ConditionalEdge:
    """Représente une transition conditionnelle sortant d'un nœud du graphe."""
    router: Callable[[dict[str, Any]], str]
    path_map: dict[str, str]


class CompiledGraph:
    """
    Graphe d'états compilé prêt à être exécuté.
    Exécute chaque nœud séquentiellement en mettant à jour un état partagé (dict)
    et en suivant les arêtes directes ou conditionnelles jusqu'à END.
    """

    def __init__(
        self,
        nodes: dict[str, Callable[[dict[str, Any]], Optional[dict[str, Any]]]],
        entry_point: str,
        edges: dict[str, str],
        conditional_edges: dict[str, ConditionalEdge],
        max_steps: int = 25,
    ):
        self.nodes = dict(nodes)
        self.entry_point = entry_point
        self.edges = dict(edges)
        self.conditional_edges = dict(conditional_edges)
        self.max_steps = max_steps

    def invoke(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        """Exécute le graphe à partir de l'état initial et retourne l'état final."""
        state: dict[str, Any] = dict(initial_state)
        trace: list[str] = list(state.get("execution_trace", []))
        current = self.entry_point
        steps = 0

        while current != END:
            if steps >= self.max_steps:
                raise RuntimeError(f"Nombre maximal d'étapes ({self.max_steps}) dépassé dans le graphe.")
            if current not in self.nodes:
                raise ValueError(f"Nœud inconnu dans le graphe : {current}")

            logger.info(f"[StateGraph] Exécution du nœud '{current}' (étape {steps + 1})")
            trace.append(current)
            state["execution_trace"] = trace

            node_fn = self.nodes[current]
            updates = node_fn(state)
            if isinstance(updates, dict):
                state.update(updates)

            steps += 1

            if current in self.conditional_edges:
                cond = self.conditional_edges[current]
                route_key = cond.router(state)
                if route_key not in cond.path_map:
                    raise ValueError(
                        f"Clé de routage '{route_key}' non trouvée à la sortie du nœud '{current}'."
                    )
                current = cond.path_map[route_key]
            elif current in self.edges:
                current = self.edges[current]
            else:
                current = END

        return state


class StateGraph:
    """
    Constructeur de graphe d'états (pattern Builder) en pur Python.
    Permet d'enregistrer des nœuds, des arêtes simples et des arêtes conditionnelles.
    """

    def __init__(self):
        self._nodes: dict[str, Callable[[dict[str, Any]], Optional[dict[str, Any]]]] = {}
        self._edges: dict[str, str] = {}
        self._conditional_edges: dict[str, ConditionalEdge] = {}
        self._entry_point: Optional[str] = None

    def add_node(
        self,
        name: str,
        action: Callable[[dict[str, Any]], Optional[dict[str, Any]]],
    ) -> "StateGraph":
        if name == END:
            raise ValueError(f"Le nom '{END}' est réservé.")
        self._nodes[name] = action
        return self

    def set_entry_point(self, name: str) -> "StateGraph":
        self._entry_point = name
        return self

    def add_edge(self, source: str, target: str) -> "StateGraph":
        self._edges[source] = target
        return self

    def add_conditional_edges(
        self,
        source: str,
        router: Callable[[dict[str, Any]], str],
        path_map: dict[str, str],
    ) -> "StateGraph":
        self._conditional_edges[source] = ConditionalEdge(router=router, path_map=dict(path_map))
        return self

    def compile(self, max_steps: int = 25) -> CompiledGraph:
        if not self._entry_point or self._entry_point not in self._nodes:
            raise ValueError("Point d'entrée du graphe non défini ou introuvable.")
        return CompiledGraph(
            nodes=self._nodes,
            entry_point=self._entry_point,
            edges=self._edges,
            conditional_edges=self._conditional_edges,
            max_steps=max_steps,
        )


@dataclass
class HallucinationGrade:
    """Résultat de l'évaluation anti-hallucination d'une réponse candidate."""
    grounded: bool
    critique: str = ""


class HallucinationGrader:
    """
    Évalue si une réponse candidate générée par le LLM est ancrée dans les faits
    de référence (mémoires RAG et sorties d'outils) ou si elle contient une hallucination.
    """

    def __init__(
        self,
        api: RapideAPI,
        model: Optional[str] = None,
        template: Optional[PromptTemplate] = None,
    ):
        self.api = api
        self.model = model or config.DEFAULT_MODEL
        self.template = template or PromptTemplate.hallucination_grader()
        self.options = Options(temperature=0.0, top_k=1, num_predict=160)

    def grade(
        self,
        user_input: str,
        candidate: str,
        facts: Optional[list[str]] = None,
    ) -> HallucinationGrade:
        """
        Analyse la réponse candidate par rapport aux faits fournis.
        Retourne un objet HallucinationGrade(grounded, critique).
        """
        if not candidate or not candidate.strip():
            return HallucinationGrade(grounded=True, critique="")

        facts_text = "\n".join(f"- {f}" for f in (facts or []) if f) or "Aucun fait spécifique fourni."
        prompt_str = self.template.render(
            facts=facts_text,
            user_input=user_input,
            candidate=candidate,
        )

        chat = Chat(
            model=self.model,
            api=self.api,
            messages=MessageList([Message(role="user", content=prompt_str)]),
            options=self.options,
            think=False,
        )

        raw_output = ""
        try:
            for token in chat.execute_stream():
                raw_output += token

            parsed = IntentGuardrail.extract_json(raw_output)
            if not parsed:
                return HallucinationGrade(grounded=True, critique="")

            grounded = bool(parsed.get("grounded", True))
            critique = str(parsed.get("critique", "")).strip()
            return HallucinationGrade(grounded=grounded, critique=critique)
        except Exception as exc:
            logger.error(f"[HallucinationGrader] Erreur lors de la vérification : {exc}")
            return HallucinationGrade(grounded=True, critique="")


class AntiHallucinationWorkflow:
    """
    Workflow orienté nœuds (StateGraph) orchestrant :
    retrieve -> generate -> (tools) -> grade -> accept / regenerate.
    """

    def __init__(
        self,
        api: RapideAPI,
        model: str,
        grader: Optional[HallucinationGrader] = None,
        tool_registry: Optional[ToolRegistry] = None,
        rag_top_k: int = 3,
        max_retries: int = 2,
        on_event: Optional[Callable[[str, str, str], None]] = None,
        confirm_tool: Optional[Callable[[str, dict], bool]] = None,
        on_tool_call: Optional[Callable[[str, dict, Any, float], None]] = None,
    ):
        self.api = api
        self.model = model
        self.grader = grader or HallucinationGrader(api=api, model=model)
        self.tool_registry = tool_registry
        self.tool_executor = (
            ToolExecutor(tool_registry, confirm=confirm_tool, on_call=on_tool_call) if tool_registry else None
        )
        self.rag_top_k = rag_top_k
        self.max_retries = max_retries
        self.on_event = on_event
        self.graph = self._build_graph()

    def _emit(self, node_id: str, state: str, detail: str) -> None:
        if self.on_event is not None:
            self.on_event(node_id, state, detail)

    def _build_graph(self) -> CompiledGraph:
        builder = StateGraph()
        builder.add_node("retrieve", self.node_retrieve)
        builder.add_node("generate", self.node_generate)
        builder.add_node("tools", self.node_tools)
        builder.add_node("grade", self.node_grade)

        builder.set_entry_point("retrieve")
        builder.add_edge("retrieve", "generate")

        builder.add_conditional_edges(
            "generate",
            self.route_after_generate,
            {
                "run_tools": "tools",
                "grade": "grade",
            },
        )
        builder.add_edge("tools", "grade")

        builder.add_conditional_edges(
            "grade",
            self.route_after_grade,
            {
                "accept": END,
                "regenerate": "generate",
            },
        )
        return builder.compile()

    # ── Nœuds du graphe ──────────────────────────────────────────────

    def node_retrieve(self, state: dict[str, Any]) -> dict[str, Any]:
        """Nœud 1 : Récupère les souvenirs pertinents depuis DeepContext via RAGManager."""
        self._emit("retrieve", "active", "Recherche vectorielle RAG...")
        profile: Optional[Profile] = state.get("profile")
        user_prompt: str = state.get("user_prompt", "")
        memories: list[str] = []

        if profile and getattr(profile, "deep_context", None):
            try:
                rag = RAGManager(api_client=self.api)
                results = rag.search(profile.deep_context, user_prompt, api_client=self.api, top_k=self.rag_top_k)
                memories = [f"[{mem.role}] {mem.content}" for _, mem in results]
            except Exception as exc:
                logger.warning(f"[Workflow.retrieve] Recherche RAG échouée : {exc}")

        self._emit("retrieve", "success", f"{len(memories)} souvenir(s) trouvé(s)")
        return {
            "memories": memories,
            "tool_outputs": [],
            "critique": "",
            "grounded": True,
            "retries": 0,
        }

    def node_generate(self, state: dict[str, Any]) -> dict[str, Any]:
        """Nœud 2 : Construit le Prompt (avec critique éventuelle) et interroge le LLM."""
        profile: Optional[Profile] = state.get("profile")
        context: Context = state["context"]
        user_prompt: str = state["user_prompt"]
        memories: list[str] = state.get("memories", [])
        critique: str = state.get("critique", "")
        retries: int = state.get("retries", 0)

        self._emit(
            "prompt",
            "active",
            "Correction avec critique" if critique else "Assemblage PromptBuilder",
        )
        p_builder = (
            PromptBuilder()
            .with_profile(profile)
            .with_memories(memories)
            .with_user_query(user_prompt)
        )
        if self.tool_registry:
            p_builder.with_tools(self.tool_registry)

        if critique:
            p_builder.with_rules([
                f"CORRECTION ANTI-HALLUCINATION REQUISE : Ta réponse précédente était invalide ({critique}). "
                "Corrige-la en respectant strictement les faits connus sans rien inventer."
            ])

        built_prompt = p_builder.build()
        self._emit(
            "prompt",
            "success",
            f"RAG:{built_prompt.memories_injected} Tools:{built_prompt.tools_injected}",
        )

        self._emit("generate", "active", f"Génération LLM (essai #{retries + 1})...")
        llm = Chat(
            model=self.model,
            api=self.api,
            messages=context.get_messages_copy(),
            tools=self.tool_registry.to_tools_list() if self.tool_registry else None,
            system_prompt=built_prompt,
        )

        tokens: list[str] = []
        for token in llm.execute_stream():
            tokens.append(token)

        candidate = "".join(tokens)
        self._emit("generate", "success", f"{len(candidate)} caractères générés")
        return {
            "candidate_answer": candidate,
            "last_llm": llm,
            "last_response": llm.last_response,
            "retries": retries + 1,
        }

    def node_tools(self, state: dict[str, Any]) -> dict[str, Any]:
        """Nœud 3 : Exécute les appels d'outils demandés par le LLM via ToolExecutor."""
        self._emit("tools", "active", "Exécution des tool_calls...")
        last_response: Optional[ChatResponse] = state.get("last_response")
        profile: Optional[Profile] = state.get("profile")
        context: Context = state["context"]
        session = state.get("session")

        if not self.tool_executor or not last_response or not last_response.message:
            return {"tool_outputs": []}

        tool_ctx = self.tool_executor.build_tool_context(
            profile=profile,
            session=session,
            context=context,
            api=self.api,
        )
        results = self.tool_executor.execute_calls(last_response.message, tool_ctx)
        outputs = [f"[{name}] {res.message}" for name, res in results]
        self._emit("tools", "success", f"{len(outputs)} outil(s) exécuté(s)")
        return {"tool_outputs": outputs}

    def node_grade(self, state: dict[str, Any]) -> dict[str, Any]:
        """Nœud 4 : Vérifie l'absence d'hallucination dans la réponse candidate."""
        self._emit("grade", "active", "Vérification factuelle...")
        user_prompt: str = state["user_prompt"]
        candidate: str = state.get("candidate_answer", "")
        facts: list[str] = list(state.get("memories", [])) + list(state.get("tool_outputs", []))

        grade_result = self.grader.grade(
            user_input=user_prompt,
            candidate=candidate,
            facts=facts,
        )
        logger.info(
            f"[Workflow.grade] grounded={grade_result.grounded} "
            f"(essai {state.get('retries', 1)}/{self.max_retries + 1})"
        )
        if grade_result.grounded:
            self._emit("grade", "success", "Ancré dans les faits (grounded)")
        else:
            self._emit("grade", "warning", f"Hallucination: {grade_result.critique}")
        return {
            "grounded": grade_result.grounded,
            "critique": grade_result.critique,
        }

    # ── Routeurs conditionnels ───────────────────────────────────────

    def route_after_generate(self, state: dict[str, Any]) -> str:
        last_response: Optional[ChatResponse] = state.get("last_response")
        if (
            self.tool_executor is not None
            and last_response is not None
            and last_response.message is not None
            and bool(last_response.message.tool_calls)
            and not state.get("tool_outputs")
        ):
            return "run_tools"
        return "grade"

    def route_after_grade(self, state: dict[str, Any]) -> str:
        if state.get("grounded", True):
            return "accept"
        if state.get("retries", 1) > self.max_retries:
            logger.warning("[Workflow] Limite de régénération anti-hallucination atteinte.")
            return "accept"
        return "regenerate"

    def run(
        self,
        session,
        profile: Profile,
        context: Context,
        user_prompt: str,
    ) -> dict[str, Any]:
        """Exécute le graphe complet pour un tour de conversation."""
        initial_state = {
            "session": session,
            "profile": profile,
            "context": context,
            "user_prompt": user_prompt,
        }
        return self.graph.invoke(initial_state)
