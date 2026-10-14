import gradio as gr
import src.webapp.utils as utils
from src.webapp.views import Views

with gr.Blocks(title="A1-Libi", fill_width=True) as frontend:
    current_email = gr.State("")
    current_chat = gr.State(None)

    login_page, email, name, instructions, login_btn = Views.connexion_page()
    chat_page, logout_btn, chatbot, new_btn, chats = Views.main_page(current_email, current_chat)

    login_btn.click(utils.login, inputs=[email, name, instructions], outputs=[current_email, current_chat, login_page, chat_page, chatbot, chats])
    logout_btn.click(utils.logout, outputs=[current_email, current_chat, login_page, chat_page, chatbot, chats])
    new_btn.click(utils.new_chat, inputs=current_email, outputs=[current_chat, chatbot, chats])
    chats.input(utils.open_chat, inputs=[current_email, chats], outputs=[current_chat, chatbot])


if __name__ == "__main__":
    frontend.launch(theme=gr.themes.Soft())
