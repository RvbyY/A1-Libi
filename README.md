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

## Run with Docker

Prepare the Docker images and the environment:

```bash
./scripts/A1Libi -setup
```

Start Ollama, download the configured models, and launch the web application:

```bash
./scripts/A1Libi -run
```

Open **http://localhost:7860** in your browser. Follow the startup logs with:

```bash
./scripts/A1Libi -logs
```

### Choosing the model

For the Docker setup, edit `HF_MODEL` and `EMBED_MODEL` in `.env`, then restart the
services:

```bash
./scripts/A1Libi -stop
./scripts/A1Libi -run
```

To pass a one-off model override to the CLI container:

```bash
docker compose run --rm app python src/main.py --model qwen2.5:7b
```

Run `docker compose run --rm app python src/main.py --help` for every option.

### Generation parameters

Temperature, context size, maximum length, seed, stop sequences and `keep_alive` are configurable
per profile (`chat`, `judge`, `guardrail`) in `config.yaml`, with CLI flags (`--temperature`, `--num-ctx`,
`--num-predict`, `--seed`, `--keep-alive`…) or live with `/params` in the chat.
Values, validation rules and the reasons behind the defaults: [docs/15-parametres-generation.md](docs/15-parametres-generation.md).

### Anti-hallucination loop

```bash
docker compose run --rm app python src/main.py --anti-hallucination --max-retries 3
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

> The first launch downloads the AI models and can take several minutes.

---

<p align="center">
  <a href="docs/README.md">
    <img src="docs/assets/banner-docs.svg" width="100%" alt="Ouvrir la documentation" />
  </a>
</p>

---

<p align="center">Licence <a href="LICENSE">MIT</a></p>
