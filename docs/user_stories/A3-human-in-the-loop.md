# A3 : Human-in-the-loop

[Retour aux user stories](README.md)

**Statut :** Fait

---

## Ce que demande le sujet

- Suspendre l'exécution.
- Demander une confirmation explicite avant toute action critique.

## Ce que fait SensAI

- Un tool déclare `requires_confirmation = True` s'il a un effet de bord.
- C'est le cas de `email`, `discord`, `telegram`, `notification` et `clear_session`.
- Avant de les exécuter, `ToolExecutor` demande l'accord de l'utilisateur.
- Sans accord, l'action est annulée et le modèle en est informé.

---

## User story 1 : valider avant un envoi

**En tant qu'** utilisateur,
**je veux** que l'assistant me demande mon accord avant d'envoyer un email ou un message,
**afin qu'** aucun message ne parte sans ma décision.

### Critères d'acceptation

- [x] Le terminal affiche l'outil et ses arguments, puis `Autoriser ? [o/N]`.
- [x] Seuls `o`, `oui`, `y` et `yes` autorisent l'action.
- [x] Entrée vide, `n` ou `Ctrl+D` annulent.
- [x] La règle s'applique aussi en mode `--anti-hallucination`.

**Vérifié par :** `test_repl_confirmation_prompt`, `test_chat_sends_once_confirmed`,
`test_anti_hallucination_workflow_also_requires_confirmation`.

---

## User story 2 : refuser sans casser la conversation

**En tant qu'** utilisateur,
**je veux** qu'une action refusée soit annulée et signalée à l'assistant,
**afin qu'il** me réponde en conséquence au lieu de prétendre l'avoir faite.

### Critères d'acceptation

- [x] Une action refusée n'est jamais exécutée.
- [x] Le modèle reçoit « Action '…' annulée : l'utilisateur ne l'a pas confirmée. ».
- [x] Sans moyen de confirmer (tâche planifiée, erreur de l'invite), l'action est refusée par défaut.
- [x] Dans la webapp, l'action est mise en attente et décrite ; elle n'est exécutée qu'après `/confirmer` (abandon : `/annuler`).
- [x] Les outils sans effet de bord (agenda en lecture, recherche mémoire…) s'exécutent sans question.

**Vérifié par :** `test_sensitive_tool_is_refused_without_explicit_approval`,
`test_chat_does_not_send_without_confirmation_callback`, `test_safe_tool_runs_without_confirmation`,
`test_webapp_sensitive_action_waits_for_confirmation`, `test_webapp_pending_action_can_be_cancelled`.

---

## Preuves

### Code

- [`src/tools/ITools.py`](../../src/tools/ITools.py)
- [`src/tools/registry.py`](../../src/tools/registry.py)
- [`src/repl.py`](../../src/repl.py)

### Tests automatisés

Les tests cités dans les critères d'acceptation se relancent avec :

```bash
.venv/bin/python -m pytest -q \
  src/galerelm/unit_tests/test_tool_confirmation.py::test_repl_confirmation_prompt \
  src/galerelm/unit_tests/test_tool_confirmation.py::test_chat_sends_once_confirmed \
  src/galerelm/unit_tests/test_tool_confirmation.py::test_anti_hallucination_workflow_also_requires_confirmation \
  src/galerelm/unit_tests/test_tool_confirmation.py::test_sensitive_tool_is_refused_without_explicit_approval \
  src/galerelm/unit_tests/test_tool_confirmation.py::test_chat_does_not_send_without_confirmation_callback \
  src/galerelm/unit_tests/test_tool_confirmation.py::test_safe_tool_runs_without_confirmation
```

Résultat au 1er novembre 2026 : 14 tests passés, 0 en échec.

### Démonstration manuelle

1. Lancer le chat et écrire « Envoie un email à bob@example.com pour dire bonjour ».
2. La CLI affiche l'outil `email`, ses arguments et `Autoriser ? [o/N]`.
3. Appuyer sur Entrée : l'action est annulée et l'assistant le signale.

---

## Limites

- Les outils des serveurs MCP demandent aussi une confirmation par défaut (`confirm: true`), réglable par serveur.
- La confirmation porte sur l'appel d'outil : elle n'empêche pas le modèle d'affirmer à tort qu'il a agi sans appeler d'outil
  (voir [Améliorations mesurées](../17-ameliorations-mesurees.md)).
