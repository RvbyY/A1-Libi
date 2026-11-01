# EV1 : Évaluation automatique (anti-hallucination)

[Retour aux user stories](README.md)

**Statut :** Fait

---

## Ce que demande le sujet

- Un LLM utilisé comme juge.
- Noter la cohérence, détecter les hallucinations et valider les sources.

## Ce que fait SensAI

- `HallucinationGrader` compare la réponse aux faits connus : souvenirs RAG et résultats d'outils.
- Il répond en JSON : `{"grounded": true/false, "critique": "…"}`.
- `AntiHallucinationWorkflow` est un graphe en pur Python : `retrieve → generate → tools → generate → grade`.
- Si la réponse n'est pas fondée, elle est régénérée avec la critique, jusqu'à `--max-retries` fois.

---

## User story 1 : des réponses vérifiées

**En tant qu'** utilisateur,
**je veux** activer une vérification des réponses avec `--anti-hallucination`,
**afin de** ne pas recevoir d'informations inventées.

### Critères d'acceptation

- [x] `--anti-hallucination` active le graphe ; il est désactivé par défaut.
- [x] Une réponse jugée non fondée est régénérée, avec la critique ajoutée au prompt.
- [x] `--max-retries N` limite le nombre de régénérations (2 par défaut).
- [x] Dans la webapp, une case à cocher active le même mode.

**Vérifié par :** `test_anti_hallucination_flag_enables_workflow`, `test_max_retries_is_forwarded`,
`test_anti_hallucination_workflow_regenerates_on_hallucination`.

---

## User story 2 : un juge qui connaît les faits

**En tant qu'** utilisateur,
**je veux** que le juge vérifie la réponse à partir de mes souvenirs et des résultats des outils,
**afin que** la vérification porte sur des faits réels et pas sur l'avis du modèle.

### Critères d'acceptation

- [x] Les souvenirs RAG et les sorties d'outils sont transmis au juge comme faits de référence.
- [x] Le juge évalue la réponse finale, rédigée après les outils.
- [x] Une régénération ne relance jamais les outils (pas de double envoi d'email).

**Vérifié par :** `test_hallucination_grader_detects_ungrounded_claim`,
`test_workflow_reprompts_after_tools_and_grades_final_answer`, `test_workflow_regeneration_never_reruns_tools`.

---

## Ce qui a été ajouté pour terminer la feature

- **Scores du juge** : pertinence, cohérence et fidélité aux sources (0 à 5), plus la liste des affirmations non appuyées.
- **Signalement à l'utilisateur** : en mode `--anti-hallucination`, une réponse non ancrée est suivie de
  « [Vérification] Affirmations non appuyées par les sources : … ».
- **Plus d'acceptation silencieuse** : si le juge plante ou répond un JSON illisible, la réponse est marquée
  « n'a pas pu être vérifiée » au lieu d'être présentée comme vérifiée.
- **Scores conservés** dans le journal des échanges (`interaction_logs`, EV3) pour suivre leur évolution.
- **Comparaison de versions** : `python -m benchmark.judge` note les réponses de plusieurs versions
  (avec ou sans documents, plusieurs modèles, `--judge-model`) sur un jeu de référence ; voir [Évaluation par le juge](../18-evaluation-juge.md).
- Le prompt du juge ne contient plus de valeurs d'exemple : le juge 2B les recopiait (5/5 partout).

### Tests de la finalisation

```bash
.venv/bin/python -m pytest -q \
  src/galerelm/unit_tests/test_judge_eval.py
```

Résultat au 1er novembre 2026 : 8 tests passés, 0 en échec.

### Vérification avec le vrai modèle

Avec le vrai modèle, sans documents : fidélité 3,2 / 5, 40 % de réponses ancrées, 6 affirmations signalées ; avec documents : 5 / 5, 100 %, aucune affirmation signalée.

---

## Preuves

### Code

- [`src/galerelm/graph.py`](../../src/galerelm/graph.py)
- [`src/galerelm/engine.py`](../../src/galerelm/engine.py)
- [`src/main.py`](../../src/main.py)

### Tests automatisés

Les tests cités dans les critères d'acceptation se relancent avec :

```bash
.venv/bin/python -m pytest -q \
  src/galerelm/unit_tests/test_config_cli.py::test_anti_hallucination_flag_enables_workflow \
  src/galerelm/unit_tests/test_config_cli.py::test_max_retries_is_forwarded \
  src/galerelm/unit_tests/test_graph.py::test_anti_hallucination_workflow_regenerates_on_hallucination \
  src/galerelm/unit_tests/test_graph.py::test_hallucination_grader_detects_ungrounded_claim \
  src/galerelm/unit_tests/test_tool_followup.py::test_workflow_reprompts_after_tools_and_grades_final_answer \
  src/galerelm/unit_tests/test_tool_followup.py::test_workflow_regeneration_never_reruns_tools
```

Résultat au 1er novembre 2026 : 6 tests passés, 0 en échec.

### Démonstration manuelle

1. Lancer `PYTHONPATH=. .venv/bin/python src/main.py --anti-hallucination --max-retries 2`.
2. Dans la webapp, cocher la case anti-hallucination : le visualiseur montre les étapes generate, grade et éventuellement une régénération.

---

## Limites

- Le juge est le modèle 2B : il détecte les erreurs grossières, mais reste indulgent et produit parfois un JSON illisible
  (réponse alors « non vérifiée »). Un juge plus gros se choisit avec `--judge-model`.
- Les scores du juge ne sont pas calibrés sur des notes humaines.
