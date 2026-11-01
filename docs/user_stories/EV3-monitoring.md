# EV3 : Monitoring

[Retour aux user stories](README.md)

**Statut :** Partiel (visualiseur temps réel et logs ; pas encore de tableau de métriques)

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
- [ ] Les métriques sont regroupées dans un tableau de bord (à faire).

**Vérifié par :** `test_chat_response`, `test_executor_reports_each_call_to_observer`.

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

- Pas de tableau de bord historique : les métriques ne sont ni agrégées ni conservées dans la durée.
- Les logs vont dans la console ; il n'y a pas encore de fichier de logs structuré (JSON).
