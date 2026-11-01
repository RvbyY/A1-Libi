# 15. Paramètres de génération

Cette page explique les réglages envoyés à Ollama à chaque appel du modèle.

Elle dit où les régler, quelles valeurs sont utilisées, et pourquoi.

[Retour au sommaire](README.md)

---

## Trois profils, un par usage

SensAI appelle le modèle pour trois tâches différentes.

Chaque tâche a son propre **profil** de paramètres.

| Profil | Utilisé par | Ce qu'on attend |
|--------|-------------|-----------------|
| `chat` | La conversation (`ChatEngine`, relance après les outils, graphe anti-hallucination) | Une réponse naturelle et complète |
| `judge` | Le juge anti-hallucination (`HallucinationGrader`) | Un petit JSON, toujours le même pour la même entrée |
| `guardrail` | Le classifieur d'intention (`IntentGuardrail`) | Un petit JSON, toujours le même pour la même entrée |

Les profils sont définis dans [`src/config.py`](../src/config.py) (`DEFAULT_GENERATION`).

La classe [`Options`](../src/galerelm/models/options.py) lit le profil au moment de chaque appel.

---

## Les paramètres

| Paramètre | Rôle | Plage acceptée |
|-----------|------|----------------|
| `temperature` | Dose de hasard. 0 = toujours le mot le plus probable. Plus haut = plus varié. | 0.0 à 2.0 |
| `top_k` | Nombre de mots candidats gardés à chaque étape. | 1 à 1000 |
| `top_p` | Garde les mots les plus probables jusqu'à cette probabilité cumulée. | 0.0 à 1.0 |
| `min_p` | Écarte les mots dont la probabilité est trop faible par rapport au meilleur. | 0.0 à 1.0 |
| `num_ctx` | Taille de la fenêtre de lecture, en tokens : prompt système, historique et réponse. | 256 à 131072 |
| `num_predict` | Nombre maximum de tokens générés. -1 = pas de limite, le modèle s'arrête seul. | -1 à 32768 |
| `seed` | Graine du hasard. Même graine + mêmes paramètres = même réponse. Absente = aléatoire. | 0 à 2147483647, ou `none` |
| `stop` | Textes qui arrêtent la génération. | Liste de chaînes |

Un réglage hors des profils : **`keep_alive`**.

- C'est la durée pendant laquelle Ollama garde le modèle en mémoire après un appel.
- Valeur : une durée (`"30m"`, `"1h"`) ou `-1` pour toujours.
- Il se règle dans `ollama.keep_alive`, avec `--keep-alive` ou la variable `OLLAMA_KEEP_ALIVE`.

---

## Les valeurs par défaut, et pourquoi

| Paramètre | `chat` | `judge` | `guardrail` |
|-----------|--------|---------|-------------|
| `temperature` | 0.7 | 0.0 | 0.0 |
| `top_k` | 40 | 1 | 1 |
| `top_p` | 0.9 | 1.0 | 1.0 |
| `min_p` | 0.05 | 0.0 | 0.0 |
| `num_ctx` | 8192 | 4096 | 2048 |
| `num_predict` | -1 | 160 | 128 |
| `seed` | aléatoire | aléatoire | aléatoire |
| `stop` | aucun | aucun | aucun |
| `keep_alive` (commun) | 30m | 30m | 30m |

### Profil `chat`

- **`temperature` 0.7, `top_k` 40, `top_p` 0.9** : un peu de variété, sans réponses incohérentes.
  Ce sont des valeurs courantes, proches des réglages par défaut d'Ollama.
- **`min_p` 0.05** : écarte les mots très improbables, qui produisent des fautes ou des mots inventés.
- **`num_ctx` 8192** : choisi d'après le [benchmark](16-benchmark-ressources.md).
  - Le prompt réel de SensAI fait déjà environ 2 300 tokens au premier message, dont environ 2 100 pour les 12 outils,
    et environ 2 900 tokens avec 10 messages d'historique.
  - À 4096, il ne restait qu'environ 1 200 tokens pour la réponse, les souvenirs et un message un peu long.
    Au-delà, Ollama coupe le début du prompt sans prévenir.
  - Passer de 4096 à 8192 coûte 104 Mo de VRAM (1 320 à 1 424 Mo), sans perte de vitesse mesurable.
- **`num_predict` -1** : la réponse n'est jamais coupée au milieu. Le modèle s'arrête à la fin de sa réponse.
- **`seed` aléatoire** : deux questions identiques peuvent recevoir deux formulations différentes.
  Pour une démo ou un test reproductible, fixer une graine : `--seed 42`.

### Profils `judge` et `guardrail`

- **`temperature` 0 et `top_k` 1** : le modèle choisit toujours le mot le plus probable.
  Le même texte reçoit donc toujours le même verdict, ce qu'on attend d'un juge ou d'un filtre.
- **`num_predict` 160 et 128** : la réponse attendue est un petit JSON.
  La limite évite qu'un modèle qui déraille génère des centaines de tokens pour rien.
- **`num_ctx` 2048 pour `guardrail`** : il ne lit qu'une question courte. Une fenêtre plus petite charge moins de mémoire.

### `keep_alive` 30m

- Un modèle déchargé doit être rechargé au message suivant, ce qui coûte plusieurs secondes.
- 30 minutes couvrent une session de travail, puis libèrent la mémoire vidéo.
- `-1` garde le modèle chargé en permanence.

Mesures qui justifient `num_ctx` et `keep_alive` : [Benchmark des ressources locales](16-benchmark-ressources.md).
- Un démarrage à froid coûte 1,8 à 3,6 secondes avant le premier token, contre 0,05 seconde modèle chargé.
- Le modèle chargé occupe 1,3 à 1,4 Go de VRAM : 30 minutes de maintien est un compromis raisonnable sur une carte de 6 Go.

---

## Où les régler

Ordre de priorité, du plus fort au plus faible :

1. **La commande `/params`**, pendant une session (non sauvegardée).
2. **Les options CLI**, au lancement (profil `chat` uniquement).
3. **Le fichier `config.yaml`**, pour tous les profils.
4. **Les valeurs par défaut** de `src/config.py`.

### Dans `config.yaml`

Seuls les paramètres à changer sont nécessaires. Les autres gardent leur valeur par défaut.

```yaml
ollama:
  keep_alive: "1h"

generation:
  chat:
    temperature: 0.3
    num_ctx: 8192
    seed: 42
  judge:
    num_predict: 200
```

Un exemple complet est dans [`config.example.yaml`](../config.example.yaml).

### En ligne de commande

```bash
PYTHONPATH=. .venv/bin/python src/main.py --temperature 0.3 --num-ctx 8192 --seed 42 --keep-alive 1h
```

Options disponibles : `--temperature`, `--top-k`, `--top-p`, `--min-p`, `--num-ctx`, `--num-predict`,
`--seed`, `--keep-alive`. La liste complète s'affiche avec `--help`.

### Pendant une session : `/params`

| Commande | Effet |
|----------|-------|
| `/params` | Affiche le tableau des trois profils et le `keep_alive` |
| `/params temperature 0.2` | Change un paramètre du profil `chat` |
| `/params judge.num_predict 200` | Change un paramètre d'un autre profil |
| `/params seed none` | Revient à une graine aléatoire |
| `/params stop ###,FIN` | Définit plusieurs textes d'arrêt, séparés par des virgules |
| `/params reset` | Revient aux valeurs du démarrage (config.yaml + options CLI) |

Le changement s'applique dès l'appel suivant, pour la conversation, le juge et le guardrail.

---

## Les erreurs sont refusées

Une valeur invalide est refusée avec un message qui dit quoi corriger.

| Entrée | Message |
|--------|---------|
| `temperature: 3` | `'temperature' doit être entre 0.0 et 2.0 (reçu : 3.0).` |
| `top_k: 2.5` | `valeur invalide '2.5' pour 'top_k' (attendu : int).` |
| `temprature: 0.2` | `paramètre de génération inconnu 'temprature'` avec la liste des paramètres connus |
| `generation.writer` | `profil de génération inconnu 'writer'` |

Au lancement, une erreur dans `config.yaml` ou dans une option CLI arrête SensAI avec le code de sortie 2.

---

## Vérifier ce qui est envoyé

La commande `/payload` affiche la requête envoyée à Ollama.

Le bloc `options` contient les paramètres du profil `chat`, et `keep_alive` la durée de maintien.

Une graine aléatoire et une liste `stop` vide ne sont pas envoyées : Ollama applique alors son propre comportement.

---

## Ce qui a été corrigé

Avant cette version :

- les valeurs étaient écrites en dur dans le code, et **contradictoires** :
  `Options()` utilisait `temperature` 0.7, `num_ctx` 4096 et `num_predict` 512,
  mais `Options.from_format()` utilisait 0.8, 2048 et 128 ;
- **aucun paramètre n'était réglable** sans modifier le code ;
- `num_predict` 512 **coupait** les réponses longues ;
- la graine était **fixée à 0** sans que ce soit documenté ;
- des textes d'arrêt arbitraires (`"\nuser:"`, `"</s>"`) pouvaient couper une réponse ;
- `keep_alive` valait `"2m"` en dur, alors que l'ancien script de lancement préchargeait le modèle pour toujours ;
- le juge et le guardrail avaient leurs propres valeurs écrites en dur.

Toutes ces valeurs viennent maintenant d'un seul endroit, la config, et sont validées.

---

## Limites

- Les options CLI ne règlent que le profil `chat`. Pour `judge` et `guardrail`, utiliser `config.yaml` ou `/params`.
- Les changements faits avec `/params` ne sont pas sauvegardés : ils durent jusqu'à la fin de la session.
- Chaque chat garde encore une ligne `Options` en base, créée à sa création, qui n'est pas utilisée pour la génération.

---

## Où c'est testé

[`test_generation_params.py`](../src/galerelm/unit_tests/test_generation_params.py) vérifie :

- la lecture de la section `generation` du YAML et chaque message d'erreur ;
- la priorité CLI > YAML > valeurs par défaut ;
- les options réellement envoyées par la conversation, le juge et le guardrail ;
- la prise en compte immédiate d'un changement fait avec `/params`, et `/params reset`.

```bash
.venv/bin/python -m pytest -q src/galerelm/unit_tests/test_generation_params.py
```
