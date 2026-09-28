# SensAI
## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run webapp (Gradio)

```bash
python -m src.webapp.main
```

## Run CLI (`basic_chat_bot.py`)

1. Install and run [Ollama](https://ollama.com/), to get the used model :
   ```bash
   ollama pull llama3
   ollama serve
   ```
   (Ollama listenning on `http://localhost:11434`.)
2. Run the script :
   ```bash
   python -m src.model.basic_chat_bot
   ```
3. Send a message, `exit` or `quit` for leave.
