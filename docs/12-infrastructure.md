# 🐳 12. Infrastructure

Cette page explique comment **installer** et **lancer** A1Libi avec les scripts.

[⬅️ Retour au sommaire](README.md)

---

## 🧰 Les fichiers

| Fichier | Rôle |
|---------|------|
| [`scripts/A1Libi`](../scripts/A1Libi) | Lance A1Libi avec **Docker** |
| [`scripts/A1Libi_dev`](../scripts/A1Libi_dev) | Lance A1Libi **sans Docker**, pour coder |
| [`Dockerfile`](../Dockerfile) | La recette de l'**image** de l'application |
| [`docker-compose.yaml`](../docker-compose.yaml) | Lance les **conteneurs** ensemble |
| [`.env.exemple`](../.env.exemple) | Le modèle du fichier de réglages `.env` |

Les scripts marchent depuis **n'importe quel dossier**.

Ils se placent tout seuls à la racine du projet.

---

## 🤔 Quel script choisir ?

| | `A1Libi` | `A1Libi_dev` |
|---|---|---|
| Pour qui | Pour **utiliser** A1Libi | Pour **coder** sur A1Libi |
| Il faut installer | Docker | Python 3.12 et Ollama |
| Ollama tourne | Dans Docker | Sur votre machine |
| Vitesse sur Mac | Plus **lent** (pas de GPU) | **Rapide** (GPU) |
| Recharge le code | Non | Oui, à chaque modification |

---

## 🐳 `A1Libi` : avec Docker

### Étapes

1. Installez [Docker](https://docs.docker.com/get-docker/).
2. Préparez le projet :

   ```bash
   ./scripts/A1Libi -setup
   ```

3. Lancez A1Libi :

   ```bash
   ./scripts/A1Libi -run
   ```

4. Ouvrez http://localhost:7860 dans le navigateur.

### Toutes les options

| Option | Ce qu'elle fait |
|--------|-----------------|
| `-setup` | Vérifie Docker, crée `.env`, prépare les images |
| `-run` | Lance tout **en arrière-plan** |
| `-stop` | Arrête tout |
| `-logs` | Affiche les logs en direct |
| `-cli` | Lance le terminal d'A1Libi |
| `-clean` | Arrête tout et **supprime** les volumes |

> [!NOTE]
> Le premier `-run` est **long**.
> Il télécharge plusieurs Go : Ollama et les modèles.
> Suivez l'avancée avec `./scripts/A1Libi -logs`.

> [!CAUTION]
> `-clean` supprime les **modèles téléchargés**.
> Il faudra les télécharger à nouveau.

### Ce que Docker lance

Docker lance **3 conteneurs**, dans cet ordre :

1. `ollama` : le serveur de l'IA.
2. `ollama-pull` : télécharge les modèles, puis s'arrête.
3. `app` : l'application web.

Chaque conteneur attend que le précédent soit **prêt**.

Les modèles sont gardés dans un **volume**.

Ils ne sont pas téléchargés à chaque lancement.

---

## 🛠️ `A1Libi_dev` : sans Docker

Il faut **deux terminaux**.

### Étapes

1. Installez Python 3.12 et [Ollama](https://ollama.com).
2. Préparez le projet :

   ```bash
   ./scripts/A1Libi_dev -setup
   ```

3. Dans le **terminal 1**, lancez Ollama :

   ```bash
   ./scripts/A1Libi_dev -back
   ```

   Laissez ce terminal **ouvert**.

4. Dans le **terminal 2**, lancez l'application web :

   ```bash
   ./scripts/A1Libi_dev -front
   ```

   Ou le terminal d'A1Libi :

   ```bash
   ./scripts/A1Libi_dev -cli
   ```

### Toutes les options

| Option | Ce qu'elle fait |
|--------|-----------------|
| `-setup` | Crée `.venv`, installe les dépendances, crée `.env` |
| `-back` | Lance Ollama, télécharge et charge les modèles |
| `-front` | Lance l'application web Gradio |
| `-cli` | Lance le terminal d'A1Libi |

> [!TIP]
> `Ctrl+C` sur `-back` arrête Ollama.
> Mais seulement si c'est le script qui l'a lancé.

---

## ⚙️ Le fichier `.env`

- Les deux scripts lisent le fichier `.env`.
- Il est à la **racine** du projet.
- `-setup` le crée à partir de `.env.exemple`.

> [!IMPORTANT]
> Avec Docker, `OLLAMA_HOST` est changé **automatiquement**.
> Il devient `http://ollama:11434`.
> Ne modifiez pas le `.env` pour ça.

---

## 🎨 Les couleurs des messages

`A1Libi` affiche ses messages en **couleur**.

| Préfixe | Couleur | Sens |
|---------|---------|------|
| `[*]` | cyan | Une information |
| `[+]` | gras | Une étape commence |
| `[✓]` | vert | Une étape a réussi |
| `[!]` | jaune | Attention |
| `[!]` | rouge | Une erreur |

### Pour écrire un message dans le script

Utilisez ces fonctions à la place de `echo` :

```sh
info    "Une information"
step    "Une étape commence"
success "Une étape a réussi"
warn    "Attention"
error   "Une erreur"
```

Pour colorer un seul mot, utilisez les variables `RED`, `GREEN`, `YELLOW`, `CYAN`, `BOLD` et `RESET` :

```sh
echo "${BOLD}important${RESET}"
```

> [!WARNING]
> Terminez **toujours** par `${RESET}`.
> Sinon, la suite du terminal reste en couleur.

Les couleurs sont **coupées** quand la sortie va dans un fichier.

Exemple : `./scripts/A1Libi -setup > log.txt`.

---

[⬅️ Page précédente : Classification d'intention](11-intent-classifier.md) · [🏠 Retour au sommaire](README.md)
