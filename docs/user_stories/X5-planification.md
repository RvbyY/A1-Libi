# ⏰ X5 : Planification de tâches

[⬅️ Retour aux user stories](README.md)

**Statut :** 🟡 Partiel (les tâches sont créées et enregistrées, mais le `TaskRunner` n'est jamais démarré)

Fiche technique détaillée : [Scheduled AI Tasks](../features/scheduled-tasks.md).

---

## 📋 Ce que demande le sujet

- Exécuter en autonomie des tâches récurrentes à intervalles réguliers (ex. rapports quotidiens).

## ⚙️ Ce que fait SensAI

- `/schedule` crée une tâche : `at HH:MM`, `in <durée>`, `daily HH:MM` ou `weekly <jour> HH:MM`.
- Le modèle peut aussi créer, terminer ou exporter une tâche avec les tools `create_task`, `complete_task`, `send_task_file`.
- Les tâches sont enregistrées en base (`ScheduledTask`).
- `TaskRunner` exécute les tâches dues avec le même moteur de chat, puis reprogramme les tâches récurrentes.

---

## 👤 User story 1 : programmer un rappel

**En tant qu'** utilisateur qui apprend le japonais,
**je veux** taper `/schedule in 30m révise tes kanji`,
**afin que** l'assistant me le rappelle au bon moment.

### ✅ Critères d'acceptation

- [x] Les formats `at`, `in` (`10s`, `30m`, `2h`, `1d`), `daily` et `weekly` sont reconnus.
- [x] Un format invalide affiche l'usage attendu.
- [x] La tâche est enregistrée en base avec son heure d'exécution.
- [ ] La tâche s'exécute à l'heure prévue (le `TaskRunner` n'est pas encore lancé par la CLI ni la webapp).

**Vérifié par :** `test_schedule_parser_modes_and_reschedule`, `test_create_scheduled_task`.

---

## 👤 User story 2 : un rapport chaque jour

**En tant qu'** utilisateur,
**je veux** programmer `/schedule daily 18:00 résume mes progrès`,
**afin de** recevoir un résumé chaque soir sans le redemander.

### ✅ Critères d'acceptation

- [x] Une tâche `daily` ou `weekly` garde sa récurrence.
- [x] Seules les tâches passées et en attente sont considérées comme dues.
- [x] Une tâche peut être terminée ou annulée.
- [x] Après exécution, une tâche récurrente est reprogrammée à la prochaine échéance.

**Vérifié par :** `test_get_due_tasks_returns_past_pending_tasks`, `test_get_due_tasks_ignores_future_tasks`,
`test_mark_completed`, `test_cancel_task`.

---

## ⚠️ Limites

- `TaskRunner.run_forever()` n'est appelé nulle part : il faut le démarrer dans un thread au lancement.
- Le résultat d'une tâche est seulement affiché dans le terminal (`print`) : il n'est pas enregistré dans un chat.
