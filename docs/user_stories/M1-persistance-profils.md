# M1 : Persistance et profils

[Retour aux user stories](README.md)

**Statut :** Fait

---

## Ce que demande le sujet

- Sauvegarder l'historique des sessions.
- Injecter automatiquement un profil utilisateur persistant.

## Ce que fait SensAI

- Les profils, les chats et les messages sont stockés dans SQLite (`galerelm.db`, à la racine).
- Au lancement, le dernier chat du profil est rechargé.
- Les instructions du profil servent de prompt système à chaque tour.
- La webapp liste les chats d'un profil et permet d'en ouvrir un ancien.

---

## User story 1 : reprendre ma conversation

**En tant qu'** utilisateur,
**je veux** retrouver ma dernière conversation quand je relance SensAI,
**afin de** continuer là où je m'étais arrêté.

### Critères d'acceptation

- [x] Chaque message est enregistré dans la base dès qu'il est envoyé.
- [x] Au lancement, le dernier chat du profil est rechargé avec ses messages.
- [x] La base est la même, quel que soit le dossier d'où l'outil est lancé.

**Vérifié par :** `test_chat_engine_stream_and_persistence`, `test_sqlalchemy_mappings`,
`test_database_path_does_not_depend_on_working_directory`.

---

## User story 2 : un assistant qui me connaît

**En tant qu'** utilisateur,
**je veux** que mes instructions de profil soient appliquées à chaque réponse,
**afin de** ne pas répéter mes préférences à chaque conversation.

### Critères d'acceptation

- [x] Un profil est créé automatiquement au premier lancement, avec des instructions par défaut.
- [x] Les instructions du profil sont placées en tête du prompt système.
- [x] Les variables du profil (`{persona}`) sont remplacées au moment du rendu.
- [x] Dans la webapp, se connecter avec un email existant met à jour le nom et les instructions.

**Vérifié par :** `test_profile_creation`, `test_prompt_builder_with_profile_memories_and_tools`.

---

## Preuves

### Code

- [`src/galerelm/session_manager.py`](../../src/galerelm/session_manager.py)
- [`src/galerelm/database.py`](../../src/galerelm/database.py)
- [`src/galerelm/models/profile.py`](../../src/galerelm/models/profile.py)
- [`src/galerelm/models/context.py`](../../src/galerelm/models/context.py)

### Tests automatisés

Les tests cités dans les critères d'acceptation se relancent avec :

```bash
.venv/bin/python -m pytest -q \
  src/galerelm/unit_tests/test_engine_and_repl.py::test_chat_engine_stream_and_persistence \
  src/galerelm/unit_tests/test_db_mapping.py::test_sqlalchemy_mappings \
  src/galerelm/unit_tests/test_memory_archive.py::test_database_path_does_not_depend_on_working_directory \
  src/galerelm/unit_tests/test_profile.py::test_profile_creation \
  src/galerelm/unit_tests/test_prompt.py::test_prompt_builder_with_profile_memories_and_tools
```

Résultat au 1er novembre 2026 : 5 tests passés, 0 en échec.

### Démonstration manuelle

1. Lancer le chat et écrire « Je m'appelle Julien ».
2. Quitter avec `/quit`, puis relancer : `/messages` affiche la conversation précédente.
3. Lancer depuis `src/` puis depuis la racine : la même base `galerelm.db` (racine du projet) est utilisée.

---

## Limites

- Les instructions du profil se modifient dans la webapp (page de connexion), pas encore depuis la CLI.
- En CLI, le profil utilisé est toujours `user@sensai.ai`.
