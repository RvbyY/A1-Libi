# SensAI

Local AI assistant using Ollama.

## Requirements

- Python 3.10+
- Ollama
- Internet connection for the first model download

## Setup

```bash
./setup.sh```

## Run

Start Ollama and pull the model (in a first terminal):

```bash
./script/backend.sh
```

Then start the CLI chatbot (in a second terminal):

```bash
PYTHONPATH=. .venv/bin/python src/main.py
```

### Choosing the model

The model can be selected without touching the code, either on the command line:

```bash
PYTHONPATH=. .venv/bin/python src/main.py --model qwen2.5:7b
```

or in a YAML configuration file (see [config.example.yaml](config.example.yaml)):

```bash
cp config.example.yaml config.yaml
PYTHONPATH=. .venv/bin/python src/main.py                         # ./config.yaml is loaded automatically
PYTHONPATH=. .venv/bin/python src/main.py --config other.yaml     # or pass a file explicitly
```

Priority: CLI arguments > YAML file > environment variables (`.env`) > defaults.
Run `src/main.py --help` for every option (`--host`, `--embed-model`, `--db`, `--skip-check`).

### Anti-hallucination loop

```bash
PYTHONPATH=. .venv/bin/python src/main.py --anti-hallucination --max-retries 3
```

Each answer is checked by an LLM judge against the known facts (RAG memories, tool outputs) and regenerated
with the judge's critique when it is not grounded, up to `--max-retries` times (default: 2).
In this mode the answer is displayed once validated, not streamed token by token.

### Startup checks

Before opening the chat, SensAI checks that Ollama answers and that the model is installed:

| Situation | Message | Exit code |
|-----------|---------|-----------|
| Ollama not running / wrong `--host` | `Impossible de joindre Ollama sur …` + how to start it | 1 |
| Model not installed | `Le modèle '…' n'est pas installé` + `ollama pull …` and the installed models | 1 |
| Invalid YAML / unknown key | `Configuration invalide : …` | 2 |
| Embedding model missing | Warning only: long-term memory (RAG) is disabled | — |

The same messages are shown if Ollama stops or times out during a conversation; the session keeps running.

## User stories

The user stories required by the project (at least two per implemented feature) are listed in
[USER_STORIES.md](USER_STORIES.md), with one detailed page per feature in [docs/user_stories](docs/user_stories/README.md).
