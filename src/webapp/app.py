import gradio as gr
import src.webapp.utils as utils

with gr.Blocks(title="A1-Libi") as frontend:
    current_email = gr.State("")

    # page de connexion
    with gr.Column(visible=True) as login_page:
        gr.HTML("<h1>Connexion</h1>")
        email = gr.Textbox(label="Email")
        name = gr.Textbox(label="Nom")
        instructions = gr.Textbox(label="Instructions", lines=3)
        login_btn = gr.Button("Se connecter", variant="primary")


    # page du chat
    with gr.Column(visible=False) as chat_page:
        with gr.Row():
            gr.HTML("<h1>A1-Libi</h1>")
            new_btn = gr.Button("Nouvelle conversation")
            logout_btn = gr.Button("Se déconnecter", variant="stop")
        chatbot = gr.Chatbot(placeholder="**Pose ta première question !**")
        gr.ChatInterface(fn=utils.respond, chatbot=chatbot, additional_inputs=[current_email])


    login_btn.click(utils.login, inputs=[email, name, instructions],
                    outputs=[current_email, login_page, chat_page, chatbot])
    logout_btn.click(utils.logout, outputs=[current_email, login_page, chat_page, chatbot])
    new_btn.click(utils.new_chat, inputs=current_email, outputs=chatbot)


if __name__ == "__main__":
    frontend.launch(theme=gr.themes.Default())
