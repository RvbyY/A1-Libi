import gradio as gr
import src.webapp.utils as utils


class Views:
    @staticmethod
    def sidebar():
        with gr.Sidebar():
            gr.HTML("<h2>💬 Conversations</h2>")
            new_btn = gr.Button("➕ Nouvelle conversation", variant="secondary")
            chats = gr.Radio(label="Historique", choices=[])
            gr.HTML("<hr style='margin:12px 0;border-color:#334155;'/><h3>⚙️ Options du Graphe</h3>")
            use_guardrail = gr.Checkbox(label="Activer IntentGuardrail", value=True)
            use_anti_hallucination = gr.Checkbox(
                label="Activer Boucle Anti-Hallucination (StateGraph)", value=True
            )
        return new_btn, chats, use_guardrail, use_anti_hallucination

    @staticmethod
    def connexion_page():
        with gr.Column(visible=True) as login_page:
            gr.HTML("<h1>🧠 SensAI — Studio & Visualiseur Temps Réel</h1>")
            email = gr.Textbox(label="Email", placeholder="alice@sensai.dev")
            name = gr.Textbox(label="Nom", placeholder="Alice")
            instructions = gr.Textbox(
                label="Instructions personnalisées (Profil)",
                lines=3,
                placeholder="Ex: Réponds toujours de manière concise et structurée.",
            )
            login_btn = gr.Button("Se connecter", variant="primary")
        return login_page, email, name, instructions, login_btn

    @staticmethod
    def main_page(current_email, current_chat):
        with gr.Column(visible=False) as chat_page:
            with gr.Row():
                gr.HTML("<h1>🧠 SensAI — Pipeline & Graphe Temps Réel</h1>")
                logout_btn = gr.Button("Se déconnecter", variant="stop", scale=0)

            # Visualiseur SVG Temps Réel en haut de l'interface
            graph_html = gr.HTML(value=utils.controller.visualizer.render_html())

            with gr.Row():
                with gr.Column(scale=7):
                    chatbot = gr.Chatbot(
                        placeholder="**Pose une question ou tape une commande (`/help`, `/schedule`, `/recall`, `/debug`) !**",
                        height=380,
                    )
                    with gr.Row():
                        msg_input = gr.Textbox(
                            placeholder="Écris ton message ou une commande (/help, /schedule in 10m Appeler Bob)...",
                            show_label=False,
                            scale=5,
                        )
                        send_btn = gr.Button("Envoyer 🚀", variant="primary", scale=1)

                with gr.Column(scale=5):
                    with gr.Accordion("🔍 Inspecteur Temps Réel (PromptBuilder & GraphState)", open=True):
                        inspector_md = gr.Markdown(value=utils.controller.build_inspector_markdown())

            new_btn, chats, use_guardrail, use_anti_hallucination = Views.sidebar()

        return (
            chat_page,
            logout_btn,
            chatbot,
            msg_input,
            send_btn,
            graph_html,
            inspector_md,
            new_btn,
            chats,
            use_guardrail,
            use_anti_hallucination,
        )
