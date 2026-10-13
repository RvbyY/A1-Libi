# 🚀 1. Démarrage

Cette page explique comment **installer** et **lancer** SensAI.

[⬅️ Retour au sommaire](README.md)

---

## ✅ Ce qu'il faut avant de commencer

- **Python** 3.10 ou plus récent.
- **Ollama** installé sur la machine.
- Une **connexion internet** pour le premier téléchargement du modèle.

---

## 📦 Étape 1 : Installer le projet

Ouvrez un terminal dans le dossier du projet.

Lancez :

```bash
./setup.sh
```

Ce script fait 3 choses :

1. Il crée un environnement Python dans `.venv`.
2. Il installe les dépendances.
3. Il crée le fichier `.env` à partir de `.env.exemple`.

> [!WARNING]
> Le fichier `requirements.txt` est **vide** pour le moment.
> Installez les dépendances à la main :
>
> ```bash
> .venv/bin/pip install sqlalchemy requests python-dotenv gradio pytest pytest-cov
> ```

---

## ⚙️ Étape 2 : Vérifier le fichier `.env`

Le fichier `.env` contient 2 réglages.

| Nom | Rôle | Exemple |
|-----|------|---------|
| `HF_MODEL` | Le modèle d'IA à utiliser | `hf.co/atakhadivi/Qwen3.8-2B-Uncensored-GGUF` |
| `OLLAMA_HOST` | L'adresse d'Ollama | `http://localhost:11434` |

> [!IMPORTANT]
> Le nom du modèle doit être **exact**.
> Une seule lettre fausse, et Ollama refuse la requête.

---

## 🧠 Étape 3 : Lancer Ollama

Lancez :

```bash
./backend.sh
```

Ce script fait 4 choses :

1. Il démarre Ollama s'il n'est pas déjà lancé.
2. Il attend que l'API réponde.
3. Il télécharge le modèle s'il manque.
4. Il charge le modèle en mémoire.

Laissez ce terminal **ouvert**.

---

## 🔎 Étape 4 : Installer le modèle de mémoire longue

La mémoire longue a besoin d'un **second modèle**.

Ce modèle transforme le texte en nombres (voir [Mémoire](03-memoire.md)).

Lancez une seule fois :

```bash
ollama pull nomic-embed-text
```

> [!NOTE]
> Sans ce modèle, SensAI fonctionne quand même.
> Mais la mémoire longue ne pourra pas retrouver les anciens messages.

---

## 💬 Étape 5 : Discuter dans le terminal

Ouvrez un **second** terminal.

Lancez :

```bash
PYTHONPATH=. .venv/bin/python src/main.py
```

Vous voyez :

```
Bienvenue Utilisateur ! (Historique: 0 messages chargés)
Tapez /help pour voir les commandes disponibles.

Vous :
```

Tapez votre message, puis **Entrée**.

Tapez `/quit` pour quitter.

---

## 🗄️ La base de données

- Elle est créée **automatiquement** au premier lancement.
- Elle s'appelle `galerelm.db`.
- Elle est créée dans le dossier **où vous lancez la commande**.

Pour repartir de zéro, supprimez-la :

```bash
rm galerelm.db
```

> [!CAUTION]
> Supprimer ce fichier efface **tous** les profils et **toutes** les conversations.

---

## 🧪 Lancer les tests

```bash
.venv/bin/pytest src/galerelm/unit_tests
```

> [!WARNING]
> Les tests sont **cassés** pour le moment.
> Voir [Problèmes connus](09-problemes-connus.md).

---

[➡️ Page suivante : Architecture](02-architecture.md)
