# 🖥️ 6. L'application web

Cette page décrit l'interface de SensAI **dans le navigateur**.

Elle est faite avec **Gradio**.

[⬅️ Retour au sommaire](README.md)

---

## ▶️ Lancer

1. Lancez le backend (Ollama) :

   ```bash
   ./script/backend.sh
   ```

2. Dans un **autre** terminal, à la racine du projet :

   ```bash
   ./script/frontend.sh
   ```

3. Ouvrez http://127.0.0.1:7860 dans le navigateur.

> [!NOTE]
> Le script lance Gradio en mode **rechargement automatique**.
> La page se met à jour quand vous sauvegardez un fichier de `src/webapp/`.

> [!WARNING]
> Le rechargement ne voit **pas** les changements dans `src/galerelm/`.
> Après une modification du backend, **relancez** le script (`Ctrl+C`, puis `./script/frontend.sh`).

---

## 👀 Ce que voit l'utilisateur

### 1. La page de connexion

C'est la page d'arrivée.

| Champ | Rôle |
|-------|------|
| Email | Identifie le profil |
| Nom | Nom du profil |
| Instructions | Consignes données à l'IA (ton, style…) |

- Le bouton **Se connecter** crée le profil s'il n'existe pas.
- S'il existe déjà, le nom et les instructions sont **mis à jour**.

> [!WARNING]
> Il n'y a **pas de mot de passe**.
> La connexion sert à **identifier** un profil, pas à le protéger.

### 2. La page du chat

Elle s'affiche après la connexion.

- Le **chat** : la réponse de l'IA s'écrit au fur et à mesure.
- Le bouton **Se déconnecter** : retour à la page de connexion.

### 3. La barre latérale

| Élément | Rôle |
|---------|------|
| Bouton **Nouvelle conversation** | Crée une conversation vide et l'ouvre |
| Liste **Conversations** | Toutes les conversations du profil. Un clic en ouvre une. |

- Les nouveaux messages vont dans la conversation **ouverte**.
- La conversation ouverte est **cochée** dans la liste.

---

## 📁 Les fichiers

Dossier : `src/webapp/`

| Fichier | Rôle |
|---------|------|
| `app.py` | Point d'entrée. Assemble les pages et branche les **événements**. |
| `views.py` | Classe `Views`. Construit les **composants** de chaque page. |
| `utils.py` | Les **fonctions** appelées par les boutons. Elles utilisent le [Wrapper](05-wrapper.md). |

Le script de lancement : `script/frontend.sh`.

---

## 🧩 Comment c'est organisé

### Une seule page, deux écrans

Il n'y a **qu'une** page web.

Elle contient deux blocs `gr.Column` :

| Bloc | Visible au départ |
|------|-------------------|
| `login_page` | ✅ oui |
| `chat_page` | ❌ non |

Pour changer d'écran, une fonction renvoie `gr.Column(visible=True)` ou `gr.Column(visible=False)`.

### Ce qui est retenu pendant la session

Deux `gr.State` gardent des valeurs **pour chaque onglet** du navigateur :

| State | Contient |
|-------|----------|
| `current_email` | L'email du profil connecté |
| `current_chat` | L'`id` de la conversation ouverte |

### Les événements

Un événement relie un composant à une fonction.

```python
bouton.click(fonction, inputs=[...], outputs=[...])
```

1. Gradio lit les valeurs des `inputs`.
2. Il appelle la fonction avec ces valeurs, **dans l'ordre**.
3. Ce que la fonction renvoie remplit les `outputs`, **dans l'ordre**.

| Événement | Fonction (`utils.py`) | Ce qui change |
|-----------|-----------------------|---------------|
| Clic sur **Se connecter** | `login` | Profil, conversation ouverte, écran, chat, liste |
| Clic sur **Se déconnecter** | `logout` | Tout est vidé, retour à la connexion |
| Clic sur **Nouvelle conversation** | `new_chat` | Nouvelle conversation ouverte, chat vide, liste |
| Clic dans la **liste** | `open_chat` | Conversation ouverte, chat |
| Message envoyé | `respond` | Réponse de l'IA, en streaming |

---

## ➕ Ajouter quelque chose

1. Créez le composant dans une méthode de `Views` (`views.py`).
2. Renvoyez-le avec `return`.
3. Écrivez la fonction dans `utils.py`.
4. Branchez l'événement dans `app.py`, **après** la création de tous les composants.

> [!TIP]
> Une fonction qui ne doit rien changer peut renvoyer `gr.skip()`.

---

[⬅️ Page précédente : Wrapper](05-wrapper.md) · [➡️ Page suivante : Terminal](07-terminal.md)
