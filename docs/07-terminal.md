# ⌨️ 7. Le terminal

Cette page décrit l'utilisation de SensAI **dans le terminal**.

[⬅️ Retour au sommaire](README.md)

---

## 📦 Prérequis

Le terminal utilise la librairie **rich**.

Elle sert à afficher les couleurs, le cadre d'accueil et le prompt.

```bash
.venv/bin/pip install rich
```

> [!NOTE]
> rich est souvent déjà installé avec Gradio.
> Vérifiez avec : `.venv/bin/python -c "import rich"`

---

## ▶️ Lancer

1. Lancez Ollama (`./script/backend.sh`).
2. À la racine du projet :

```bash
PYTHONPATH="$PWD:$PWD/src" .venv/bin/python src/main.py
```

---

## 👀 À quoi ça ressemble

Le style est celui d'un **terminal de hacker** : écriture verte.

```
╭─ [ A1-LIBI ] ────────────────────────────────────────────────╮
│  ▄▀█ ▄█        A1-Libi v0.1 · uncensored                     │
│  █▀█  █        > session : Utilisateur · 10 messages chargés │
│  █   █ █▄▄ █   > modèle  : Qwen3.8-2B-Uncensored-GGUF        │
│  █▄▄ █ █▄█ █   > tapez /help pour les commandes              │
╰──────────────────────────────────────────────────────────────╯

┌──(Utilisateur㉿a1-libi)-[~]
└─❯ salut

>_ Salut ! Comment puis-je t'aider ?
```

| Élément | Rôle |
|---------|------|
| Le cadre en haut | Logo, profil, nombre de messages, modèle |
| `┌──(…)` et `└─❯` | Le prompt : c'est là que vous tapez |
| `>_` | Le début de la réponse de l'IA |
| Texte rouge | Une erreur |

> [!TIP]
> rich colore le **texte**, pas le fond.
> Pour un fond noir, changez le thème de votre terminal.

---

## 🔤 Message ou commande ?

| Vous tapez | Ce qui se passe |
|------------|-----------------|
| Un texte normal | Il est envoyé à l'IA |
| Un texte qui commence par `/` | C'est une **commande**. Rien n'est envoyé à l'IA. |

---

## 📋 Les commandes

### Général

| Commande | Effet |
|----------|-------|
| `/help` | Affiche la liste des commandes |
| `/quit` | Quitte. Marche aussi avec `/exit` et `/q`. |

### Voir l'état

| Commande | Effet |
|----------|-------|
| `/profile` | Affiche le profil |
| `/context` | Affiche les chiffres de la conversation |
| `/messages` | Affiche la mémoire courte |
| `/memories` | Affiche la mémoire longue |
| `/payload` | Affiche le JSON exact envoyé à l'IA |

### Mémoire longue

| Commande | Effet |
|----------|-------|
| `/recall <texte>` | Cherche dans la mémoire longue, avec les scores |

Exemple :

```
└─❯ /recall où j'habite
── Résultats RAG pour "où j'habite" (2 trouvés) ──
  1. 👤 [user] (score: 0.8123) J'habite à Paris
  2. 🤖 [assistant] (score: 0.7710) Noté, vous habitez à Paris.
```

### Repartir de zéro

| Commande | Effet |
|----------|-------|
| `/clear` | Vide la mémoire courte |
| `/new` | Crée une nouvelle conversation |

> [!NOTE]
> `/clear` et `/new` **ne suppriment pas** la mémoire longue.

---

## 🧩 Comment le code est organisé

Fichier : `src/repl.py`

| Fonction | Rôle |
|----------|------|
| `repl(sensai)` | La boucle principale. Elle dirige tout. |
| `print_welcome` | Affiche le cadre d'accueil |
| `read_input` | Affiche le prompt et lit la saisie |
| `handle_command` | Exécute une commande `/…`. Renvoie `True` pour quitter. |
| `stream_answer` | Envoie le message à l'IA et affiche la réponse au fur et à mesure |
| `save_answer` | Enregistre la réponse dans la base |
| `_cmd_…` | Une fonction par commande |

`src/main.py` crée l'objet `SensAI`, puis appelle `repl(sensai)`.

---

## 🎨 Changer les couleurs

Toutes les couleurs sont dans **un seul** endroit : `THEME`, en haut de `src/repl.py`.

```python
THEME = Theme({
    "hack":        "green",
    "hack.dim":    "dim green",
    "hack.bright": "bold bright_green",
    "hack.error":  "bold red",
})
```

- Dans le code, on écrit `[hack]texte[/]`.
- Changez `green` ici, et tout le terminal change.

> [!WARNING]
> Avec `console.print`, un `[` dans le texte est lu comme un style.
> Pour afficher un vrai `[`, mettez un `\` devant.
> Dans une chaîne Python, cela s'écrit `"\\["`.

---

## ➕ Ajouter une commande

1. Ouvrez `src/repl.py`.
2. Ajoutez une fonction :

```python
def _cmd_bonjour(self, args: str):
    """Dit bonjour."""
    console.print(f"[hack]Bonjour {self.profile.name} ![/]")
```

3. Ajoutez-la dans le dictionnaire `_commands`, en bas du fichier :

```python
"/bonjour": _cmd_bonjour,
```

C'est tout.

- La phrase entre `"""` apparaît dans `/help`.
- Renvoyez `True` pour **quitter** le programme.

---

## 📜 Les logs

Par défaut, les logs sont **cachés**.

Seules les **erreurs** s'affichent, pour garder un terminal lisible.

Pour les revoir, dans `src/main.py`, en bas du fichier :

1. Décommentez la ligne `logging.basicConfig(level=logging.INFO, …)`.
2. Commentez la ligne `logging.basicConfig(level=logging.ERROR)`.

Format :

```
2026-10-05 12:00:00 - galerelm.models.context - INFO - [Context] Ajout d'un message (user)
```

| Nom du log | Partie |
|------------|--------|
| `sensai` | `main.py` |
| `galerelm.models.context` | Mémoire courte |
| `galerelm.models.deep_context` | Mémoire longue |
| `galerelm.models.chat` | Requêtes vers l'IA |
| `galerelm.wrapper` | Wrapper |
| `src.rapideAPI.client` | Appels HTTP |

Pour encore plus de détails, remplacez `INFO` par `DEBUG`.

---

[⬅️ Page précédente : Application web](06-web-application.md) · [➡️ Page suivante : RapideAPI](08-rapideapi.md)
