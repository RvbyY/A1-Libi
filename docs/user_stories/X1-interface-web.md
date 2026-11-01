# X1 : Interface web

[Retour aux user stories](README.md)

**Statut :** Fait, avec une limite (pas de changement d'agent ni d'affichage des tokens consommés)

---

## Ce que demande le sujet

- Un frontend web découplé, qui repose sur le même backend que la CLI.

## Ce que fait SensAI

- Une application **Gradio** (`src/webapp/`), lancée avec `./script/frontend.sh`.
- Elle passe par `SensAIWrapper`, la même couche que la CLI : mêmes profils, mêmes chats, même base.
- Une page de connexion (email, nom, instructions), une page de chat et une barre latérale des conversations.
- Des cases à cocher activent le guardrail et l'anti-hallucination, avec un visualiseur du pipeline.

---

## User story 1 : discuter dans le navigateur

**En tant qu'** utilisateur qui n'aime pas le terminal,
**je veux** discuter avec l'assistant dans mon navigateur,
**afin d'** utiliser SensAI sans ligne de commande.

### Critères d'acceptation

- [x] La connexion par email crée le profil ou met à jour le nom et les instructions.
- [x] La réponse s'écrit au fur et à mesure dans le chat.
- [x] Les commandes `/…` fonctionnent aussi dans la webapp.

**Vérifié par :** `test_wrapper_creates_deep_context_and_streams` (couche `SensAIWrapper`).

---

## User story 2 : gérer plusieurs conversations

**En tant qu'** utilisateur,
**je veux** créer de nouvelles conversations et rouvrir les anciennes depuis une barre latérale,
**afin de** séparer mes sujets sans perdre mon historique.

### Critères d'acceptation

- [x] « Nouvelle conversation » crée un chat vide et l'ouvre.
- [x] Un clic sur une conversation de la liste l'ouvre avec ses messages.
- [x] Créer une conversation archive les précédentes en mémoire longue.

**Vérifié par :** `test_webapp_new_chat_archives_previous_chats`.

---

## Preuves

### Code

- [`src/webapp/app.py`](../../src/webapp/app.py)
- [`src/webapp/views.py`](../../src/webapp/views.py)
- [`src/webapp/utils.py`](../../src/webapp/utils.py)
- [`src/galerelm/wrapper.py`](../../src/galerelm/wrapper.py)
- [`script/frontend.sh`](../../script/frontend.sh)

### Tests automatisés

Les tests cités dans les critères d'acceptation se relancent avec :

```bash
.venv/bin/python -m pytest -q \
  src/galerelm/unit_tests/test_engine_and_repl.py::test_wrapper_creates_deep_context_and_streams \
  src/galerelm/unit_tests/test_memory_archive.py::test_webapp_new_chat_archives_previous_chats
```

Résultat au 1er novembre 2026 : 2 tests passés, 0 en échec.

### Démonstration manuelle

1. Lancer Ollama puis `./script/frontend.sh`, et ouvrir http://127.0.0.1:7860.
2. Se connecter avec un email : la page de chat s'ouvre.
3. Envoyer un message : la réponse s'écrit au fur et à mesure.
4. Cliquer sur « Nouvelle conversation », puis rouvrir l'ancienne depuis la liste.

---

## Limites

- Pas de mot de passe : l'email identifie le profil, il ne le protège pas.
- Pas de boîte de confirmation pour les outils sensibles : ils y sont toujours refusés.
- Les logs d'appels d'outils ne sont affichés que dans la CLI.
- L'interface Gradio elle-même n'a pas de tests automatisés.
