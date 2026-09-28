import gradio as gr
from src.model.basic_chat_bot import generate_prompt
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

gr.Markdown("# Ici c'est la galère")

chatbot = gr.Interface(
    generate_prompt,
    inputs=["textbox"],
    outputs=["textbox"],
    additional_inputs=[
        gr.State(None),  # profile: Profile = None
        gr.Checkbox(label="Persistence", value=True),  # persistence: bool = True
        gr.Number(label="Budgeting", value=-1, precision=0),  # budgeting: int = -1
        gr.Checkbox(label="Tools", value=True),  # tools: bool = True
        gr.Checkbox(label="Sandbox code", value=True),  # sandbox_code: bool = True
        gr.Checkbox(label="Web search", value=True),  # web_search: bool = True
        gr.Checkbox(label="File access", value=True),  # file_access: bool = True
        gr.Dropdown(choices=["json", "csv"], value="json", label="Structured language"),  # structured_language: Structure = "json"
        gr.Checkbox(label="Reasoning", value=True),  # reasoning: bool = True
        gr.Checkbox(label="Rollback", value=True),  # rollback: bool = True
        gr.Textbox(label="Persona", placeholder="Persona", value=""),  # persona: str = None
        gr.Checkbox(label="Interrupt", value=True)  # interrupt: bool = True
    ],
    api_name="galere",
)
