import gradio as gr
from src.galerelm.wrapper import SensAIWrapper

api = SensAIWrapper(db_url="sqlite:///galerelm.db")

def respond(message, history, email, chat_id):
    yield from api.chat_stream(email=email, prompt=message, context_id=chat_id)

def load_history(email, chat_id):
    return [{"role": m.role, "content": m.content} for m in api.get_chat_history(email, chat_id)]

def get_chats(email, chat_id):
    choices = [(f"Chat {c.id}", c.id) for c in api.list_chats(email)]
    return gr.Radio(choices=choices, value=chat_id)

def login(email, name, instructions):
    if not email:
        gr.Warning("Entre un email.")
        return gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
    api.create_profile(email=email, name=name, instructions=instructions)
    api.update_profile(email=email, name=name, instructions=instructions)
    chat_id = api.list_chats(email)[0].id  # le plus récent
    return email, chat_id, gr.Column(visible=False), gr.Column(visible=True), load_history(email, chat_id), get_chats(email, chat_id)

def logout():
    return "", None, gr.Column(visible=True), gr.Column(visible=False), [], gr.Radio(choices=[], value=None)

def new_chat(email):
    chat_id = api.start_new_chat(email).id
    return chat_id, [], get_chats(email, chat_id)

def open_chat(email, chat_id):
    return chat_id, load_history(email, chat_id)
