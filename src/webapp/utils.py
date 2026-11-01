"""
Module webapp/utils.py
Encapsule le contrôleur WebAppController gérant les interactions Gradio,
l'exécution des commandes CLI (/help, /schedule, /recall...), le streaming du LLM,
et la mise à jour en temps réel du graphique de nœuds (PipelineVisualizer).
"""
import contextlib
import io
import json
import gradio as gr
from rich.console import Console

from src.galerelm.intent_classifier import IntentGuardrail
from src.galerelm.output_guardrail import OutputGuardrail
from src.config import config
from src.galerelm import metrics
from src.galerelm.models import Message
from src.galerelm.wrapper import SensAIWrapper
from src.webapp.visualizer import PipelineVisualizer


class WebAppController:
    """
    Contrôleur orienté objet pour l'application Web Gradio + Visualiseur Temps Réel.
    """

    def __init__(self, db_url: str = None):
        # None : utilise config.DB_URL (.env, config.yaml), comme la CLI
        self.api = SensAIWrapper(db_url=db_url)
        self.visualizer = PipelineVisualizer()
        self.api.engine.on_event = self.visualizer.mark
        # A3 dans la webapp : une action sensible demandée par le modèle est mise en attente,
        # puis exécutée seulement si l'utilisateur répond /confirmer (ou abandonnée avec /annuler).
        self.pending_actions: dict[str, list[tuple[str, dict]]] = {}
        self._current_email = ""
        self.api.engine.confirm_tool = self._hold_sensitive_action

    def _hold_sensitive_action(self, name: str, arguments: dict) -> bool:
        """Callback de confirmation : rien n'est exécuté pendant la génération, l'action attend /confirmer."""
        self.pending_actions.setdefault(self._current_email, []).append((name, dict(arguments)))
        return False

    def pending_actions_markdown(self, email: str) -> str:
        actions = self.pending_actions.get(email) or []
        if not actions:
            return ""
        lines = ["**Action en attente de confirmation** : répondez `/confirmer` pour l'exécuter, ou `/annuler`."]
        for name, arguments in actions:
            details = ", ".join(f"{key}={value!r}" for key, value in arguments.items())
            lines.append(f"- `{name}({details})`")
        return "\n".join(lines)

    def resolve_pending(self, email: str, chat_id: int, confirm: bool) -> str:
        """Exécute (ou abandonne) les actions en attente de ce profil, et enregistre le résultat dans le chat."""
        actions = self.pending_actions.pop(email, [])
        if not actions:
            return "Aucune action en attente."
        if not confirm:
            return "Action annulée : " + ", ".join(name for name, _ in actions) + "."
        core = self.api.core
        lines = []
        with core.db.session_scope() as session:
            profile = self.api.sessions.get_profile_or_raise(session, email)
            context = self.api.sessions.get_context_or_raise(session, profile.id, chat_id)
            executor = core.chat_engine.tool_executor
            tool_ctx = executor.build_tool_context(profile=profile, session=session, context=context, api=core.api,
                                                   task_manager=core.task_manager)
            for name, arguments in actions:
                try:
                    result = executor.registry.execute(name, tool_ctx, arguments)
                except Exception as exc:
                    lines.append(f"- `{name}` : échec ({exc})")
                    continue
                context.add(Message(role="tool", content=f"[{name}] {result.message}"), api_client=core.api)
                lines.append(f"- `{name}` : {'réussi' if result.success else 'échec'} ({result.message})")
            session.commit()
        return "Actions confirmées :\n" + "\n".join(lines)

    def usage_markdown(self, email: str, chat_id) -> str:
        """Consommation du dernier échange (X1) : tokens lus et générés, remplissage du contexte, agent actif."""
        engine = self.api.engine
        persona = (engine.persona or {}).get("name", "-")
        parts = [f"Agent : **{persona}**", f"Modèle : `{engine.model}`"]
        response = engine.last_response
        if response is not None and (response.prompt_eval_count or response.eval_count):
            parts.append(f"Tokens : {response.prompt_eval_count or 0} lus, {response.eval_count or 0} générés")
        num_ctx = config.GENERATION["chat"]["num_ctx"]
        if response is not None and response.prompt_eval_count:
            used = (response.prompt_eval_count or 0) + (response.eval_count or 0)
            parts.append(f"Fenêtre : {used} / {num_ctx} tokens ({round(100 * used / num_ctx)} %)")
        else:
            parts.append(f"Fenêtre : {num_ctx} tokens")
        if email and chat_id is not None:
            try:
                count = len(self.api.get_chat_history(email, chat_id))
                parts.append(f"Mémoire courte : {count} / {config.CONTEXT_LIMIT} messages")
            except Exception:
                pass
        return " · ".join(parts)

    def monitoring(self, email: str, days: int = 7):
        """Onglet Monitoring (EV3) : indicateurs texte et tableau jour par jour (volume, latence, erreurs, tokens)."""
        import pandas as pd

        with self.api.core.db.session_scope() as session:
            profile = self.api.sessions.get_profile(session, email) if email else None
            data = metrics.report(session, days=days, profile_id=profile.id if profile else None)
        rows = [
            {"jour": day, "appels": s["calls"], "latence_moyenne_s": s["latency_mean"], "latence_p95_s": s["latency_p95"],
             "erreurs_pct": s["error_rate"], "tokens_lus": s["prompt_tokens_mean"]}
            for day, s in data["per_day"].items()
        ]
        table = pd.DataFrame(rows, columns=["jour", "appels", "latence_moyenne_s", "latence_p95_s", "erreurs_pct", "tokens_lus"])
        return "```\n" + metrics.format_report(data) + "\n```", table

    def persona_choices(self) -> list[tuple[str, str]]:
        return [(f"{spec['name']} ({key})", key) for key, spec in config.PERSONAS.items()]

    def change_persona(self, key: str, email: str, chat_id):
        """Change d'agent pour les prochains messages, sans effacer la conversation (X1, A5)."""
        self.api.core.set_persona(key)
        self.visualizer.mark("prompt", "success", f"Agent : {self.api.engine.persona['name']}")
        return self.usage_markdown(email, chat_id), self.visualizer.render_html()

    def configure_pipeline(self, use_simplifier: bool, use_guardrail: bool, use_anti_hallucination: bool) -> str:
        """Active ou désactive dynamiquement la simplification du prompt, IntentGuardrail et AntiHallucinationWorkflow."""
        self.api.engine.simplify_prompt = use_simplifier

        # Case guardrail : filtre d'entrée (intention) et filtre de sortie (données personnelles anonymisées)
        if use_guardrail:
            self.api.engine.guardrail = IntentGuardrail(api=self.api.core.api, model=self.api.core.model)
            mode = config.GUARDRAIL_OUTPUT if config.GUARDRAIL_OUTPUT != "off" else "anonymize"
            self.api.engine.output_guardrail = OutputGuardrail(mode, config.GUARDRAIL_PII)
        else:
            self.api.engine.guardrail = None
            self.api.engine.output_guardrail = None

        if use_anti_hallucination:
            self.api.engine.enable_anti_hallucination(max_retries=2)
        else:
            self.api.engine.hallucination_grader = None

        return self.visualizer.render_html()

    def build_inspector_markdown(self) -> str:
        """Construit l'aperçu temps réel du Prompt assemblé et du GraphState."""
        engine = self.api.engine
        sections = []

        if engine.last_built_prompt:
            sys_txt = engine.last_built_prompt.system_content
            sections.append(f"### 🧩 System Prompt assemblé (`PromptBuilder`)\n```text\n{sys_txt}\n```")

        if engine.last_graph_state:
            safe_state = {
                k: v
                for k, v in engine.last_graph_state.items()
                if k in ("query", "rag_docs", "candidate_answer", "is_grounded", "grade_reason", "retries", "max_retries", "tool_outputs")
            }
            sections.append(
                f"### 🔄 État du Graphe (`GraphState`)\n```json\n{json.dumps(safe_state, indent=2, ensure_ascii=False)}\n```"
            )

        if not sections:
            return "*Envoyez un message ou une commande pour inspecter le `Prompt` et le `GraphState` en temps réel.*"
        return "\n\n".join(sections)

    def _execute_slash_command(self, message: str, email: str, chat_id: int) -> str:
        """Exécute une commande `/cmd` via CommandRegistry et capture sa sortie."""
        self.visualizer.reset()
        self.visualizer.mark("input", "success", f"Commande : {message}")
        self.visualizer.mark("command", "active", f"Dispatch {message.split()[0]}")

        core = self.api.core
        buffer = io.StringIO()

        try:
            with core.db.session_scope() as session, contextlib.redirect_stdout(buffer):
                core.session = session
                core.profile = self.api.sessions.get_profile_or_raise(session, email)
                core.context = self.api.sessions.get_context_or_raise(session, core.profile.id, chat_id)
                core.commands.dispatch(message, core)
                output = buffer.getvalue().strip() or f"Commande `{message}` exécutée avec succès."
                self.visualizer.mark("command", "success", f"Exécutée : {message.split()[0]}")
                self.visualizer.mark("persist", "success", "Session synchronisée")
                return f"```\n{output}\n```"
        except Exception as exc:
            self.visualizer.mark("command", "error", str(exc))
            return f"⚠️ Erreur lors de la commande : `{exc}`"

    def stream_message(
        self,
        message: str,
        history: list,
        email: str,
        chat_id: int,
        use_simplifier: bool,
        use_guardrail: bool,
        use_anti_hallucination: bool,
    ):
        """Générateur Gradio : met à jour le chat, le graphe SVG, l'inspecteur et la consommation (tokens, contexte)."""
        def frame():
            return "", history, self.visualizer.render_html(), self.build_inspector_markdown(), self.usage_markdown(email, chat_id)

        if not message or not message.strip():
            yield frame()
            return

        if not email:
            history = list(history or []) + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": "Veuillez d'abord vous connecter avec votre email."},
            ]
            yield frame()
            return

        self.configure_pipeline(use_simplifier, use_guardrail, use_anti_hallucination)
        history = list(history or []) + [{"role": "user", "content": message}]
        command = message.strip()

        # 1. Confirmation des actions sensibles en attente (A3)
        if command in ("/confirmer", "/annuler"):
            history.append({"role": "assistant", "content": self.resolve_pending(email, chat_id, command == "/confirmer")})
            yield frame()
            return

        # 2. Branche Commande CLI (/help, /schedule, /recall, /persona...)
        if command.startswith("/"):
            cmd_reply = self._execute_slash_command(command, email, chat_id)
            history.append({"role": "assistant", "content": cmd_reply})
            yield frame()
            return

        # 3. Branche Pipeline LLM & Graphe de Nœuds
        self.visualizer.reset()
        self.visualizer.mark("input", "active", "Réception requête...")
        history.append({"role": "assistant", "content": "*Génération en cours...*"})
        yield frame()

        self._current_email = email
        self.pending_actions.pop(email, None)
        try:
            for partial_text in self.api.chat_stream(email=email, prompt=message, context_id=chat_id):
                history[-1] = {"role": "assistant", "content": partial_text}
                yield frame()
        except Exception as exc:
            self.visualizer.mark("generate", "error", str(exc))
            history[-1] = {"role": "assistant", "content": f"Erreur LLM : `{exc}`"}

        pending = self.pending_actions_markdown(email)
        if pending:
            history[-1] = {"role": "assistant", "content": f"{history[-1]['content']}\n\n{pending}".strip()}
        yield frame()

    def respond(self, message, history, email, chat_id):
        """Compatibilité directe pour appels simples."""
        yield from self.api.chat_stream(email=email, prompt=message, context_id=chat_id)

    def load_history(self, email, chat_id):
        return [{"role": m.role, "content": m.content} for m in self.api.get_chat_history(email, chat_id)]

    def get_chats(self, email, chat_id):
        choices = [(f"Chat {c.id}", c.id) for c in self.api.list_chats(email)]
        return gr.Radio(choices=choices, value=chat_id)

    def login(self, email, name, instructions):
        if not email:
            gr.Warning("Entre un email.")
            return gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
        self.api.create_profile(email=email, name=name, instructions=instructions)
        self.api.update_profile(email=email, name=name, instructions=instructions)
        chat_id = self.api.list_chats(email)[0].id
        self.visualizer.reset()
        self.visualizer.mark("persist", "success", f"Profil chargé ({email})")
        return (
            email,
            chat_id,
            gr.Column(visible=False),
            gr.Column(visible=True),
            self.load_history(email, chat_id),
            self.get_chats(email, chat_id),
            self.visualizer.render_html(),
        )

    def logout(self):
        self.visualizer.reset()
        return (
            "",
            None,
            gr.Column(visible=True),
            gr.Column(visible=False),
            [],
            gr.Radio(choices=[], value=None),
            self.visualizer.render_html(),
        )

    def new_chat(self, email):
        chat_id = self.api.start_new_chat(email).id
        self.visualizer.reset()
        self.visualizer.mark("persist", "success", f"Nouveau Chat #{chat_id}")
        return chat_id, [], self.get_chats(email, chat_id), self.visualizer.render_html()

    def open_chat(self, email, chat_id):
        self.visualizer.reset()
        self.visualizer.mark("persist", "success", f"Chat #{chat_id} chargé")
        return chat_id, self.load_history(email, chat_id), self.visualizer.render_html()


controller = WebAppController()
api = controller.api
respond = controller.respond
load_history = controller.load_history
get_chats = controller.get_chats
login = controller.login
logout = controller.logout
new_chat = controller.new_chat
open_chat = controller.open_chat
