# 🚀 1. Démarrage

Cette page explique comment **installer** et **lancer** A1Libi.

[⬅️ Retour au sommaire](README.md)

> [!TIP]
> Vous voulez juste **utiliser** A1Libi ?
> Le plus simple est Docker : une seule commande.
> Voir [Infrastructure](12-infrastructure.md).
>
> Cette page explique l'installation **sans Docker**, pour coder.

---

## ✅ Ce qu'il faut avant de commencer

- **Python** 3.12.
- **Ollama** installé sur la machine.
- Une **connexion internet** pour le premier téléchargement du modèle.

---

## 📦 Étape 1 : Installer le projet

Ouvrez un terminal dans le dossier du projet.

Lancez :

```bash
./scripts/A1Libi_dev -setup
```

Ce [script](../scripts/A1Libi_dev) fait 3 choses :

1. Il crée un environnement Python dans `.venv`.
2. Il installe les dépendances.
3. Il crée le fichier `.env` à partir de `.env.exemple`.

---

## ⚙️ Étape 2 : Vérifier le fichier `.env`

Les 3 réglages les plus importants :

| Nom | Rôle | Exemple |
|-----|------|---------|
| `HF_MODEL` | Le modèle d'IA à utiliser | `hf.co/atakhadivi/Qwen3.8-2B-Uncensored-GGUF` |
| `EMBED_MODEL` | Le modèle de la mémoire longue | `nomic-embed-text` |
| `OLLAMA_HOST` | L'adresse d'Ollama | `http://localhost:11434` |

La liste complète est dans [`.env.exemple`](../.env.exemple).

> [!IMPORTANT]
> Le nom du modèle doit être **exact**.
> Une seule lettre fausse, et Ollama refuse la requête.
> SensAI le vérifie au démarrage et affiche la commande `ollama pull` à lancer.

### Optionnel : fichier `config.yaml`

Au lieu du `.env`, vous pouvez copier [config.example.yaml](../config.example.yaml) en `config.yaml`.
Il est chargé automatiquement au lancement.

Vous pouvez aussi choisir le modèle directement en ligne de commande :

```bash
PYTHONPATH=. .venv/bin/python src/main.py --model llama3.2
PYTHONPATH=. .venv/bin/python src/main.py --config mon_fichier.yaml
```

Ordre de priorité : **arguments CLI > `config.yaml` > `.env` > valeurs par défaut**.

---

## 🧠 Étape 3 : Lancer Ollama

Lancez :

```bash
./scripts/A1Libi_dev -back
```

Ce script fait 4 choses :

1. Il démarre Ollama s'il n'est pas déjà lancé.
2. Il attend que l'API réponde.
3. Il télécharge les **2 modèles** s'ils manquent : `HF_MODEL` et `EMBED_MODEL`.
4. Il charge le modèle en mémoire.

Laissez ce terminal **ouvert**.

> [!NOTE]
> `EMBED_MODEL` sert à la mémoire longue.
> Il transforme le texte en nombres (voir [Mémoire](03-memoire.md)).

---

## 💬 Étape 4 : Discuter

Ouvrez un **second** terminal.

Pour discuter dans le terminal, lancez :

```bash
./scripts/A1Libi_dev -cli
```

Pour discuter dans le navigateur, lancez :

```bash
./scripts/A1Libi_dev -front
```

Avec `-cli`, vous voyez :

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
- Elle est créée à la **racine** du projet (les scripts s'y placent tout seuls).

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
> Voir [Problèmes connus](10-problemes-connus.md).

---

[➡️ Page suivante : Architecture](02-architecture.md)
