# X1 : Interface web

[Retour aux user stories](README.md)

**Statut :** Fait

---

## Ce que demande le sujet

- Un frontend web découplé, qui repose sur le même backend que la CLI.

## Ce que fait SensAI

- Une application **Gradio** (`src/webapp/`), lancée avec `./scripts/A1Libi -run` (Docker).
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

## Ce qui a été ajouté pour terminer la feature

- **Changement d'agent** : liste déroulante « Agent » dans la barre latérale (personas A5), sans effacer la conversation.
- **Consommation affichée** sous le chat après chaque réponse : tokens lus et générés, remplissage de la fenêtre de contexte,
  mémoire courte (messages / limite), agent et modèle actifs.
- **Confirmation des actions sensibles** dans la webapp : l'action est mise en attente et décrite, puis exécutée
  avec `/confirmer` ou abandonnée avec `/annuler`.
- **Onglet Monitoring** (EV3).
- Deux bugs corrigés : l'inspecteur appelait une méthode inexistante (`render_system`), ce qui faisait planter chaque message,
  et les commandes `/…` utilisaient un attribut inexistant (`core.ui`) avec un mauvais découpage de la commande.

### Tests de la finalisation

```bash
.venv/bin/python -m pytest -q \
  src/galerelm/unit_tests/test_persona_webapp.py \
  src/galerelm/unit_tests/test_monitoring.py
```

Résultat au 1er novembre 2026 : 24 tests passés, 0 en échec.

### Vérification avec le vrai modèle

La webapp se charge, et son contrôleur a été testé de bout en bout : message, inspecteur, consommation, commande `/persona`, changement d'agent, confirmation et annulation d'une action.

---

## Preuves

### Code

- [`src/webapp/app.py`](../../src/webapp/app.py)
- [`src/webapp/views.py`](../../src/webapp/views.py)
- [`src/webapp/utils.py`](../../src/webapp/utils.py)
- [`src/galerelm/wrapper.py`](../../src/galerelm/wrapper.py)
- [`scripts/A1Libi`](../../scripts/A1Libi)

### Tests automatisés

Les tests cités dans les critères d'acceptation se relancent avec :

```bash
.venv/bin/python -m pytest -q \
  src/galerelm/unit_tests/test_engine_and_repl.py::test_wrapper_creates_deep_context_and_streams \
  src/galerelm/unit_tests/test_memory_archive.py::test_webapp_new_chat_archives_previous_chats
```

Résultat au 1er novembre 2026 : 2 tests passés, 0 en échec.

### Démonstration manuelle

1. Lancer `./scripts/A1Libi -run`, et ouvrir http://localhost:7860.
2. Se connecter avec un email : la page de chat s'ouvre.
3. Envoyer un message : la réponse s'écrit au fur et à mesure.
4. Cliquer sur « Nouvelle conversation », puis rouvrir l'ancienne depuis la liste.

---

## Limites

- Le contrôleur de la webapp est partagé : l'agent choisi s'applique à tous les utilisateurs connectés en même temps.
- Pas de mot de passe : l'email identifie le profil, il ne le protège pas.
