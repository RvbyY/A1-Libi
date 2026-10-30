"""
Module webapp/utils.py
Encapsule le contrôleur WebAppController gérant les interactions Gradio,
l'exécution des commandes CLI (/help, /schedule, /recall...), le streaming du LLM,
et la mise à jour en temps réel du graphique de nœuds (PipelineVisualizer).
"""
import io
import json
import gradio as gr
from rich.console import Console

from src.galerelm.intent_classifier import IntentGuardrail
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

    def configure_pipeline(self, use_guardrail: bool, use_anti_hallucination: bool) -> str:
        """Active ou désactive dynamiquement IntentGuardrail et AntiHallucinationWorkflow."""
        if use_guardrail:
            self.api.engine.guardrail = IntentGuardrail(api=self.api.core.api, model=self.api.core.model)
        else:
            self.api.engine.guardrail = None

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
            sys_txt = engine.last_built_prompt.render_system()
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
        capture_console = Console(file=buffer, force_terminal=False, color_system=None, width=100)
        old_console = core.ui.console
        core.ui.console = capture_console

        try:
            with core.db.session_scope() as session:
                core.session = session
                core.profile = self.api.sessions.get_profile_or_raise(session, email)
                core.context = self.api.sessions.get_context_or_raise(session, core.profile.id, chat_id)
                core.commands.dispatch(message[1:], core)
                output = buffer.getvalue().strip() or f"Commande `{message}` exécutée avec succès."
                self.visualizer.mark("command", "success", f"Exécutée : {message.split()[0]}")
                self.visualizer.mark("persist", "success", "Session synchronisée")
                return f"```\n{output}\n```"
        except Exception as exc:
            self.visualizer.mark("command", "error", str(exc))
            return f"⚠️ Erreur lors de la commande : `{exc}`"
        finally:
            core.ui.console = old_console

    def stream_message(
        self,
        message: str,
        history: list,
        email: str,
        chat_id: int,
        use_guardrail: bool,
        use_anti_hallucination: bool,
    ):
        """Générateur Gradio mettant à jour simultanément le Chatbot, le Graphe SVG et l'Inspecteur."""
        if not message or not message.strip():
            yield "", history, self.visualizer.render_html(), self.build_inspector_markdown()
            return

        if not email:
            history = list(history or []) + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": "⚠️ Veuillez d'abord vous connecter avec votre email."},
            ]
            yield "", history, self.visualizer.render_html(), self.build_inspector_markdown()
            return

        self.configure_pipeline(use_guardrail, use_anti_hallucination)
        history = list(history or []) + [{"role": "user", "content": message}]

        # 1. Branche Commande CLI (/help, /schedule, /recall, /debug...)
        if message.strip().startswith("/"):
            cmd_reply = self._execute_slash_command(message.strip(), email, chat_id)
            history.append({"role": "assistant", "content": cmd_reply})
            yield "", history, self.visualizer.render_html(), self.build_inspector_markdown()
            return

        # 2. Branche Pipeline LLM & Graphe de Nœuds
        self.visualizer.reset()
        self.visualizer.mark("input", "active", "Réception requête...")
        history.append({"role": "assistant", "content": "⏳ *Exécution du graphe en cours...*"})
        yield "", history, self.visualizer.render_html(), self.build_inspector_markdown()

        try:
            for partial_text in self.api.chat_stream(email=email, prompt=message, context_id=chat_id):
                history[-1] = {"role": "assistant", "content": partial_text}
                yield "", history, self.visualizer.render_html(), self.build_inspector_markdown()
        except Exception as exc:
            self.visualizer.mark("generate", "error", str(exc))
            history[-1] = {"role": "assistant", "content": f"❌ Erreur LLM : `{exc}`"}

        yield "", history, self.visualizer.render_html(), self.build_inspector_markdown()

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
