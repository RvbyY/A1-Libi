# 🌐 7. RapideAPI

Cette page décrit le **client HTTP** du projet.

[⬅️ Retour au sommaire](README.md)

---

## 🎯 Rôle

RapideAPI envoie les requêtes à Ollama.

C'est la **seule** partie du projet qui fait des appels réseau.

Fichier : `src/rapideAPI/client.py`

---

## ▶️ Créer un client

```python
from src.rapideAPI import RapideAPI

api = RapideAPI(base_url="http://localhost:11434")
```

| Paramètre | Défaut | Rôle |
|-----------|--------|------|
| `base_url` | `""` | Adresse du serveur |
| `default_headers` | aucun | En-têtes ajoutés à chaque requête |
| `timeout` | 120 | Temps d'attente max, en secondes |

---

## 📤 Les méthodes

| Méthode | Rôle |
|---------|------|
| `get(endpoint)` | Lire |
| `post(endpoint, json=...)` | Envoyer |
| `put(endpoint, json=...)` | Remplacer |
| `patch(endpoint, json=...)` | Modifier |
| `delete(endpoint)` | Supprimer |
| `stream_ndjson(endpoint, json_data=...)` | Recevoir une réponse **morceau par morceau** |
| `health()` | Vérifie qu'Ollama répond |

Le résultat :

- Si le serveur renvoie du JSON → un **dictionnaire**.
- Sinon → du **texte**.

---

## 🌊 Le streaming

Ollama renvoie sa réponse en **NDJSON** : un objet JSON **par ligne**.

```
{"message": {"content": "Bon"}, "done": false}
{"message": {"content": "jour"}, "done": false}
{"done": true, "eval_count": 2}
```

`stream_ndjson()` lit chaque ligne et la renvoie aussitôt.

```python
for morceau in api.stream_ndjson("api/chat", json_data=payload):
    print(morceau["message"]["content"], end="")
```

---

## 🔌 Les adresses Ollama utilisées

| Adresse | Utilisée par | Rôle |
|---------|--------------|------|
| `api/chat` | `Chat` | Discuter |
| `api/embed` | `DeepContext` | Transformer du texte en vecteur |
| `api/tags` | `SensAIWrapper.get_status()` | Lister les modèles |
| `api/version` | `RapideAPI.health()` | Version d'Ollama |

---

## ⚠️ Les pièges d'Ollama

Ces erreurs ont déjà été rencontrées.

| Erreur | Cause | Solution |
|--------|-------|----------|
| HTTP 500 | Le champ `thinking` est dans un message | Ne pas l'envoyer (déjà fait dans `Message.format()`) |
| HTTP 400 | `logprobs: false` ou `top_logprobs: 0` est envoyé | Ne pas envoyer les options vides (déjà fait dans `Chat.format()`) |
| Le prompt système est ignoré | Il n'est pas en **première** position | Toujours le mettre en premier (déjà fait dans `Chat`) |
| Modèle introuvable | Nom du modèle mal écrit | Vérifier `HF_MODEL` dans `.env` |

---

## 📜 Les logs

Chaque requête est enregistrée :

```
==> [POST] http://localhost:11434/api/chat
<== [POST] http://localhost:11434/api/chat - Status: 200 - Temps: 1.42s
```

En cas d'erreur, le message du serveur est affiché.

---

[⬅️ Page précédente : Terminal](06-terminal.md) · [➡️ Page suivante : Glossaire](08-glossaire.md)
