# EV1 : Évaluation automatique (anti-hallucination)

[Retour aux user stories](README.md)

**Statut :** Partiel (détection d'hallucinations faite ; note de cohérence et validation des sources à faire)

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

## Ce qu'il reste à faire

Objectif : produire des **scores** comparables entre versions, en plus de la détection d'hallucinations.

1. **Enrichir le juge.**
   - Dans `HALLUCINATION_GRADER_TEMPLATE` (`src/galerelm/models/prompt.py`), demander en JSON :
     `relevance`, `coherence` et `faithfulness` (de 0 à 5), plus la liste `unsupported_claims`.
   - Ajouter ces champs à `HallucinationGrade` (`src/galerelm/graph.py`).
2. **Ne plus accepter en silence.**
   - Aujourd'hui, un juge en erreur ou un JSON illisible valide la réponse.
   - Marquer plutôt la réponse « non vérifiée » et l'afficher comme telle.
3. **Signaler les affirmations douteuses.**
   - Afficher les `unsupported_claims` sous la réponse quand la limite de régénérations est atteinte.
4. **Conserver les scores.**
   - Ajouter une table `EvaluationResult` : date, modèle, prompt, question, réponse, scores.
5. **Comparer des versions.**
   - Créer un jeu de questions de référence (`eval/dataset.jsonl`).
   - Créer un script `python -m src.evaluation run --model <modèle>` qui rejoue le jeu et affiche les scores moyens.
   - Deux exécutions (deux modèles, ou deux prompts) donnent un tableau comparatif.
6. **Tester.**
   - Analyse des scores, cas « non vérifié », calcul des moyennes avec un faux juge.

**Quand le considérer comme fait :** le script produit un rapport de scores pour deux modèles,
et une réponse inventée est signalée à l'utilisateur.

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

- Pas encore de note de cohérence ni de validation des sources.
- Si le juge plante ou renvoie un JSON illisible, la réponse est acceptée sans avertissement.
- Le même modèle génère et juge : un petit modèle détecte peu d'erreurs.
- Dans ce mode, la réponse s'affiche d'un bloc, sans streaming.
