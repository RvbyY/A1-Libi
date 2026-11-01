# R1 : RAG basique

[Retour aux user stories](README.md)

**Statut :** Fait

---

## Ce que demande le sujet

- Ingérer des documents locaux, les découper, les vectoriser et les stocker.
- Faire une recherche sémantique pour enrichir le contexte.

## Ce que fait SensAI

- Les anciens messages sont vectorisés avec `nomic-embed-text` (via Ollama) et stockés dans `DeepContext`.
- À chaque question, les 3 souvenirs les plus proches sont injectés dans le prompt.
- Ouvrir un nouveau chat archive les chats précédents dans cette mémoire longue.
- Le tool `search_memory` permet aussi au modèle de chercher lui-même.

---

## User story 1 : se souvenir d'une ancienne conversation

**En tant qu'** utilisateur,
**je veux** que l'assistant retrouve ce que je lui ai dit dans un autre chat,
**afin de** ne pas avoir à me répéter.

### Critères d'acceptation

- [x] `/new` et « nouveau chat » archivent les chats précédents en mémoire longue.
- [x] Un message déjà archivé n'est pas recopié.
- [x] Les souvenirs trouvés sont injectés en tête du prompt, avec une consigne pour s'en servir.

**Vérifié par :** `test_new_chat_archives_previous_short_chat`, `test_new_chat_memory_is_injected_in_next_prompt`,
`test_archiving_is_idempotent_and_skips_noise`.

---

## User story 2 : une recherche par le sens

**En tant qu'** utilisateur,
**je veux** que la recherche retrouve un souvenir même avec d'autres mots,
**afin que** « où j'habite ? » retrouve « je vis à Lyon ».

### Critères d'acceptation

- [x] Les textes sont transformés en vecteurs par le modèle d'embedding.
- [x] Les souvenirs sont classés par similarité cosinus.
- [x] Sans modèle d'embedding, SensAI fonctionne quand même (mémoire longue désactivée, avec un avertissement).

**Vérifié par :** `test_embedding_service_and_rag_manager`, `test_check_ollama_ok_with_warning_for_missing_embedding_model`.

---

## Ce qui a été ajouté pour terminer la feature

- **Ingestion** (`src/galerelm/documents.py`) : `/ingest <fichier ou dossier>` lit les fichiers texte
  (`.md`, `.txt`, `.rst`, `.csv`, `.json`, `.yaml`, `.py`, `.html`), en ignorant les dossiers cachés.
- **Découpage** en fragments d'environ 800 caractères, coupés entre deux paragraphes, phrases ou mots,
  avec un chevauchement de 100 caractères.
- **Vectorisation** avec le modèle d'embedding, et **stockage** dans la table `document_chunks` (un profil = ses documents).
  Réingérer un fichier remplace ses anciens fragments.
- **Recherche** par similarité cosinus ; les meilleurs extraits sont injectés dans le prompt avec leur source
  (`[guide.md#2]`), et donnés au juge anti-hallucination comme faits.
- `/documents` liste les fichiers ingérés ; `/documents oublier <chemin>` ou `oublier tout` les retire.

### Tests de la finalisation

```bash
.venv/bin/python -m pytest -q \
  src/galerelm/unit_tests/test_documents.py
```

Résultat au 1er novembre 2026 : 10 tests passés, 0 en échec.

### Vérification avec le vrai modèle

Mesuré avec le vrai modèle dans [l'évaluation par le juge](../18-evaluation-juge.md) : avec les documents ingérés, la fidélité des réponses passe de 3,2 à 5 sur 5, et les réponses ancrées de 40 % à 100 %.

---

## Preuves

### Code

- [`src/galerelm/rag.py`](../../src/galerelm/rag.py)
- [`src/galerelm/models/deep_context.py`](../../src/galerelm/models/deep_context.py)
- [`src/galerelm/session_manager.py`](../../src/galerelm/session_manager.py)
- [`src/tools/memory/memory_tools.py`](../../src/tools/memory/memory_tools.py)

### Tests automatisés

Les tests cités dans les critères d'acceptation se relancent avec :

```bash
.venv/bin/python -m pytest -q \
  src/galerelm/unit_tests/test_memory_archive.py::test_new_chat_archives_previous_short_chat \
  src/galerelm/unit_tests/test_memory_archive.py::test_new_chat_memory_is_injected_in_next_prompt \
  src/galerelm/unit_tests/test_memory_archive.py::test_archiving_is_idempotent_and_skips_noise \
  src/galerelm/unit_tests/test_db_mapping.py::test_embedding_service_and_rag_manager \
  src/galerelm/unit_tests/test_ollama_errors.py::test_check_ollama_ok_with_warning_for_missing_embedding_model
```

Résultat au 1er novembre 2026 : 5 tests passés, 0 en échec.

### Démonstration manuelle

1. Écrire « J'habite à Lyon », puis taper `/new` : le terminal indique le nombre de messages archivés.
2. Taper `/memories` : le souvenir apparaît dans la mémoire longue.
3. Demander « Où est-ce que j'habite ? » puis taper `/payload` : le souvenir figure en tête du prompt système.

---

## Limites

- Pas de PDF : il faudrait ajouter une bibliothèque de lecture PDF.
- Pas de seuil de pertinence ni de reclassement des extraits : c'est le périmètre de R2.
