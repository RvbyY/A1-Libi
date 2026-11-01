# 18. Évaluation par un LLM juge

Cette page montre comment SensAI note ses propres réponses avec un modèle utilisé comme juge (feature EV1),
et comment ces notes servent à comparer deux versions du système.

[Retour au sommaire](README.md)

---

## Ce que fait le juge

Pour une question, une réponse et des faits de référence, le juge (`HallucinationGrader`) renvoie :

| Champ | Signification |
|-------|---------------|
| `relevance` | De 0 à 5 : la réponse répond-elle à la question ? |
| `coherence` | De 0 à 5 : la réponse est-elle claire et sans contradiction ? |
| `faithfulness` | De 0 à 5 : la réponse est-elle fidèle aux faits de référence ? |
| `grounded` | La réponse est-elle entièrement appuyée par les faits ? |
| `unsupported_claims` | Les affirmations non appuyées, ou contredites par les faits |
| `verified` | Faux si le juge n'a pas pu se prononcer (erreur, réponse illisible) |

Il sert à deux endroits :

1. **Pendant la conversation**, avec `--anti-hallucination` : une réponse non ancrée est régénérée,
   puis signalée à l'utilisateur si elle reste non ancrée ; une réponse que le juge n'a pas pu vérifier est signalée aussi.
   Les scores sont enregistrés dans le journal des échanges (voir [Monitoring](user_stories/EV3-monitoring.md)).
2. **Pour comparer des versions**, avec le script `benchmark/judge.py`, décrit ci-dessous.

---

## Protocole de comparaison

### Le jeu de référence

Fichier : [`benchmark/datasets/judge.yaml`](../benchmark/datasets/judge.yaml).

- 6 cas, chacun avec un **document fictif** (règlement d'une entreprise inventée, fiche d'un produit inventé)
  et une question. Le modèle ne peut pas connaître ces informations par cœur.
- 4 questions ont leur réponse dans le document, 2 non : une réponse fidèle doit alors dire qu'elle ne sait pas.

### Les versions comparées

| Version | Ce que reçoit SensAI |
|---------|----------------------|
| `sans documents` | Seulement la question : le modèle répond avec ses connaissances |
| `avec documents` | Le document est ingéré (feature R1) : ses extraits sont injectés dans le prompt |

Dans les deux cas, **le juge reçoit le document de référence** : il note donc la fidélité de la réponse à la vérité du cas.

### Conditions

- Modèle de SensAI et juge : Qwen3.8 2B (le seul modèle disponible sur la machine).
- Température 0 et graine 42 pour SensAI ; profil `judge` pour le juge (température 0).
- 2 répétitions de chaque cas, soit 12 réponses notées par version.

### Reproduire

```bash
PYTHONPATH=. .venv/bin/python -m benchmark.judge --reps 2
```

Pour comparer deux modèles, ou utiliser un juge plus gros :

```bash
PYTHONPATH=. .venv/bin/python -m benchmark.judge --models modele-a modele-b --judge-model modele-juge
```

---

## Résultats

Mesures du 1er novembre 2026.
Rapport complet, avec chaque réponse : [`benchmark/results/2026-11-01_2059_judge.md`](../benchmark/results/2026-11-01_2059_judge.md).

| Version | Pertinence | Cohérence | Fidélité | Réponses ancrées | Non vérifiées | Affirmations signalées |
|---------|------------|-----------|----------|------------------|---------------|------------------------|
| Sans documents | 3,8 | 4,4 | 3,2 | 40 % | 2 / 12 | 6 |
| Avec documents | 5 | 5 | 5 | 100 % | 0 / 12 | 0 |

- **Les scores distinguent bien les deux versions** : la fidélité passe de 3,2 à 5 sur 5 avec les documents.
- **Les inventions sont signalées.** Sans document, le modèle affirme « Kestrel 3 : 20 minutes d'autonomie, garantie 1 an »
  alors que le document dit 31 heures et 3 ans : le juge met une fidélité de 2 et cite l'affirmation contredite.

---

## Ce que le juge rate

Le juge est le même petit modèle que SensAI. Les mesures montrent ses limites :

- **Il a validé une erreur.** Avec les documents, la réponse « une astreinte de nuit en semaine est payée 120 euros » est notée 5 / 5,
  alors que le document dit 120 euros pour le **week-end** et ne parle pas des nuits en semaine.
- **Il note bien des réponses vides de sens.** Des réponses comme « [Your complete, well-structured response…] » reçoivent 5 / 5.
- **Une première version du prompt du juge donnait 5 / 5 partout** : il recopiait les valeurs d'exemple du JSON demandé.
  Le prompt ne contient plus de valeurs d'exemple, et demande de comparer chaque chiffre aux faits.
- **Quand il ne sait pas répondre proprement**, il produit un JSON illisible : la réponse est alors « non vérifiée » (2 cas sur 12),
  au lieu d'être acceptée comme avant.

Conclusion : les scores du juge 2B sont utiles pour comparer des versions entre elles, pas comme note absolue.
Pour des notes plus fiables, utiliser un modèle plus gros comme juge (`--judge-model`).

---

## Où c'est testé

[`test_judge_eval.py`](../src/galerelm/unit_tests/test_judge_eval.py) vérifie, sans Ollama :

- la lecture des scores, leur limite à 0-5 et la liste des affirmations non appuyées ;
- qu'un juge en erreur ou illisible donne une réponse « non vérifiée » ;
- le signalement à l'utilisateur et l'enregistrement des scores dans le journal ;
- la comparaison de versions par le script et le contenu du rapport.

```bash
.venv/bin/python -m pytest -q src/galerelm/unit_tests/test_judge_eval.py
```
