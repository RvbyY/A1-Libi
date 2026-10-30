# 🛠️ T1 : Appel d'outils (function calling)

[⬅️ Retour aux user stories](README.md)

**Statut :** ✅ Fait (appel de fonctions natif d'Ollama, pas le protocole MCP lui-même)

---

## 📋 Ce que demande le sujet

- L'agent émet des requêtes structurées pour appeler des fonctions externes.
- Il intègre les résultats retournés.

## ⚙️ Ce que fait SensAI

- 12 tools : agenda, email, Discord, Telegram, notification, mémoire (3), tâches (3) et `tools_selftest`.
- Les tools sont envoyés à Ollama (champ `tools`) et résumés dans le prompt système.
- Les `tool_calls` du modèle sont exécutés, puis le modèle est relancé avec leurs résultats.
- Chaque appel est affiché dans la CLI : nom, arguments, ✓/✗, durée.

---

## 👤 User story 1 : faire agir l'assistant

**En tant qu'** utilisateur,
**je veux** demander en langage naturel une action comme « ajoute une réunion demain à 10h »,
**afin que** l'assistant appelle le bon outil et me confirme le résultat.

### ✅ Critères d'acceptation

- [x] Les tools sont listés dans le prompt avec leurs paramètres obligatoires (`*`) et leurs valeurs possibles.
- [x] Un `tool_call` du modèle exécute l'outil correspondant, et le résultat est ajouté à l'historique (rôle `tool`).
- [x] Le modèle est relancé avec ce résultat pour formuler sa réponse finale.
- [x] Le nombre de relances est limité (`max_tool_rounds`, 3 par défaut).

**Vérifié par :** `test_chat_engine_executes_tool_calls`, `test_model_is_reprompted_with_tool_results`,
`test_tool_rounds_are_bounded`, `test_with_tools_lists_signature_with_required_enum_and_types`.

---

## 👤 User story 2 : voir ce que fait l'assistant

**En tant qu'** utilisateur du terminal,
**je veux** voir chaque outil appelé avec ses arguments, son statut et sa durée,
**afin de** savoir exactement quelles actions ont été faites en mon nom.

### ✅ Critères d'acceptation

- [x] Une ligne par appel : `⚙ tool nom(arg='…') ✓ message (12 ms)`.
- [x] Les valeurs trop longues sont tronquées, et un message sur plusieurs lignes reste sur une seule ligne.
- [x] Chaque appel est aussi journalisé par le logger `sensai.tools`.

**Vérifié par :** `test_repl_prints_tool_calls_with_status_and_duration`, `test_repl_keeps_each_tool_call_on_one_line`,
`test_executor_reports_each_call_to_observer`.

---

## 👤 User story 3 : tester que les outils marchent

**En tant que** développeur,
**je veux** demander à l'assistant de « tester les outils » et voir `tools_selftest` me renvoyer mon message,
**afin de** vérifier en une phrase toute la chaîne d'appel d'outils.

### ✅ Critères d'acceptation

- [x] `tools_selftest` renvoie le message reçu, éventuellement répété (`repeat`).
- [x] `mode: fail` simule une erreur, affichée en ✗ sans faire planter la session.
- [x] Les arguments invalides sont refusés avec un message lisible.

**Vérifié par :** `test_selftest_through_full_pipeline`, `test_selftest_fail_mode_simulates_an_error`,
`test_selftest_rejects_invalid_arguments`.

---

## ⚠️ Limites

- Ce n'est pas un serveur ou un client MCP : les outils sont des classes Python appelées via le function calling d'Ollama.
- Un petit modèle (2B) appelle parfois mal les outils, ou invente un résultat au lieu de les appeler.
- `send_task_file` : le test attend `file_path` alors que l'outil attend `task_id` (test en échec).
