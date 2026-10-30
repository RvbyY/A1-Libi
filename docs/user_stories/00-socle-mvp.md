# 🧱 Socle MVP : chatbot en ligne de commande

[⬅️ Retour aux user stories](README.md)

**Statut :** ✅ Fait

---

## 📋 Ce que demande le sujet

- Un chatbot en ligne de commande.
- Des réponses affichées en **streaming**.
- L'historique de la session envoyé à chaque tour.
- La gestion des erreurs : modèle absent, entrée vide, réseau coupé.
- Le choix du modèle par argument CLI ou par fichier de configuration.

## ⚙️ Ce que fait SensAI

- `src/main.py` lance la boucle du terminal (`TerminalREPL`).
- Les réponses arrivent token par token depuis l'API HTTP d'Ollama.
- Le contexte de la session est renvoyé au modèle à chaque message.
- `--model`, `--config`, `--host` et `config.yaml` choisissent le modèle sans toucher au code.
- `src/galerelm/ollama.py` traduit les erreurs réseau en messages clairs.

---

## 👤 User story 1 : voir la réponse s'écrire

**En tant qu'** utilisateur du terminal,
**je veux** voir la réponse de l'assistant s'afficher au fur et à mesure,
**afin de** commencer à lire sans attendre la fin de la génération.

### ✅ Critères d'acceptation

- [x] Les tokens s'affichent dès qu'Ollama les envoie.
- [x] La réponse complète est enregistrée dans l'historique à la fin.
- [x] Le message suivant reçoit les tours précédents comme contexte.

**Vérifié par :** `test_chat_engine_stream_and_persistence`.

---

## 👤 User story 2 : choisir mon modèle

**En tant qu'** utilisateur,
**je veux** choisir le modèle avec `--model` ou dans `config.yaml`,
**afin de** changer de modèle sans modifier le code.

### ✅ Critères d'acceptation

- [x] `--model` a priorité sur `config.yaml`, qui a priorité sur `.env`.
- [x] Une clé inconnue ou une valeur invalide dans le YAML est refusée avec un message clair.
- [x] `config.yaml` à la racine est chargé automatiquement.

**Vérifié par :** `test_cli_overrides_yaml`, `test_load_yaml_rejects_invalid_files`,
`test_default_config_file_is_loaded_when_present`.

---

## 👤 User story 3 : comprendre une erreur

**En tant qu'** utilisateur,
**je veux** un message clair quand Ollama est éteint ou quand le modèle n'est pas installé,
**afin de** savoir quelle commande lancer pour corriger le problème.

### ✅ Critères d'acceptation

- [x] Ollama injoignable : le message propose `ollama serve`.
- [x] Modèle absent : le message propose `ollama pull <modèle>` et liste les modèles installés.
- [x] Une entrée vide est ignorée sans appeler le modèle.
- [x] Une erreur pendant la conversation n'arrête pas la session.

**Vérifié par :** `test_connection_refused_becomes_unreachable`, `test_streamed_404_becomes_model_not_found`,
`test_main_stops_when_model_is_missing`, `test_check_ollama_unreachable`.

---

## ⚠️ Limites

- Si la génération échoue, le message de l'utilisateur reste dans l'historique sans réponse.
