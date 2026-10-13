import requests
from src.galerelm.models.profile import Profile
from typing import Literal

Structure = Literal["json", "csv"]

from src.model.intent_classifier import classify_request
from src.model.ollama_client import call_ollama
from src.model.prompt_template import generate_prompt


CHAT_OPTIONS = {
    "temperature": 0.4,
    "top_k": 30,
    "top_p": 0.85,
    "num_predict": 512,
    "repeat_penalty": 1.2,
    "repeat_last_n": 128,
}


messages = [
    {
        "role": "system",
        "content": (
            "Tu es Alibi. "
            "Sois direct, concis, sérieux et non répétitif."
        ),
    }
]


def send_message(user_input: str) -> str:
    category = classify_request(user_input)

    if category == "LEGAL":
        return "Cela ne te menera nulle part de savoir cela..."

    if category == "AMBIGUOUS":
        return "Requête ambiguë."

    prompt = generate_prompt(
        prompt=user_input,
        persona="Alibi",
    )

    messages.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    data = call_ollama(
        messages=messages,
        options=CHAT_OPTIONS,
    )

    reply = data["message"]["content"]

    messages.append(
        {
            "role": "assistant",
            "content": reply,
        }
    )

    return reply


def main():
    while True:
        user_input = input("Me: ").strip()

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            break

        try:
            reply = send_message(user_input)
            print(f"Alibi: {reply}")

        except requests.RequestException as exc:
            print(f"Erreur Ollama: {exc}")

        except (KeyError, ValueError) as exc:
            print(f"Réponse Ollama invalide: {exc}")


if __name__ == "__main__":
    main()