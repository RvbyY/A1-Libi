import gradio as gr
import src.webapp.utils as utils

class Views:
    @staticmethod
    def sidebar():
        with gr.Sidebar():
            gr.HTML("<h1>Chats</h1>")
            new_btn = gr.Button("Nouvelle conversation")
            chats = gr.Radio(label="Conversations", choices=[])
        return new_btn, chats

    @staticmethod
    def connexion_page():
        with gr.Column(visible=True) as login_page:
            gr.HTML("<h1>Connexion</h1>")
            email = gr.Textbox(label="Email")
            name = gr.Textbox(label="Nom")
            instructions = gr.Textbox(label="Instructions", lines=3)
            login_btn = gr.Button("Se connecter", variant="primary")
        return login_page, email, name, instructions, login_btn

    @staticmethod
    def main_page(current_email, current_chat):
        with gr.Column(visible=False) as chat_page:
            with gr.Row():
                gr.HTML("<h1>A1-Libi</h1>")
                logout_btn = gr.Button("Se déconnecter", variant="stop")
            chatbot = gr.Chatbot(placeholder="**Pose ta première question !**")
            gr.ChatInterface(fn=utils.respond, chatbot=chatbot, additional_inputs=[current_email, current_chat])
            new_btn, chats = Views.sidebar()
        return chat_page, logout_btn, chatbot, new_btn, chats
