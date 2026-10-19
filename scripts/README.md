# scripts/

Deux lanceurs pour le projet. Ils peuvent être appelés depuis n'importe quel dossier : chacun se place tout seul à la racine du projet.

| Fichier | Mode | Quand l'utiliser | Prérequis |
|---|---|---|---|
| `A1Libi` | Docker | Pour lancer le projet sans rien installer d'autre | Docker |
| `A1Libi_dev` | Natif | Pour coder : rechargement automatique | Python 3.12 + [Ollama](https://ollama.com) |

## `A1Libi` : script Docker

Tout tourne dans des conteneurs (Ollama, téléchargement des modèles, app web) via `docker-compose.yaml`.

```bash
./scripts/A1Libi -setup   # vérifie Docker, crée .env, build les images
./scripts/A1Libi -run     # lance tout en arrière-plan → http://localhost:7860
./scripts/A1Libi -stop    # arrête tout
./scripts/A1Libi -logs    # suit les logs
./scripts/A1Libi -cli     # lance la CLI dans le conteneur
./scripts/A1Libi -clean   # arrête + supprime les volumes (/!\ modèles re-téléchargés)
```

> Le premier `-run` télécharge plusieurs Go (image Ollama + modèles).
> Sur Mac, Ollama dans Docker n'a pas accès au GPU : les réponses sont plus lentes qu'en mode dev.

## `A1Libi_dev` : script développement

Tout tourne directement sur ta machine, dans le `.venv`, avec l'Ollama installé localement. Il faut deux terminaux.

```bash
./scripts/A1Libi_dev -setup   # crée .venv, installe les dépendances, crée .env

# Terminal 1
./scripts/A1Libi_dev -back    # lance Ollama, télécharge et précharge les modèles (bloquant)

# Terminal 2
./scripts/A1Libi_dev -front   # app web Gradio (recharge à chaque modif)
./scripts/A1Libi_dev -cli     # ou la CLI
```

`Ctrl+C` sur `-back` arrête Ollama, mais seulement si c'est le script qui l'a lancé.

## Messages et couleurs

`A1Libi` affiche ses messages avec un préfixe coloré. Pour écrire un message, on passe par ces fonctions plutôt que par `echo` :

| Fonction | Préfixe | Couleur | Usage |
|---|---|---|---|
| `info`    | `[*]` | cyan  | information, rien à faire |
| `step`    | `[+]` | gras  | une étape commence |
| `success` | `[✓]` | vert  | étape terminée avec succès |
| `warn`    | `[!]` | jaune | attention, action destructive ou lente |
| `error`   | `[!]` | rouge | erreur (écrite sur la sortie d'erreur, stderr) |

```sh
step "Building images..."
error "Docker n'est pas installé"
```

Les couleurs sont des variables (`RED`, `GREEN`, `YELLOW`, `CYAN`, `BOLD`, `RESET`). On peut aussi les utiliser directement dans un texte : `"${BOLD}important${RESET}"`. Pense à toujours terminer par `${RESET}`, sinon la suite du terminal reste colorée.

Les couleurs sont **désactivées automatiquement** quand la sortie n'est pas un terminal (par exemple `./scripts/A1Libi -setup > log.txt`), pour ne pas remplir le fichier de codes illisibles.

> Les codes sont créés avec `printf '\033[..m'` et non `$'...'`, pour rester compatible avec `sh` (dash sur Linux).

## Configuration

Les deux scripts lisent le fichier `.env` à la racine. `-setup` le crée à partir de `.env.exemple` s'il n'existe pas.
En mode Docker, `OLLAMA_HOST` est remplacé automatiquement par `http://ollama:11434` : pas besoin de modifier le `.env`.
