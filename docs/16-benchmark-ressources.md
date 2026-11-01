# 16. Benchmark des ressources locales

Cette page décrit comment SensAI mesure ce que coûte le modèle sur la machine :
vitesse, latence et mémoire.

Elle donne le protocole, les résultats mesurés et les choix qui en découlent.

[Retour au sommaire](README.md)

---

## Objectif

Répondre à trois questions, avec des chiffres :

1. Le modèle est-il assez rapide pour une conversation fluide sur cette machine ?
2. Que coûte le passage du GPU au CPU, et l'augmentation de la fenêtre de contexte (`num_ctx`) ?
3. Quels réglages choisir pour la configuration par défaut ([Paramètres de génération](15-parametres-generation.md)) ?

---

## Protocole

### Ce qui est mesuré

| Mesure | Définition | Source |
|--------|------------|--------|
| Chargement | Temps pour charger le modèle en mémoire, lors d'un démarrage à froid | `load_duration` d'Ollama |
| 1er token | Temps entre l'envoi de la requête et le premier token généré (réflexion comprise) | Mesuré côté client |
| Réponse visible | Temps avant le premier token de la réponse elle-même, après la réflexion | Mesuré côté client |
| Total | Durée complète de la requête | Mesuré côté client |
| Lecture | Vitesse de traitement du prompt, en tokens par seconde | `prompt_eval_count` / `prompt_eval_duration` |
| Génération | Vitesse de génération, en tokens par seconde | `eval_count` / `eval_duration` |
| Taille chargée, part GPU | Mémoire occupée par le modèle, et part placée en VRAM | `GET /api/ps` (`size`, `size_vram`) |
| VRAM ajoutée | Mémoire vidéo utilisée en plus après chargement, tous processus | `nvidia-smi` avant et après |
| RAM Ollama | Mémoire résidente des processus `ollama` et `llama-server` | `/proc/<pid>/status` (`VmRSS`) |
| Embeddings | Durée d'un calcul de vecteurs pour 1 texte et pour 32 textes | Mesuré côté client |

### Combinaisons testées

- **Modèle** : celui du projet, `hf.co/atakhadivi/Qwen3.8-2B-Uncensored-GGUF` (1,88 milliard de paramètres, quantifié Q4_K_M, 1,27 Go).
- **Exécution** :
  - `gpu` : placement automatique d'Ollama (le modèle tient entièrement en VRAM) ;
  - `cpu` : option `num_gpu: 0`, aucune couche sur la carte graphique.
- **Fenêtre de contexte** : `num_ctx` à 2048, 4096 et 8192 tokens.
- **Deux prompts** :
  - `court` : une question de culture générale, qui mesure surtout la génération ;
  - `long` : environ 1 500 tokens de texte suivis d'une demande de résumé, qui mesurent surtout la lecture du prompt.
- **Réflexion** : le modèle commence par une phase de réflexion (champ `thinking` d'Ollama).
  Une mesure à part compare la réflexion par défaut (le comportement de SensAI) et la réflexion désactivée (`think: false`).
- **Embeddings** : `nomic-embed-text`, utilisé par la mémoire longue.

Le second modèle installé, `Qwen3.8-27B` (17,7 Go), n'a pas pu être mesuré :
son fichier n'est pas téléchargé, et il dépasse la mémoire de la machine (6 Go de VRAM et 15 Go de RAM).

### Conditions

Pour que les mesures soient comparables :

- **Paramètres fixes** : `temperature` 0 et `seed` 42, `num_predict` 128 pour la vitesse, 1024 pour la mesure de réflexion.
- **Démarrage à froid** : le modèle est déchargé (`keep_alive: 0`) avant chaque combinaison.
  La première requête mesure donc le chargement réel.
- **Chauffe** : une requête non mesurée précède les mesures de chaque prompt.
- **Répétitions** : 3 mesures par prompt et par combinaison. Les tableaux donnent la médiane, puis le minimum et le maximum.
- **Pas de cache** : chaque prompt commence par un identifiant unique.
  Sans cela, Ollama réutiliserait le prompt déjà lu, et la vitesse de lecture serait faussée.
- **Machine** : sur secteur, sans autre calcul lourd en cours. Le serveur Ollama est le seul à utiliser le GPU.

### Reproduire

1. Lancer Ollama : `ollama serve` (ou `./scripts/A1Libi -run` avec Docker).
2. Lancer le benchmark depuis la racine du projet :

   ```bash
   PYTHONPATH=. .venv/bin/python -m benchmark.resources
   ```

3. Le script écrit dans `benchmark/results/` :
   - `<date>_resources.md` : le rapport avec tous les tableaux ;
   - `<date>_resources.csv` : chaque mesure, une ligne par requête ;
   - `<date>_thinking.csv` et `<date>_embeddings.csv` : les mesures de réflexion et d'embeddings.

Options utiles :

| Option | Effet |
|--------|-------|
| `--models m1 m2` | Mesurer d'autres modèles installés |
| `--backends gpu` | Ne mesurer que le GPU |
| `--num-ctx 2048 16384` | Choisir les tailles de contexte |
| `--reps 5` | Changer le nombre de répétitions |
| `--no-thinking` | Ne pas mesurer la réflexion |

Le code est dans [`benchmark/resources.py`](../benchmark/resources.py).
Ses calculs sont testés dans [`test_benchmark_resources.py`](../src/galerelm/unit_tests/test_benchmark_resources.py),
sans Ollama, avec un faux serveur.

---

## Résultats

Mesures du 1er novembre 2026. Rapport complet et données brutes :

- [`benchmark/results/2026-11-01_1945_resources.md`](../benchmark/results/2026-11-01_1945_resources.md) : tous les tableaux ;
- [`2026-11-01_1945_resources.csv`](../benchmark/results/2026-11-01_1945_resources.csv), [`_thinking.csv`](../benchmark/results/2026-11-01_1945_thinking.csv), [`_embeddings.csv`](../benchmark/results/2026-11-01_1945_embeddings.csv) : chaque mesure.

### Machine

| Élément | Valeur |
|---------|--------|
| Processeur | Intel Core i7-12650H, 16 threads (ordinateur portable) |
| Mémoire vive | 15,3 Go |
| Carte graphique | NVIDIA GeForce RTX 4050 Laptop, 6 Go de VRAM, pilote 580.178.04 |
| Système | Linux 7.0.0-38 |
| Ollama | 0.34.4 |
| Modèle | Qwen3.8 2B Uncensored, Q4_K_M, 1,27 Go sur disque |

### Vitesse, modèle chargé

Médiane de 3 mesures. Génération : 128 tokens. Les écarts entre `num_ctx` sont faibles : la ligne donne la plage observée.

| Exécution | Prompt | Lecture (tok/s) | Génération (tok/s) | 1er token | Total |
|-----------|--------|-----------------|--------------------|-----------|-------|
| GPU | court | 1 870 à 1 906 | 115,6 à 116,5 | 0,05 s | 0,97 à 1,05 s |
| GPU | long (1 500 tokens) | 5 277 à 5 537 | 113,3 à 113,9 | 0,36 à 0,37 s | 1,48 à 1,50 s |
| CPU | court | 152 à 182 | 31,3 à 33,1 | 0,31 à 0,37 s | 3,09 à 3,89 s |
| CPU | long (1 500 tokens) | 152 à 180 | 31,2 à 32,5 | 9,8 à 11,6 s | 13,8 à 15,5 s |

### Démarrage à froid

| Exécution | Chargement | 1er token | Première réponse complète |
|-----------|------------|-----------|---------------------------|
| GPU | 1,8 à 3,6 s | 1,9 à 3,7 s | 3,0 à 4,8 s |
| CPU | 1,8 à 3,3 s | 2,1 à 3,6 s | 5,1 à 6,9 s |

### Mémoire

| Exécution | num_ctx | Taille chargée | Part en VRAM | VRAM ajoutée (carte) | RAM des processus Ollama |
|-----------|---------|----------------|--------------|----------------------|--------------------------|
| GPU | 2048 | 1 294 Mo | 100 % | 1 413 Mo | 1 938 Mo |
| GPU | 4096 | 1 320 Mo | 100 % | 1 439 Mo | 1 940 Mo |
| GPU | 8192 | 1 424 Mo | 100 % | 1 543 Mo | 1 994 Mo |
| CPU | 2048 | 1 299 Mo | 0 % | 0 Mo | 2 481 Mo |
| CPU | 4096 | 1 325 Mo | 0 % | 0 Mo | 2 428 Mo |
| CPU | 8192 | 1 433 Mo | 0 % | 0 Mo | 2 056 Mo |

### Réflexion du modèle

Le modèle réfléchit avant de répondre (champ `thinking`). SensAI n'affiche que la réponse :
pendant la réflexion, l'utilisateur ne voit rien.

| Réflexion | Réponse visible après | Tokens de réflexion | Total |
|-----------|-----------------------|---------------------|-------|
| Par défaut (comportement de SensAI) | 0,34 s | 30 | 1,09 s |
| Désactivée (`think: false`) | 0,05 s | 0 | 0,83 s |

### Embeddings (mémoire longue)

| Lot | Durée |
|-----|-------|
| 1 texte | 0,01 s |
| 32 textes | 0,15 s |

### Taille réelle du prompt de SensAI

Mesurée sur une vraie conversation (`prompt_eval_count` d'Ollama), avec la configuration par défaut :

| Situation | Tokens envoyés au modèle |
|-----------|--------------------------|
| Premier message, sans aucun outil | 184 |
| Premier message, avec les 12 outils | 2 275 |
| Avec 10 messages d'historique | environ 2 900 |

---

## Analyse

1. **Sur GPU, la conversation est fluide.**
   - 116 tokens par seconde, c'est bien plus rapide que la lecture humaine.
   - Le premier token arrive en 0,05 seconde, et en 0,36 seconde même avec 1 500 tokens à lire.
   - Le modèle tient entièrement en VRAM : 1,3 à 1,4 Go sur 6 Go.
2. **Sur CPU, la génération reste utilisable, mais la lecture devient le problème.**
   - La génération est 3,6 fois plus lente (32 contre 116 tokens/s), ce qui reste lisible.
   - La lecture du prompt est 10 à 35 fois plus lente (150 à 180 contre 1 900 à 5 500 tokens/s).
   - Or le prompt de SensAI fait 2 275 tokens dès le premier message.
     Sans cache, cela représente environ 13 secondes d'attente avant le premier mot sur CPU.
   - En conversation réelle, Ollama réutilise le début du prompt déjà lu (instructions, outils),
     ce qui réduit cette attente à partir du deuxième message. Ce benchmark désactive volontairement ce cache.
3. **La taille de contexte coûte peu de mémoire sur ce modèle.**
   - De 2048 à 8192 tokens : +130 Mo de VRAM, dont +104 Mo de 4096 à 8192.
   - Aucune perte de vitesse au-delà du bruit de mesure (lecture longue : -5 % à 8192).
4. **Le démarrage à froid coûte 2 à 4 secondes.** Garder le modèle chargé (`keep_alive`) évite ce coût à chaque message.
5. **Les outils représentent 92 % du prompt** (2 091 tokens sur 2 275).
   L'essentiel vient du schéma JSON envoyé à Ollama (environ 1 770 tokens), indispensable à l'appel d'outils.
   La description en double dans le prompt système en coûtait 288 : elle a été réduite aux noms
   (voir [Améliorations mesurées](17-ameliorations-mesurees.md)).
6. **La réflexion ajoute 0,3 seconde** sur cette question, avec 30 tokens.
   Sur une question complexe, elle peut être bien plus longue, et rien ne s'affiche pendant ce temps.
7. **Les embeddings sont négligeables** : 0,15 seconde pour 32 messages. Archiver tous les chats en mémoire longue ne ralentit pas SensAI.

---

## Décisions prises

| Décision | Justification mesurée |
|----------|-----------------------|
| `num_ctx` du profil `chat` passé de 4096 à **8192** | Prompt réel de 2 300 à 2 900 tokens ; +104 Mo de VRAM seulement, pas de perte de vitesse |
| `keep_alive` à **30 minutes** | Un rechargement coûte 2 à 4 s ; le modèle chargé n'occupe que 1,4 Go de VRAM |
| GPU recommandé, CPU en secours | Génération ×3,6 et lecture ×10 à ×35 sur GPU |
| `num_ctx` 2048 pour le guardrail | Il ne lit qu'une question courte ; la fenêtre la plus petite suffit |

Les valeurs sont appliquées dans [Paramètres de génération](15-parametres-generation.md).

### Pistes suivantes, chiffrées

- **Réduire le coût des outils** : fait. La description en double est réduite aux noms, -288 tokens par requête,
  mesuré contre une baseline dans [Améliorations mesurées](17-ameliorations-mesurees.md).
- **Rendre la réflexion configurable** (`think`), et l'afficher pendant qu'elle a lieu.

---

## Limites de ce benchmark

- **Un seul modèle mesuré.** Le 27B n'est pas téléchargé et ne tiendrait pas en mémoire.
  Pour comparer des tailles, installer par exemple un modèle de 7 à 8 milliards de paramètres et le passer à `--models`.
- **3 répétitions** par combinaison : assez pour voir des écarts de ce facteur, pas pour des écarts fins.
- **Ordinateur portable** : la fréquence du processeur varie (température, énergie), ce qui explique une partie du bruit sur CPU.
- **RAM des processus Ollama** : la mesure `VmRSS` compte aussi le fichier du modèle projeté en mémoire.
  Elle surestime donc la mémoire réellement réservée.
- **VRAM ajoutée** : `nvidia-smi` mesure toute la carte. Le chiffre est une différence avant et après chargement.
- **Démarrage à froid** : après le premier chargement, le fichier du modèle est dans le cache disque du système.
  Les chargements suivants sont donc plus rapides qu'un vrai premier lancement après redémarrage.

