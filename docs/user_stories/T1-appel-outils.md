# T1 : Appel d'outils (function calling)

[Retour aux user stories](README.md)

**Statut :** Fait, avec une limite (l'appel d'outils fonctionne de bout en bout, mais SensAI n'a pas de client MCP pour brancher un outil MCP existant)

---

## Ce que demande le sujet

- L'agent émet des requêtes structurées pour appeler des fonctions externes.
- Il intègre les résultats retournés.

## Ce que fait SensAI

- 12 tools : agenda, email, Discord, Telegram, notification, mémoire (3), tâches (3) et `tools_selftest`.
- Les tools sont envoyés à Ollama (champ `tools`) et résumés dans le prompt système.
- Les `tool_calls` du modèle sont exécutés, puis le modèle est relancé avec leurs résultats.
- Chaque appel est affiché dans la CLI : nom, arguments, succès ou échec, durée.

---

## User story 1 : faire agir l'assistant

**En tant qu'** utilisateur,
**je veux** demander en langage naturel une action comme « ajoute une réunion demain à 10h »,
**afin que** l'assistant appelle le bon outil et me confirme le résultat.

### Critères d'acceptation

- [x] Les tools sont listés dans le prompt avec leurs paramètres obligatoires (`*`) et leurs valeurs possibles.
- [x] Un `tool_call` du modèle exécute l'outil correspondant, et le résultat est ajouté à l'historique (rôle `tool`).
- [x] Le modèle est relancé avec ce résultat pour formuler sa réponse finale.
- [x] Le nombre de relances est limité (`max_tool_rounds`, 3 par défaut).

**Vérifié par :** `test_chat_engine_executes_tool_calls`, `test_model_is_reprompted_with_tool_results`,
`test_tool_rounds_are_bounded`, `test_with_tools_lists_signature_with_required_enum_and_types`.

---

## User story 2 : voir ce que fait l'assistant

**En tant qu'** utilisateur du terminal,
**je veux** voir chaque outil appelé avec ses arguments, son statut et sa durée,
**afin de** savoir exactement quelles actions ont été faites en mon nom.

### Critères d'acceptation

- [x] Une ligne par appel : nom de l'outil, arguments, succès ou échec, message et durée en millisecondes.
- [x] Les valeurs trop longues sont tronquées, et un message sur plusieurs lignes reste sur une seule ligne.
- [x] Chaque appel est aussi journalisé par le logger `sensai.tools`.

**Vérifié par :** `test_repl_prints_tool_calls_with_status_and_duration`, `test_repl_keeps_each_tool_call_on_one_line`,
`test_executor_reports_each_call_to_observer`.

---

## User story 3 : tester que les outils marchent

**En tant que** développeur,
**je veux** demander à l'assistant de « tester les outils » et voir `tools_selftest` me renvoyer mon message,
**afin de** vérifier en une phrase toute la chaîne d'appel d'outils.

### Critères d'acceptation

- [x] `tools_selftest` renvoie le message reçu, éventuellement répété (`repeat`).
- [x] `mode: fail` simule une erreur, affichée comme un échec sans faire planter la session.
- [x] Les arguments invalides sont refusés avec un message lisible.

**Vérifié par :** `test_selftest_through_full_pipeline`, `test_selftest_fail_mode_simulates_an_error`,
`test_selftest_rejects_invalid_arguments`.

---

## Ce qu'il reste à faire

Objectif : parler le **protocole MCP**, pour utiliser un outil MCP existant et exposer nos propres outils en MCP.
La checklist précise que la feature sera testée avec un outil MCP existant **et** avec le nôtre.

1. **Client MCP.**
   - Créer `src/tools/mcp/client.py` : JSON-RPC 2.0 sur l'entrée et la sortie standard d'un sous-processus.
   - Implémenter `initialize`, `tools/list` et `tools/call`.
2. **Adapter les outils distants.**
   - Créer `McpTool(ToolsInterface)` : le nom, la description et l'`inputSchema` de l'outil MCP
     deviennent `name`, `description` et `parameters`.
   - `execute` appelle `tools/call` et renvoie un `ToolResult`.
   - Laisser choisir `requires_confirmation` par serveur.
3. **Configurer les serveurs.**
   - Ajouter une section `mcp_servers` dans `config.yaml` : commande et arguments de chaque serveur.
   - Au démarrage, lister leurs outils et les ajouter au `ToolRegistry`.
4. **Notre propre serveur MCP.**
   - Créer `src/tools/mcp/server.py`, qui expose nos tools (au moins `tools_selftest`) en MCP.
5. **Tester.**
   - Un faux serveur MCP (petit script Python) : découverte des outils, appel, erreur, arrêt du sous-processus.
6. **Démontrer.**
   - Brancher un serveur MCP public (par exemple le serveur « filesystem » de référence), puis le nôtre.

**Quand la limite sera levée :** un outil d'un serveur MCP existant apparaît dans le prompt
et s'exécute depuis le chat, comme nos propres outils.

---

## Preuves

### Code

- [`src/tools/registry.py`](../../src/tools/registry.py)
- [`src/tools/__init__.py`](../../src/tools/__init__.py)
- [`src/galerelm/engine.py`](../../src/galerelm/engine.py)
- [`src/galerelm/models/prompt.py`](../../src/galerelm/models/prompt.py)
- [`src/tools/diagnostic/selftest_tool.py`](../../src/tools/diagnostic/selftest_tool.py)

### Tests automatisés

Les tests cités dans les critères d'acceptation se relancent avec :

```bash
.venv/bin/python -m pytest -q \
  src/galerelm/unit_tests/test_engine_and_repl.py::test_chat_engine_executes_tool_calls \
  src/galerelm/unit_tests/test_tool_followup.py::test_model_is_reprompted_with_tool_results \
  src/galerelm/unit_tests/test_tool_followup.py::test_tool_rounds_are_bounded \
  src/galerelm/unit_tests/test_prompt.py::test_with_tools_lists_signature_with_required_enum_and_types \
  src/galerelm/unit_tests/test_tool_logs.py::test_repl_prints_tool_calls_with_status_and_duration \
  src/galerelm/unit_tests/test_tool_logs.py::test_repl_keeps_each_tool_call_on_one_line \
  src/galerelm/unit_tests/test_tool_logs.py::test_executor_reports_each_call_to_observer \
  src/galerelm/unit_tests/test_tools.py::test_selftest_through_full_pipeline \
  src/galerelm/unit_tests/test_tools.py::test_selftest_fail_mode_simulates_an_error \
  src/galerelm/unit_tests/test_tools.py::test_selftest_rejects_invalid_arguments
```

Résultat au 1er novembre 2026 : 21 tests passés, 0 en échec.

### Démonstration manuelle

1. Lancer le chat et écrire « Teste les outils avec le message ping ».
2. La CLI affiche une ligne d'appel pour `tools_selftest`, avec le statut et la durée.
3. La réponse finale reprend le résultat de l'outil.
4. Écrire « Teste les outils en mode fail avec le message ping » : l'appel est affiché comme un échec et la session continue.

---

## Limites

- Ce n'est pas un serveur ou un client MCP : les outils sont des classes Python appelées via le function calling d'Ollama.
- Un petit modèle (2B) appelle parfois mal les outils, ou invente un résultat au lieu de les appeler.
- `send_task_file` : le test attend `file_path` alors que l'outil attend `task_id` (test en échec).
