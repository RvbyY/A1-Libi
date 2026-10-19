import os
import requests

from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.getenv(
    "HF_MODEL",
    "hf.co/atakhadivi/Qwen3.8-2B-Uncensored-GGUF:latest",
)

OLLAMA_URL = f"{OLLAMA_HOST}/api/chat"


def call_ollama(
    messages: list[dict],
    options: dict | None = None,
    timeout: int = 120,
    think: bool | None = None,
) -> dict:
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
    }

    if options is not None:
        payload["options"] = options

    if think is not None:
        payload["think"] = think

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=timeout,
    )

    response.raise_for_status()

    return response.json()