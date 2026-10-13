# ⌨️ 6. Le terminal

Cette page décrit l'utilisation de SensAI **dans le terminal**.

[⬅️ Retour au sommaire](README.md)

---

## ▶️ Lancer

```bash
PYTHONPATH=. .venv/bin/python src/main.py
```

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
Vous : /recall où j'habite
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

## ➕ Ajouter une commande

1. Ouvrez `src/main.py`.
2. Ajoutez une méthode dans la classe `SensAI` :

```python
def _cmd_bonjour(self, args: str):
    """Dit bonjour."""
    print(f"Bonjour {self.profile.name} !")
```

3. Ajoutez-la dans le dictionnaire `_commands` :

```python
"/bonjour": _cmd_bonjour,
```

C'est tout.

- La phrase entre `"""` apparaît dans `/help`.
- Renvoyez `True` pour **quitter** le programme.

---

## 📜 Les logs

Les logs s'affichent dans le terminal.

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

Pour voir plus de détails, changez `INFO` en `DEBUG` en bas de `main.py`.

---

[⬅️ Page précédente : Wrapper](05-wrapper.md) · [➡️ Page suivante : RapideAPI](07-rapideapi.md)
