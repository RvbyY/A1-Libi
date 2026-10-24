<p align="center">
  <img src="docs/assets/A1-Libi.svg" width="120" alt="Logo A1Libi" />
</p>

<h1 align="center">A1Libi</h1>

<p align="center">
  <b>Assistant IA local, avec une mémoire courte et une mémoire longue.</b><br/>
  Propulsé par le framework GalèreLM · projet <a href="https://www.epitech.eu/">Epitech</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Ollama-IA%20locale-000000?style=flat-square&logo=ollama&logoColor=white" />
  <img src="https://img.shields.io/badge/Gradio-interface%20web-F97316?style=flat-square&logo=gradio&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-prêt-2496ED?style=flat-square&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/licence-MIT-4c1?style=flat-square" />
</p>

---

<p align="center">
  <img src="docs/assets/banner.svg" width="100%" alt="Premiers pas" />
</p>

Il faut seulement [Docker](https://docs.docker.com/get-docker/).

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
./scripts/A1Libi -setup   # prépare le projet
./scripts/A1Libi -run     # lance tout
```

Ouvrez ensuite **http://localhost:7860**.

> Le premier lancement télécharge les modèles d'IA : il peut prendre plusieurs minutes.

---

<p align="center">
  <a href="docs/README.md">
    <img src="docs/assets/banner-docs.svg" width="100%" alt="Ouvrir la documentation" />
  </a>
</p>

---

<p align="center">Licence <a href="LICENSE">MIT</a></p>
