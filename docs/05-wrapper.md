# 🎁 5. Le Wrapper (pour Gradio)

Cette page décrit les fonctions à utiliser **depuis une interface**.

[⬅️ Retour au sommaire](README.md)

---

## 🎯 À quoi sert le wrapper

Le wrapper cache toute la complexité.

- ✅ Vous **utilisez** ces fonctions.
- ❌ Vous **n'utilisez pas** directement `Context`, `Chat`, la base…

Fichier : `src/galerelm/wrapper.py`

Classe : `SensAIWrapper`

---

## ▶️ Démarrer

```python
from src.galerelm.wrapper import SensAIWrapper

ai = SensAIWrapper("sqlite:///galerelm.db")
```

---

## 📦 Les objets de réponse

Les fonctions ne renvoient **pas** de dictionnaires.

Elles renvoient des **objets typés**. Ils sont dans `models/dto.py`.

Avantage : l'éditeur **propose** les champs, et les fautes de frappe sont **détectées**.

| Objet | Champs |
|-------|--------|
| `ProfileResponse` | `id`, `name`, `email`, `instructions` |
| `ContextResponse` | `id`, `profile_id`, `context_limit` |
| `MessageResponse` | `role`, `content` |
| `ChatCompletionResponse` | `message`, `eval_count`, `eval_duration` |
| `MemoryResponse` | `id`, `role`, `content`, `score` |
| `StatusResponse` | `db_status`, `api_status`, `active_model` |

---

## 🧑 1. Profils

| Fonction | Renvoie | Rôle |
|----------|---------|------|
| `create_profile(email, name, instructions)` | `ProfileResponse` | Crée un profil et sa première conversation |
| `get_profile(email)` | `ProfileResponse` ou `None` | Lit un profil |
| `update_profile(email, name, instructions)` | `ProfileResponse` | Modifie un profil |
| `list_profiles()` | liste de `ProfileResponse` | Tous les profils |

---

## 💬 2. Conversations

| Fonction | Renvoie | Rôle |
|----------|---------|------|
| `start_new_chat(email)` | `ContextResponse` | Nouvelle conversation vide |
| `get_chat_history(email)` | liste de `MessageResponse` | Messages de la conversation en cours |
| `clear_chat(email)` | `bool` | Vide la conversation en cours |

> [!NOTE]
> La conversation "en cours" est la **plus récente** du profil.

---

## 🤖 3. Discuter

| Fonction | Renvoie | Rôle |
|----------|---------|------|
| `chat_stream(email, prompt)` | générateur de `str` | Réponse qui **grandit** au fil de l'écriture |
| `chat_blocking(email, prompt)` | `ChatCompletionResponse` | Réponse **complète**, d'un coup |

Pour `chat_stream`, chaque valeur contient **tout le texte depuis le début** :

```
"Bon"
"Bonjour"
"Bonjour !"
```

C'est le format attendu par Gradio.

Les deux fonctions :

1. Sauvegardent le message.
2. Cherchent les souvenirs (RAG).
3. Appellent l'IA.
4. Sauvegardent la réponse.

---

## 🔵 4. Mémoire longue

| Fonction | Renvoie | Rôle |
|----------|---------|------|
| `get_memories(email)` | liste de `MemoryResponse` | Tous les souvenirs |
| `search_memories(email, query, top_k)` | liste de `MemoryResponse` | Souvenirs proches, avec `score` |
| `delete_memory(memory_id)` | `bool` | Supprime un souvenir |

---

## 🩺 5. Système

| Fonction | Renvoie | Rôle |
|----------|---------|------|
| `get_status()` | `StatusResponse` | État de la base et d'Ollama |
| `set_active_model(model_name)` | `bool` | Change de modèle |

---

## 🧪 Exemple complet avec Gradio

```python
import gradio as gr
from src.galerelm.wrapper import SensAIWrapper

ai = SensAIWrapper()
EMAIL = "user@sensai.ai"
ai.create_profile(EMAIL, "Utilisateur", "Tu es un assistant concis.")


def repondre(message, historique):
    for texte in ai.chat_stream(EMAIL, message):
        yield texte


gr.ChatInterface(repondre, type="messages").launch()
```

Pour afficher l'historique dans un `gr.Chatbot` :

```python
historique = [
    {"role": m.role, "content": m.content}
    for m in ai.get_chat_history(EMAIL)
]
```

---

## ⚠️ Erreurs possibles

| Situation | Ce qui se passe |
|-----------|-----------------|
| Email inconnu | `ValueError` |
| Pas de conversation | `ValueError` |
| L'IA ne répond pas (`chat_blocking`) | `RuntimeError` |

> [!WARNING]
> Le wrapper utilise **une seule** session de base de données.
> Avec plusieurs utilisateurs **en même temps**, des conflits sont possibles.

---

[⬅️ Page précédente : Modèles](04-modeles.md) · [➡️ Page suivante : Terminal](06-terminal.md)
