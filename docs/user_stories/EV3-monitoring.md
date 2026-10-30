# 📊 EV3 : Monitoring

[⬅️ Retour aux user stories](README.md)

**Statut :** 🟡 Partiel (visualiseur temps réel et logs ; pas encore de tableau de métriques)

---

## 📋 Ce que demande le sujet

- Une journalisation structurée : latence, tokens, prompts.
- Une interface de visualisation des métriques.

## ⚙️ Ce que fait SensAI

- `ChatEngine` émet un événement à chaque étape : guardrail, RAG, prompt, génération, outils, vérification, sauvegarde.
- La webapp affiche ces étapes en direct dans un graphe SVG (`PipelineVisualizer`).
- Chaque réponse d'Ollama garde ses compteurs : tokens générés, durée de génération.
- Chaque appel d'outil est journalisé avec sa durée.

---

## 👤 User story 1 : suivre le pipeline en direct

**En tant que** développeur,
**je veux** voir dans la webapp quelle étape du pipeline est en cours et comment elle s'est terminée,
**afin de** comprendre où une réponse a échoué ou ralenti.

### ✅ Critères d'acceptation

- [x] Chaque étape passe par les états actif, succès, avertissement ou erreur.
- [x] Le détail de l'étape est affiché (ex. « 2 souvenir(s) trouvé(s) », « Prompt prêt (1834 car.) »).
- [x] Le graphe se met à jour pendant la génération.

**Vérifié par :** `test_pipeline_visualizer_tracks_realtime_events`, `test_prompt_event_reports_real_prompt_size`.

---

## 👤 User story 2 : mesurer les appels

**En tant que** développeur,
**je veux** connaître le nombre de tokens et la durée de chaque génération et de chaque outil,
**afin de** repérer ce qui est lent ou coûteux.

### ✅ Critères d'acceptation

- [x] `eval_count` et `eval_duration` d'Ollama sont conservés dans chaque réponse.
- [x] Chaque appel d'outil est journalisé avec sa durée en millisecondes.
- [ ] Les métriques sont regroupées dans un tableau de bord (à faire).

**Vérifié par :** `test_chat_response`, `test_executor_reports_each_call_to_observer`.

---

## ⚠️ Limites

- Pas de tableau de bord historique : les métriques ne sont ni agrégées ni conservées dans la durée.
- Les logs vont dans la console ; il n'y a pas encore de fichier de logs structuré (JSON).
