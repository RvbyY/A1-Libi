import requests
from src.galerelm.models.profile import Profile
from typing import Literal

Structure = Literal["json", "csv"]

messages = [
    {"role": "system", "content": "Tu es un homme complétement en colère contre moi"}
]

def generate_prompt(prompt: str, profile: Profile = None, persistence: bool = True, budgeting: int = -1, tools: bool = True, sandbox_code: bool = True, web_search: bool = True, file_access: bool = True, structured_language: Structure = "json", reasoning: bool = True, rollback: bool = True, persona: str = None, interrupt: bool = True):
    return "prompt"

def main():
    while True:
        user_input = input("Me: ")
        if user_input.lower() in ("exit", "quit"):
            break
        messages.append({"role": "user", "content": user_input})
        res = requests.post( "http://localhost:11434/api/chat", json={"model": "llama3", "messages": messages, "stream": False} )
        reply = res.json()["message"]["content"]
        print(f"robot de con: {reply}")
        messages.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    main()
