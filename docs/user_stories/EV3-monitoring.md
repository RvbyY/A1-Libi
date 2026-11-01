# EV3 : Monitoring

[Retour aux user stories](README.md)

**Statut :** Fait

---

## Ce que demande le sujet

- Une journalisation structurée : latence, tokens, prompts.
- Une interface de visualisation des métriques.

## Ce que fait SensAI

- `ChatEngine` émet un événement à chaque étape : guardrail, RAG, prompt, génération, outils, vérification, sauvegarde.
- La webapp affiche ces étapes en direct dans un graphe SVG (`PipelineVisualizer`).
- Chaque réponse d'Ollama garde ses compteurs : tokens générés, durée de génération.
- Chaque appel d'outil est journalisé avec sa durée.

---

## User story 1 : suivre le pipeline en direct

**En tant que** développeur,
**je veux** voir dans la webapp quelle étape du pipeline est en cours et comment elle s'est terminée,
**afin de** comprendre où une réponse a échoué ou ralenti.

### Critères d'acceptation

- [x] Chaque étape passe par les états actif, succès, avertissement ou erreur.
- [x] Le détail de l'étape est affiché (ex. « 2 souvenir(s) trouvé(s) », « Prompt prêt (1834 car.) »).
- [x] Le graphe se met à jour pendant la génération.

**Vérifié par :** `test_pipeline_visualizer_tracks_realtime_events`, `test_prompt_event_reports_real_prompt_size`.

---

## User story 2 : mesurer les appels

**En tant que** développeur,
**je veux** connaître le nombre de tokens et la durée de chaque génération et de chaque outil,
**afin de** repérer ce qui est lent ou coûteux.

### Critères d'acceptation

- [x] `eval_count` et `eval_duration` d'Ollama sont conservés dans chaque réponse.
- [x] Chaque appel d'outil est journalisé avec sa durée en millisecondes.
- [x] Les métriques sont regroupées dans un tableau de bord : onglet Monitoring de la webapp et commande `/stats`.

**Vérifié par :** `test_chat_response`, `test_executor_reports_each_call_to_observer`.

---

## Ce qui a été ajouté pour terminer la feature

- **Journal structuré** : chaque échange écrit une ligne dans la table `interaction_logs` : date, profil, modèle, agent,
  statut (`ok`, `blocked`, `error`, `interrupted`), erreur, latence, premier morceau, tokens lus et générés,
  taille du prompt, souvenirs et extraits injectés, outils appelés et échecs, scores du juge.
  La même ligne part aussi dans le logger `galerelm.engine` au format JSON.
- **Métriques** (`src/galerelm/metrics.py`) : volume, taux d'erreur, latence moyenne, médiane et p95, tokens, outils,
  **jour par jour** (pour voir une dérive) et **par modèle**.
- **Vues** : commande `/stats [jours]` dans le terminal, et onglet « Monitoring » dans la webapp
  (indicateurs, tableau par jour et courbe de latence).
- Une erreur de journalisation ne casse jamais la conversation.

### Tests de la finalisation

```bash
.venv/bin/python -m pytest -q \
  src/galerelm/unit_tests/test_monitoring.py
```

Résultat au 1er novembre 2026 : 9 tests passés, 0 en échec.

### Vérification avec le vrai modèle

Après trois échanges réels, `/stats` affichait : 3 échanges, 0 % d'erreur, latence moyenne 3,13 s (p95 8,22 s), 2 422 tokens lus en moyenne.

---

## Preuves

### Code

- [`src/webapp/visualizer.py`](../../src/webapp/visualizer.py)
- [`src/galerelm/engine.py`](../../src/galerelm/engine.py)
- [`src/tools/registry.py`](../../src/tools/registry.py)
- [`src/galerelm/models/response.py`](../../src/galerelm/models/response.py)

### Tests automatisés

Les tests cités dans les critères d'acceptation se relancent avec :

```bash
.venv/bin/python -m pytest -q \
  src/galerelm/unit_tests/test_graph.py::test_pipeline_visualizer_tracks_realtime_events \
  src/galerelm/unit_tests/test_engine_and_repl.py::test_prompt_event_reports_real_prompt_size \
  src/galerelm/unit_tests/test_chat.py::test_chat_response \
  src/galerelm/unit_tests/test_tool_logs.py::test_executor_reports_each_call_to_observer
```

Résultat au 1er novembre 2026 : 4 tests passés, 0 en échec.

### Démonstration manuelle

1. Lancer la webapp et envoyer un message.
2. Le visualiseur affiche chaque étape du pipeline en direct, avec la taille du prompt.
3. En CLI, chaque appel d'outil est affiché avec sa durée.

---

## Limites

- La question et la réponse sont gardées tronquées à 500 caractères dans le journal.
- Les tokens enregistrés sont ceux de la dernière génération de l'échange (après une relance d'outil, c'est la relance).
