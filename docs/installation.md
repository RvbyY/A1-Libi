# Installation et Utilisation de SensAI

Ce guide explique comment installer SensAI.
Il vous montre ensuite comment l'utiliser de deux manières :
1. Dans le terminal (en ligne de commande).
2. Sur le web (avec le Wrapper pour Gradio ou FastAPI).

---

## 🛠️ 1. Installation du projet

**Étape 1 : Préparer l'environnement Python**
SensAI a besoin de Python 3.10 ou plus.
Ouvrez votre terminal et tapez ces commandes :

```bash
# Créer un environnement virtuel
python3 -m venv .venv

# Activer l'environnement
source .venv/bin/activate

# Installer les dépendances (SQLAlchemy, httpx, etc.)
pip install -r requirements.txt
```

**Étape 2 : Lancer Ollama**
SensAI utilise Ollama pour faire tourner l'IA localement.
Assurez-vous que l'application Ollama est ouverte en arrière-plan.

**Étape 3 : Configurer le projet (Optionnel)**
Par défaut, SensAI utilise :
- Le modèle : `llama3.2`
- La base de données : `galerelm.db` (créée automatiquement)
- Le port Ollama : `http://localhost:11434`

Vous pouvez modifier ces valeurs dans le fichier `.env` si vous le souhaitez.

---

## 💻 2. Utilisation dans le Terminal (CLI)

C'est la méthode la plus rapide pour tester l'IA.
Tout se passe directement dans votre invite de commande.

**Pour lancer SensAI :**
```bash
python -m src.main
```

**Comment ça marche ?**
- Au premier lancement, l'IA vous demandera votre nom, votre email, et vos instructions système (comment l'IA doit se comporter).
- Vous pouvez ensuite taper vos messages et discuter normalement.
- L'IA mémorise tout dans une base de données locale.

**Les commandes magiques :**
Tapez ces commandes dans le chat pour contrôler l'IA :
- `/help` : Affiche toutes les commandes disponibles.
- `/new` : Démarre une nouvelle conversation vierge. (Les anciennes mémoires restent accessibles).
- `/messages` : Affiche l'historique court de la discussion actuelle.
- `/memories` : Affiche toutes les mémoires long-terme archivées de votre profil.
- `/recall <mot>` : Cherche une ancienne conversation dans votre mémoire long-terme.
- `/quit` : Ferme l'application.

---

## 🌐 3. Utilisation pour le Web (Le Wrapper)

Le `SensAIWrapper` est conçu pour les développeurs.
Il est parfait si vous voulez créer une interface web (avec Gradio, Streamlit ou FastAPI).

**Pourquoi utiliser le Wrapper ?**
- Il est "Thread-Safe" (il gère plusieurs utilisateurs en même temps sans mélanger les données).
- Il est "Stateless" (il ne bloque pas le serveur).
- Il renvoie des objets propres et sécurisés (DTOs).

**Exemple de code simple pour Python :**

```python
from src.galerelm.wrapper import SensAIWrapper

# 1. Initialiser le Wrapper
api = SensAIWrapper(db_url="sqlite:///galerelm.db")

# 2. Créer un profil utilisateur
mon_email = "test@test.com"
api.create_profile(
    email=mon_email,
    name="Alice",
    instructions="Réponds toujours comme une pirate informatique."
)

# 3. Poser une question et recevoir la réponse en direct (Streaming)
question = "Comment pirater une disquette ?"
generateur = api.chat_stream(email=mon_email, prompt=question)

# 4. Afficher la réponse petit à petit
for texte in generateur:
    print(texte)
```

**Principales fonctions du Wrapper :**
- `create_profile(...)` : Crée un utilisateur.
- `chat_stream(...)` : Renvoie la réponse mot par mot (idéal pour Gradio).
- `chat_blocking(...)` : Attend la fin de la phrase pour renvoyer la réponse complète.
- `get_chat_history(...)` : Récupère la discussion en cours.
- `get_memories(...)` : Récupère les mémoires long-terme de l'utilisateur.
