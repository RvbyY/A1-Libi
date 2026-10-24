import gradio as gr
import src.webapp.utils as utils
from src.webapp.views import Views

with gr.Blocks(title="SensAI — Visualiseur Temps Réel", fill_width=True) as frontend:
    current_email = gr.State("")
    current_chat = gr.State(None)

    login_page, email, name, instructions, login_btn = Views.connexion_page()
    (
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
    ) = Views.main_page(current_email, current_chat)

    login_btn.click(
        utils.login,
        inputs=[email, name, instructions],
        outputs=[current_email, current_chat, login_page, chat_page, chatbot, chats, graph_html],
    )
    logout_btn.click(
        utils.logout,
        outputs=[current_email, current_chat, login_page, chat_page, chatbot, chats, graph_html],
    )
    new_btn.click(
        utils.new_chat,
        inputs=current_email,
        outputs=[current_chat, chatbot, chats, graph_html],
    )
    chats.input(
        utils.open_chat,
        inputs=[current_email, chats],
        outputs=[current_chat, chatbot, graph_html],
    )

    # Envoi de message ou commande avec mise à jour temps réel du graphe SVG et de l'inspecteur
    msg_input.submit(
        utils.controller.stream_message,
        inputs=[msg_input, chatbot, current_email, current_chat, use_guardrail, use_anti_hallucination],
        outputs=[msg_input, chatbot, graph_html, inspector_md],
    )
    send_btn.click(
        utils.controller.stream_message,
        inputs=[msg_input, chatbot, current_email, current_chat, use_guardrail, use_anti_hallucination],
        outputs=[msg_input, chatbot, graph_html, inspector_md],
    )


if __name__ == "__main__":
    frontend.launch(theme=gr.themes.Soft())
