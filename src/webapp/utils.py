import gradio as gr
from src.galerelm.wrapper import SensAIWrapper

api = SensAIWrapper(db_url="sqlite:///galerelm.db")

def respond(message, history, email):
    yield from api.chat_stream(email=email, prompt=message)

def load_history(email):
    return [{"role": m.role, "content": m.content} for m in api.get_chat_history(email)]

def login(email, name, instructions):
    if not email:
        gr.Warning("Entre un email.")
        return gr.skip(), gr.skip(), gr.skip(), gr.skip()
    api.create_profile(email=email, name=name, instructions=instructions)
    api.update_profile(email=email, name=name, instructions=instructions)
    return email, gr.Column(visible=False), gr.Column(visible=True), load_history(email)

def logout():
    return "", gr.Column(visible=True), gr.Column(visible=False), []

def new_chat(email):
    api.start_new_chat(email)
    return []
