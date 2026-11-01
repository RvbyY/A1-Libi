# ✅ Check-list : implémenter un tool

À dérouler pour **chaque** nouveau tool (ou modification d'un tool existant) avant d'ouvrir la PR.
Exemple de référence : [`tasks/complete_task.py`](tasks/complete_task.py).
Architecture détaillée : [docs/12](../../docs/12-architecture-context-tools.md) et [docs/13](../../docs/13-context-tools.md).

---

## 1. Fichier et classe

- [ ] Le fichier est dans le bon sous-dossier (`calendar/`, `communication/`, `memory/`, `tasks/`, ou un nouveau dossier par domaine).
- [ ] La classe hérite de `ToolsInterface` et implémente `name`, `description`, `parameters` et `execute`.
- [ ] Les imports internes sont **relatifs** (`from ..ITools import ToolContext, ToolResult, ToolsInterface`) pour ne pas aggraver l'import circulaire `src.tools` ↔ `src.galerelm`.
- [ ] Le constructeur n'a aucun argument obligatoire, pour que `default_tool_registry()` puisse l'instancier avec `tool_cls()`. Les dépendances optionnelles, comme `session_factory`, ont une valeur par défaut.
- [ ] Un alias est exporté si le projet en utilise un (`CompleteTaskTool = CompleteTask`).

## 2. Définition vue par le LLM

Ces trois propriétés sont envoyées à Ollama (`tools`) **et** résumées dans le prompt système sous forme de signature
(`- nom(param*: a|b, autre: integer) — description`). Le modèle n'a rien d'autre pour décider d'appeler le tool.

- [ ] `name` est unique dans le registre, en `snake_case` et sous forme de verbe ou de domaine (`create_task`, `calendar`). Un doublon écrase silencieusement l'autre tool dans `ToolRegistry`.
- [ ] `description` tient en une phrase et dit **quoi** fait le tool et **quand** l'utiliser. Elle mentionne les effets de bord (envoi, suppression, etc.).
- [ ] `parameters` est un JSON Schema valide : `"type": "object"`, `properties`, `required`.
- [ ] Chaque paramètre a un `type` et une `description` courte. Le format attendu est précisé (ISO 8601, e-mail, ID…).
- [ ] Les valeurs fermées utilisent `enum` (elles apparaissent dans le prompt sous la forme `action*: add|list|cancel`).
- [ ] `required` liste exactement les paramètres sans lesquels l'exécution échoue, ni plus ni moins.
- [ ] **Les noms des paramètres du schéma sont exactement ceux lus dans `execute`.** Une différence (par ex. `file_path` d'un côté, `task_id` de l'autre) rend le tool inutilisable.

## 3. Exécution (`execute`)

- [ ] Chaque argument est validé (présence, type, format, bornes) **avant** toute action. Le LLM peut envoyer n'importe quoi, y compris des chaînes vides ou des types incorrects.
- [ ] La méthode retourne toujours un `ToolResult`, en cas de succès comme d'échec. Les erreurs attendues (`ValueError`, `TypeError`, erreurs réseau ou SMTP) sont capturées et deviennent `ToolResult(False, "...")`.
- [ ] `message` est court et compréhensible par le LLM : il est réinjecté tel quel dans le contexte (`[nom] message`, rôle `tool`) et sert de « fait » au vérificateur anti-hallucination.
- [ ] `data` ne contient que des données sérialisables en JSON (dates en `isoformat()`, pas d'objets SQLAlchemy).
- [ ] Le tool ne fait aucun `print` et n'écrit pas directement sur la sortie : il utilise `logging`.

## 4. Sécurité et isolation

- [ ] Toute donnée lue ou modifiée est filtrée par propriétaire : `context.user_id` ou `context.profile`. Un utilisateur ne doit jamais accéder aux données d'un autre (voir `_get_owned_task`).
- [ ] Aucun secret n'est écrit en dur. Les tokens et hôtes sont lus via `src/config.py` ou `.env`, et la variable est ajoutée à `.env.exemple`.
- [ ] Les chemins de fichiers reçus du LLM sont validés : pas de `..`, ils restent dans un dossier autorisé.
- [ ] Aucun argument n'est passé à un shell, à `eval` ou à une requête SQL brute.
- [ ] **Action critique** (envoi d'un message, suppression, paiement, écriture disque) : la classe déclare `requires_confirmation = True` et l'effet est signalé dans la `description`. `ToolExecutor` demande alors l'accord de l'utilisateur et refuse l'action si personne ne peut confirmer ([A3] Human-in-the-loop).

## 5. Session et base de données

- [ ] Le tool utilise `context.session`, ou son `session_factory` s'il en a un, et lève une erreur claire si aucune session n'est disponible.
- [ ] Il fait `commit()` uniquement après une modification réussie, et ne laisse pas de transaction à moitié appliquée en cas d'erreur.
- [ ] Un nouveau modèle ORM est exporté dans `src/galerelm/models/__init__.py`, sinon la table n'est pas créée.

## 6. Enregistrement

- [ ] La classe est importée et ajoutée à `BUILTIN_TOOLS` et à `__all__` dans [`__init__.py`](__init__.py).
- [ ] Le tool apparaît bien dans le prompt :
  ```bash
  PYTHONPATH=. .venv/bin/python -c "import src.main; from src.tools import default_tool_registry; from src.galerelm.models import PromptBuilder; print(PromptBuilder().with_tools(default_tool_registry()).build().system_content)"
  ```

## 7. Tests (`src/galerelm/unit_tests/test_tools.py`)

- [ ] Cas nominal : arguments valides, `success is True` et `data` attendu.
- [ ] Chaque paramètre requis manquant ou vide renvoie `success is False`.
- [ ] Les types et formats invalides (date, e-mail, enum hors liste) renvoient `success is False`.
- [ ] Isolation : un autre `user_id` ne peut ni lire ni modifier les données.
- [ ] Appel via le pipeline complet : un faux chunk Ollama avec `tool_calls` passe par `SensAI.chat()` et produit un message de rôle `tool` (modèle : `test_chat_engine_executes_tool_calls`).
- [ ] Aucun appel réseau réel : SMTP, Discord, Telegram et HTTP sont mockés.
- [ ] `.venv/bin/python -m pytest -q` passe en entier.

## 8. Test manuel avec le modèle

- [ ] Avec Ollama lancé, une demande en langage naturel déclenche bien le tool (`/payload` permet de voir le prompt envoyé).
- [ ] Une demande hors sujet ne déclenche **pas** le tool.
- [ ] Une demande à laquelle il manque un paramètre requis amène le modèle à demander l'information au lieu de l'inventer.
- [ ] Le résultat du tool est correctement reformulé dans la réponse finale.
- [ ] Le même scénario fonctionne en mode `--anti-hallucination`.

## 9. Documentation

- [ ] Une section est ajoutée dans [docs/13-context-tools.md](../../docs/13-context-tools.md) : rôle, arguments, exemple d'appel et exemple de `ToolResult`.
- [ ] Les limites connues sont ajoutées dans « Limites actuelles » de [docs/12](../../docs/12-architecture-context-tools.md).
- [ ] Deux user stories sont ajoutées dans `USER_STORIES.md` (« En tant que…, je veux…, afin de… »).
